"""Tests for Sandbox — runtime permission enforcement."""
import pytest
import sys
from marketplace.sandbox import (
    ImportBlocker,
    PermissionGuard,
    SandboxedExecutor,
    SAFE_MODULES,
    PERMISSION_MODULES,
)


# --- ImportBlocker Tests ---

def test_blocker_allows_safe_modules():
    """Safe modules like json and re should always be importable."""
    blocker = ImportBlocker(allowed_modules=set())
    # find_module returns None means "allow"
    assert blocker.find_module("json") is None
    assert blocker.find_module("re") is None
    assert blocker.find_module("math") is None


def test_blocker_blocks_unauthorized_modules():
    """Modules not in allowed set should be blocked."""
    blocker = ImportBlocker(allowed_modules=set())
    # find_module returns self means "block"
    assert blocker.find_module("subprocess") is blocker


def test_blocker_allows_permitted_modules():
    """Modules explicitly in the allowed set should pass."""
    allowed = PERMISSION_MODULES["network"]
    blocker = ImportBlocker(allowed_modules=allowed | SAFE_MODULES)
    assert blocker.find_module("requests") is None


def test_blocker_blocks_always_dangerous():
    """ctypes and importlib should always be blocked."""
    # Even with all permissions granted
    all_allowed = set()
    for mods in PERMISSION_MODULES.values():
        all_allowed.update(mods)
    all_allowed.update(SAFE_MODULES)
    
    blocker = ImportBlocker(allowed_modules=all_allowed)
    assert blocker.find_module("ctypes") is blocker


def test_blocker_handles_submodules():
    """Blocking 'os' should also block 'os.path'."""
    blocker = ImportBlocker(allowed_modules=set())
    assert blocker.find_module("os.path") is blocker


# --- PermissionGuard Tests ---

def test_guard_blocks_imports_inside_context():
    """Imports should be blocked inside the guard."""
    with PermissionGuard(permissions=[]):
        # subprocess is not in any permission
        blocker_found = any(
            isinstance(f, ImportBlocker) for f in sys.meta_path
        )
        assert blocker_found is True


def test_guard_cleans_up_after_exit():
    """Import blocker should be removed after exiting the guard."""
    with PermissionGuard(permissions=[]):
        pass
    
    blocker_found = any(
        isinstance(f, ImportBlocker) for f in sys.meta_path
    )
    assert blocker_found is False


def test_guard_cleans_up_on_exception():
    """Import blocker should be removed even if an exception occurs."""
    try:
        with PermissionGuard(permissions=[]):
            raise ValueError("test error")
    except ValueError:
        pass
    
    blocker_found = any(
        isinstance(f, ImportBlocker) for f in sys.meta_path
    )
    assert blocker_found is False


def test_guard_with_network_allows_requests():
    """Network permission should allow requests-related modules."""
    guard = PermissionGuard(permissions=["network"])
    assert "requests" in guard.allowed_modules


def test_guard_with_filesystem_allows_pathlib():
    """Filesystem permission should allow pathlib."""
    guard = PermissionGuard(permissions=["filesystem"])
    assert "pathlib" in guard.allowed_modules


def test_guard_with_no_perms_still_allows_safe():
    """Even with no permissions, safe modules should be allowed."""
    guard = PermissionGuard(permissions=[])
    assert "json" in guard.allowed_modules
    assert "math" in guard.allowed_modules


# --- SandboxedExecutor Tests ---

def test_executor_runs_safe_function():
    """A function using only safe modules should execute without issues."""
    executor = SandboxedExecutor()
    executor.register_skill_permissions("test_skill", ["network"])
    
    def safe_func(name="World"):
        import json
        return json.dumps({"greeting": f"Hello, {name}!"})
    
    result = executor.execute_tool(safe_func, "safe_func", "test_skill", {"name": "Bazaar"})
    assert "Hello, Bazaar!" in result


def test_executor_raises_for_unregistered_skill():
    """Executing a tool for a skill with no registered permissions should raise."""
    executor = SandboxedExecutor()
    
    def some_func():
        return "hi"
    
    with pytest.raises(PermissionError):
        executor.execute_tool(some_func, "some_func", "unknown_skill")


def test_executor_clear_removes_all():
    """clear() should remove all registered permissions."""
    executor = SandboxedExecutor()
    executor.register_skill_permissions("a", ["network"])
    executor.register_skill_permissions("b", ["filesystem"])
    
    executor.clear()
    assert executor.get_skill_permissions("a") is None
    assert executor.get_skill_permissions("b") is None


# --- Integration: Real Import Blocking ---

def test_sandbox_blocks_subprocess_without_execute():
    """A tool importing subprocess without 'execute' permission should fail."""
    def malicious_func():
        import subprocess
        return subprocess.run(["echo", "hacked"], capture_output=True)
    
    executor = SandboxedExecutor()
    executor.register_skill_permissions("bad_skill", ["network"])  # no "execute"
    
    with pytest.raises(ImportError, match="SANDBOX"):
        executor.execute_tool(malicious_func, "malicious_func", "bad_skill")


def test_sandbox_allows_subprocess_with_execute():
    """A tool importing subprocess WITH 'execute' permission should work."""
    def legit_func():
        import subprocess
        result = subprocess.run(["echo", "hello"], capture_output=True, text=True)
        return result.stdout.strip()
    
    executor = SandboxedExecutor()
    executor.register_skill_permissions("build_skill", ["execute"])
    
    result = executor.execute_tool(legit_func, "legit_func", "build_skill")
    assert result == "hello"