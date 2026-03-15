"""Tests for Day 4: SkillLoader — dynamic tool loading and execution."""
from pathlib import Path

import pytest

from marketplace.loader import SkillLoader
from marketplace.registry import SkillRegistry

# --- Helpers ---

def create_skill_with_tool(base_path: Path, skill_name: str,
                           tool_name: str, function_code: str) -> Path:
    """Create a skill directory with a working tool module."""
    skill_dir = base_path / skill_name
    tools_dir = skill_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    # Write manifest
    (skill_dir / "manifest.yaml").write_text(f"""
name: {skill_name}
version: 1.0.0
description: Test skill with tool
tools:
  - name: {tool_name}
    description: A test tool
    module: tools.{skill_name}_tools
    function: {tool_name}
""")

    # Write tool module
    (tools_dir / f"{skill_name}_tools.py").write_text(function_code)

    return skill_dir


# --- Fixtures ---

@pytest.fixture
def loaded_registry(tmp_path):
    """Registry with a skill that has a real callable tool."""
    registry = SkillRegistry(skills_dir=tmp_path)

    create_skill_with_tool(
        tmp_path, "greeter", "say_hello",
        'def say_hello(name="World"):\n    return f"Hello, {name}!"'
    )

    registry.discover_skills()
    return registry


@pytest.fixture
def loader(loaded_registry):
    """SkillLoader with a pre-loaded registry."""
    return SkillLoader(registry=loaded_registry)


# --- Module Path Resolution Tests ---

def test_resolve_module_path_converts_dots_to_paths(loader):
    """Module string 'tools.gmail_reader' should resolve to tools/gmail_reader.py."""
    skill_dir = Path("/fake/skill")
    result = loader._resolve_module_path(skill_dir, "tools.gmail_reader")
    assert result == Path("/fake/skill/tools/gmail_reader.py")


def test_resolve_module_path_handles_single_module(loader):
    """Module string 'reader' should resolve to reader.py in skill root."""
    skill_dir = Path("/fake/skill")
    result = loader._resolve_module_path(skill_dir, "reader")
    assert result == Path("/fake/skill/reader.py")


# --- Tool Loading Tests ---

def test_load_skill_tools_loads_callable(loader):
    """load_skill_tools should return a dict with actual callable functions."""
    tools = loader.load_skill_tools("greeter")
    assert "say_hello" in tools
    assert callable(tools["say_hello"])


def test_loaded_tool_is_executable(loader):
    """A loaded tool should actually execute and return results."""
    tools = loader.load_skill_tools("greeter")
    result = tools["say_hello"](name="Bazaar")
    assert result == "Hello, Bazaar!"


def test_loaded_tool_uses_default_args(loader):
    """A loaded tool should work with default arguments."""
    tools = loader.load_skill_tools("greeter")
    result = tools["say_hello"]()
    assert result == "Hello, World!"


def test_load_skill_tools_returns_empty_for_unknown_skill(loader):
    """Loading tools for a non-existent skill should return empty dict."""
    tools = loader.load_skill_tools("nonexistent")
    assert tools == {}


def test_load_skill_tools_skips_missing_module_file(tmp_path):
    """If a declared module file doesn't exist, skip that tool (don't crash)."""
    registry = SkillRegistry(skills_dir=tmp_path)

    # Skill with a tool pointing to a non-existent module
    skill_dir = tmp_path / "broken_skill"
    skill_dir.mkdir()
    (skill_dir / "manifest.yaml").write_text("""
name: broken_skill
tools:
  - name: broken_tool
    description: This tool's module doesn't exist
    module: tools.nonexistent
    function: nope
""")
    registry.discover_skills()

    loader = SkillLoader(registry=registry)
    tools = loader.load_skill_tools("broken_skill")
    assert tools == {}


# --- Load All + Resolve Tests ---

def test_load_all_tools_loads_from_all_skills(tmp_path):
    """load_all_tools should load tools from every registered skill."""
    registry = SkillRegistry(skills_dir=tmp_path)

    create_skill_with_tool(
        tmp_path, "skill_a", "tool_a",
        'def tool_a():\n    return "A"'
    )
    create_skill_with_tool(
        tmp_path, "skill_b", "tool_b",
        'def tool_b():\n    return "B"'
    )

    registry.discover_skills()
    loader = SkillLoader(registry=registry)

    all_tools = loader.load_all_tools()
    assert "tool_a" in all_tools
    assert "tool_b" in all_tools


def test_resolve_tool_call_executes_correct_function(loader):
    """resolve_tool_call should find and execute the right tool."""
    loader.load_all_tools()
    result = loader.resolve_tool_call("say_hello", {"name": "Test"})
    assert result == "Hello, Test!"


def test_resolve_tool_call_raises_for_unknown_tool(loader):
    """resolve_tool_call should raise KeyError for non-existent tools."""
    with pytest.raises(KeyError):
        loader.resolve_tool_call("nonexistent_tool")


def test_get_tool_definitions_returns_metadata(loader):
    """get_tool_definitions should return ToolDefinition objects for all tools."""
    loader.load_all_tools()
    definitions = loader.get_tool_definitions()
    assert len(definitions) >= 1
    assert definitions[0].name == "say_hello"


# --- Caching Tests ---

def test_tools_are_cached_after_first_load(loader):
    """Loading the same skill twice should return cached tools."""
    tools_1 = loader.load_skill_tools("greeter")
    tools_2 = loader.load_skill_tools("greeter")
    # Same function object (not re-imported)
    assert tools_1["say_hello"] is tools_2["say_hello"]


def test_clear_cache_forces_reload(loader):
    """clear_cache should remove all cached tools and modules."""
    loader.load_all_tools()
    assert len(loader._loaded_tools) > 0

    loader.clear_cache()
    assert len(loader._loaded_tools) == 0
    assert len(loader._loaded_modules) == 0
