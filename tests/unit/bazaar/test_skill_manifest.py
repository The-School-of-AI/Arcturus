"""Tests for SkillManifest, ToolDefinition, and MarketplaceSkill base class."""
import pytest
from pathlib import Path
from marketplace.skill_base import (
    load_manifest, SkillManifest, ToolDefinition, MarketplaceSkill
)


# --- ToolDefinition Tests ---

def test_tool_definition_creates_with_required_fields():
    """A ToolDefinition should be creatable with just the 4 required fields."""
    tool = ToolDefinition(
        name="read_inbox",
        description="Read emails from Gmail",
        module="tools.gmail_reader",
        function="read_inbox"
    )
    assert tool.name == "read_inbox"
    assert tool.module == "tools.gmail_reader"
    assert tool.parameters == {}  # defaults to empty


def test_tool_definition_accepts_optional_parameters_schema():
    """A ToolDefinition should accept an optional JSON Schema for parameters."""
    tool = ToolDefinition(
        name="search",
        description="Search emails",
        module="tools.gmail_reader",
        function="search",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}}
        }
    )
    assert "query" in tool.parameters["properties"]


# --- SkillManifest Tests ---

def test_manifest_requires_name():
    """SkillManifest should reject creation without a name — it's the only required field."""
    with pytest.raises(Exception):
        SkillManifest()


def test_manifest_defaults_are_sensible():
    """All optional fields should have sensible defaults so minimal manifests work."""
    manifest = SkillManifest(name="test_skill")
    assert manifest.version == "1.0.0"
    assert manifest.author == "Community"
    assert manifest.category == "general"
    assert manifest.dependencies == []
    assert manifest.skill_dependencies == []
    assert manifest.tools == []


def test_manifest_loads_from_example_yaml():
    """The example manifest.yaml should load and validate correctly."""
    manifest = load_manifest(Path("marketplace/skills/_example/manifest.yaml"))
    assert manifest.name == "example_skill"
    assert manifest.version == "1.0.0"
    assert len(manifest.tools) == 2
    assert manifest.tools[0].name == "say_hello"


def test_load_manifest_raises_on_missing_file():
    """load_manifest should raise FileNotFoundError for non-existent paths."""
    with pytest.raises(FileNotFoundError):
        load_manifest(Path("does/not/exist/manifest.yaml"))


def test_load_manifest_raises_on_empty_file(tmp_path):
    """load_manifest should raise ValueError if the YAML file is empty."""
    empty_manifest = tmp_path / "manifest.yaml"
    empty_manifest.write_text("")
    with pytest.raises(ValueError):
        load_manifest(empty_manifest)


# --- MarketplaceSkill Tests ---

def test_marketplace_skill_cannot_be_instantiated_directly():
    """MarketplaceSkill is abstract — you must subclass and implement prompt_text."""
    with pytest.raises(TypeError):
        MarketplaceSkill()


def test_concrete_skill_must_implement_prompt_text():
    """A subclass that doesn't implement prompt_text should fail to instantiate."""
    class IncompleteSkill(MarketplaceSkill):
        pass  # forgot to implement prompt_text!
    
    with pytest.raises(TypeError):
        IncompleteSkill()


def test_concrete_skill_with_prompt_text_works():
    """A properly implemented subclass should instantiate successfully."""
    class HelloSkill(MarketplaceSkill):
        @property
        def prompt_text(self) -> str:
            return "You can say hello!"
    
    skill = HelloSkill()
    assert skill.prompt_text == "You can say hello!"
    assert skill.get_callable_tools() == {}  # default empty