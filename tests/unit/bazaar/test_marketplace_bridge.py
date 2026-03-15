"""Tests for MarketplaceBridge integration of registry + installer + loader."""
import pytest
from pathlib import Path
from marketplace.bridge import MarketplaceBridge


# --- Helpers ---

def create_skill_with_tool(base_path: Path, name: str, tool_name: str) -> Path:
    """Create a skill with a working tool."""
    skill_dir = base_path / name
    tools_dir = skill_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    
    (skill_dir / "manifest.yaml").write_text(f"""
name: {name}
version: 1.0.0
description: Test skill {name}
tools:
  - name: {tool_name}
    description: Test tool
    module: tools.{name}_tools
    function: {tool_name}
""")
    
    (tools_dir / f"{name}_tools.py").write_text(
        f'def {tool_name}(name="World"):\n    return f"Hello from {name}, {{name}}!"'
    )
    return skill_dir


# --- Fixtures ---

@pytest.fixture
def bridge(tmp_path):
    """A marketplace bridge with one installed skill."""
    create_skill_with_tool(tmp_path, "greeter", "say_hello")
    b = MarketplaceBridge(skills_dir=tmp_path)
    b.initialize()
    return b


# --- Initialization Tests ---

def test_bridge_initializes_and_discovers(bridge):
    """Bridge should discover skills on initialization."""
    assert bridge.registry.count == 1


def test_bridge_initializes_only_once(bridge):
    """Calling initialize() multiple times should be safe (idempotent)."""
    bridge.initialize()
    bridge.initialize()
    assert bridge.registry.count == 1


# --- Tool Resolution Tests ---

def test_resolve_tool_executes_marketplace_tool(bridge):
    """resolve_tool should execute a marketplace tool and return the result."""
    result = bridge.resolve_tool("say_hello", {"name": "Bazaar"})
    assert result == "Hello from greeter, Bazaar!"


def test_resolve_tool_returns_none_for_unknown(bridge):
    """resolve_tool should return None for non-marketplace tools."""
    result = bridge.resolve_tool("unknown_tool")
    assert result is None


# --- Tool Definitions Tests ---

def test_get_tool_definitions_returns_metadata(bridge):
    """get_tool_definitions should return ToolDefinition objects."""
    defs = bridge.get_tool_definitions()
    assert len(defs) >= 1
    assert defs[0].name == "say_hello"


# --- Install + Refresh Tests ---

def test_install_and_refresh_makes_tool_available(tmp_path):
    """Installing a skill and refreshing should make its tools callable."""
    install_dir = tmp_path / "installed"
    install_dir.mkdir()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    
    bridge = MarketplaceBridge(skills_dir=install_dir)
    bridge.initialize()
    
    # No tools initially
    assert bridge.resolve_tool("say_hi") is None
    
    # Create and install a skill
    skill_dir = create_skill_with_tool(source_dir, "hello_skill", "say_hi")
    result = bridge.installer.install_skill(skill_dir)
    assert result.success is True
    
    # Refresh to pick up the new skill
    bridge.refresh()
    
    # Now the tool should work
    result = bridge.resolve_tool("say_hi", {"name": "Test"})
    assert result == "Hello from hello_skill, Test!"


def test_uninstall_and_refresh_removes_tool(tmp_path):
    """Uninstalling and refreshing should remove the tool."""
    create_skill_with_tool(tmp_path, "temp_skill", "temp_tool")
    
    bridge = MarketplaceBridge(skills_dir=tmp_path)
    bridge.initialize()
    
    # Tool works initially
    assert bridge.resolve_tool("temp_tool") is not None
    
    # Uninstall
    bridge.installer.uninstall_skill("temp_skill")
    bridge.refresh()
    
    # Tool should be gone
    assert bridge.resolve_tool("temp_tool") is None