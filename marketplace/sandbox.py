import sys
import threading
from typing import Set, Optional, Dict, List, Any, Callable
from pathlib import Path
import logging

logger = logging.getLogger("bazaar")


# --- Permission → Allowed Modules Mapping ---

# Modules that are ALWAYS allowed (safe standard library)
SAFE_MODULES = {
    "json", "re", "math", "datetime", "time", "collections",
    "itertools", "functools", "typing", "dataclasses", "enum",
    "logging", "copy", "string", "textwrap", "hashlib", "base64",
    "uuid", "decimal", "fractions", "statistics", "random",
    "abc", "contextlib", "io", "pydantic", "yaml",
}

# Modules unlocked by each permission
PERMISSION_MODULES: Dict[str, Set[str]] = {
    "network": {
        "requests", "urllib", "urllib3", "httpx", "aiohttp",
        "socket", "ssl", "http", "http.client", "email",
    },
    "filesystem": {
        "os", "os.path", "pathlib", "shutil", "glob",
        "tempfile", "fnmatch", "stat",
    },
    "execute": {
        "subprocess", "os.system", "os.popen",
        "multiprocessing", "signal",
    },
}

# Modules that are ALWAYS blocked (dangerous regardless of permissions)
ALWAYS_BLOCKED = {
    "ctypes",       # Direct memory access
    "importlib",    # Can bypass this sandbox
}


class ImportBlocker:
    """
    Custom import hook that blocks unauthorized module imports.
    
    Installed into sys.meta_path to intercept imports at the finder level.
    Only active when inside a PermissionGuard context.
    """
    
    def __init__(self, allowed_modules: Set[str]):
        self.allowed_modules = allowed_modules
    
    def find_module(self, fullname: str, path=None):
        """
        Called by Python for every import statement.
        
        Returns:
            self → to trigger load_module (which raises ImportError)
            None → let normal import proceed
        """
        # Get the top-level module name (e.g., "os" from "os.path")
        top_module = fullname.split(".")[0]
        
        # Always allow safe modules
        if top_module in SAFE_MODULES or fullname in SAFE_MODULES:
            return None
        
        # Always block dangerous modules
        if top_module in ALWAYS_BLOCKED or fullname in ALWAYS_BLOCKED:
            logger.warning(f"SANDBOX: Blocked always-dangerous import '{fullname}'")
            return self  # Trigger load_module → raises ImportError
        
        # Check if the module is allowed by current permissions
        if top_module in self.allowed_modules or fullname in self.allowed_modules:
            return None
        
        # Not in any allowed list → block it
        logger.warning(f"SANDBOX: Blocked unauthorized import '{fullname}'")
        return self
    
    def load_module(self, fullname):
        """Raise ImportError for blocked modules."""
        raise ImportError(
            f"SANDBOX: Module '{fullname}' is not allowed. "
            f"Add the required permission to manifest.yaml"
        )

class PermissionGuard:
    """
    Context manager that activates import restrictions for a set of permissions.
    
    Usage:
        with PermissionGuard(permissions=["network"]):
            import requests      # ✅ Allowed
            import subprocess    # ❌ ImportError
    """
    
    def __init__(self, permissions: List[str] = None):
        self.permissions = set(permissions or [])
        self._blocker: Optional[ImportBlocker] = None
        
        # Compute the full set of allowed modules
        self.allowed_modules = set(SAFE_MODULES)
        for perm in self.permissions:
            if perm in PERMISSION_MODULES:
                self.allowed_modules.update(PERMISSION_MODULES[perm])
    
    def __enter__(self):
        """Activate import restrictions."""
        self._blocker = ImportBlocker(self.allowed_modules)
        # Only evict modules that are *explicitly controlled* by permissions
        # the skill doesn't have. This avoids evicting internal Python
        # infrastructure (e.g. warnings) that allowed modules depend on.
        self._evicted: Dict[str, Any] = {}
        blocked_modules: Set[str] = set(ALWAYS_BLOCKED)
        for perm, mods in PERMISSION_MODULES.items():
            if perm not in self.permissions:
                blocked_modules.update(mods)

        for mod_name in list(sys.modules.keys()):
            top = mod_name.split(".")[0]
            if top in blocked_modules or mod_name in blocked_modules:
                self._evicted[mod_name] = sys.modules.pop(mod_name)
        sys.meta_path.insert(0, self._blocker)
        logger.debug(f"Sandbox activated with permissions: {self.permissions}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Deactivate import restrictions."""
        if self._blocker in sys.meta_path:
            sys.meta_path.remove(self._blocker)
        self._blocker = None
        # Restore evicted modules so the rest of the process is unaffected.
        sys.modules.update(self._evicted)
        self._evicted = {}
        logger.debug("Sandbox deactivated")
        return False  # Don't suppress exceptions

class SandboxedExecutor:
    """
    Executes marketplace skill tools within a permission sandbox.
    
    Wraps the SkillLoader's tool execution with PermissionGuard
    based on the skill's declared permissions.
    """
    
    def __init__(self):
        self._skill_permissions: Dict[str, List[str]] = {}
    
    def register_skill_permissions(self, skill_name: str, permissions: List[str]):
        """Register the permissions declared by a skill."""
        self._skill_permissions[skill_name] = permissions
        logger.debug(f"Registered permissions for '{skill_name}': {permissions}")
    
    def execute_tool(
        self,
        tool_func: Callable,
        tool_name: str,
        skill_name: str,
        arguments: Dict[str, Any] = None,
    ) -> Any:
        """
        Execute a tool function within the skill's permission sandbox.
        
        Args:
            tool_func: The callable tool function
            tool_name: Name of the tool (for logging)
            skill_name: Name of the skill that owns this tool
            arguments: Arguments to pass to the tool function
            
        Returns:
            The tool function's return value
            
        Raises:
            ImportError: If the tool tries to import unauthorized modules
            PermissionError: If the skill has no registered permissions
        """
        arguments = arguments or {}
        permissions = self._skill_permissions.get(skill_name)
        
        if permissions is None:
            raise PermissionError(
                f"No permissions registered for skill '{skill_name}'. "
                f"Register permissions before executing tools."
            )
        
        logger.info(f"Executing '{tool_name}' in sandbox (permissions: {permissions})")
        
        with PermissionGuard(permissions=permissions):
            return tool_func(**arguments)
    
    def get_skill_permissions(self, skill_name: str) -> Optional[List[str]]:
        """Get the registered permissions for a skill."""
        return self._skill_permissions.get(skill_name)
    
    def clear(self):
        """Clear all registered permissions (for testing)."""
        self._skill_permissions.clear()