"""
Tests for marketplace.sdk.templates and the --template flag on skill create.

Covers:
  - TemplateRegistry contents and lookup
  - All three new templates scaffold the correct files
  - Manifest permissions match template expectations
  - Unknown template name is rejected in the CLI
  - `skill template list` command output
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from marketplace.sdk.cli import main
from marketplace.sdk.templates import (
    get_template,
    list_templates,
    TEMPLATE_REGISTRY,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def invoke_create(runner: CliRunner, name: str, skills_root: str,
                  template: str = "default") -> object:
    """Invoke `arcturus skill create <name> --template <template>`."""
    return runner.invoke(
        main,
        ["skill", "create", name,
         "--skills-root", skills_root,
         "--template", template],
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# TemplateRegistry tests
# ---------------------------------------------------------------------------

class TestTemplateRegistry:

    def test_all_named_templates_present(self):
        """Registry must contain all four expected template names."""
        expected = {"default", "prompt_only", "tool_enabled", "agent_based"}
        assert expected == set(TEMPLATE_REGISTRY.keys())

    def test_get_template_returns_correct_info(self):
        tpl = get_template("prompt_only")
        assert tpl.name == "prompt_only"
        assert tpl.permissions == []

    def test_tool_enabled_declares_network(self):
        tpl = get_template("tool_enabled")
        assert "network" in tpl.permissions

    def test_agent_based_has_no_raw_permissions(self):
        tpl = get_template("agent_based")
        assert tpl.permissions == []

    def test_unknown_template_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown template"):
            get_template("nonexistent_template")

    def test_list_templates_returns_all(self):
        templates = list_templates()
        names = {t.name for t in templates}
        assert "prompt_only" in names
        assert "tool_enabled" in names
        assert "agent_based" in names


# ---------------------------------------------------------------------------
# prompt_only scaffold tests
# ---------------------------------------------------------------------------

class TestPromptOnlyTemplate:

    def test_create_exits_zero(self, tmp_path):
        runner = CliRunner()
        result = invoke_create(runner, "my_skill", str(tmp_path), "prompt_only")
        assert result.exit_code == 0, result.output

    def test_manifest_created(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "my_skill", str(tmp_path), "prompt_only")
        assert (tmp_path / "my_skill" / "manifest.yaml").exists()

    def test_manifest_has_no_permissions(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "my_skill", str(tmp_path), "prompt_only")
        manifest_path = tmp_path / "my_skill" / "manifest.yaml"
        data = yaml.safe_load(manifest_path.read_text())
        assert data["permissions"] == []

    def test_tool_file_created(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "my_skill", str(tmp_path), "prompt_only")
        assert (tmp_path / "my_skill" / "src" / "tools" / "main.py").exists()


# ---------------------------------------------------------------------------
# tool_enabled scaffold tests
# ---------------------------------------------------------------------------

class TestToolEnabledTemplate:

    def test_manifest_declares_network(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "my_skill", str(tmp_path), "tool_enabled")
        data = yaml.safe_load(
            (tmp_path / "my_skill" / "manifest.yaml").read_text()
        )
        assert "network" in data["permissions"]

    def test_tool_file_imports_httpx(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "my_skill", str(tmp_path), "tool_enabled")
        code = (tmp_path / "my_skill" / "src" / "tools" / "main.py").read_text()
        assert "httpx" in code


# ---------------------------------------------------------------------------
# agent_based scaffold tests
# ---------------------------------------------------------------------------

class TestAgentBasedTemplate:

    def test_manifest_has_skill_dependencies_key(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "my_skill", str(tmp_path), "agent_based")
        data = yaml.safe_load(
            (tmp_path / "my_skill" / "manifest.yaml").read_text()
        )
        assert "skill_dependencies" in data

    def test_tool_file_imports_bridge(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "my_skill", str(tmp_path), "agent_based")
        code = (tmp_path / "my_skill" / "src" / "tools" / "main.py").read_text()
        assert "MarketplaceBridge" in code


# ---------------------------------------------------------------------------
# CLI — unknown template rejected
# ---------------------------------------------------------------------------

class TestCLITemplateValidation:

    def test_unknown_template_exits_nonzero(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["skill", "create", "my_skill",
             "--skills-root", str(tmp_path),
             "--template", "magic_template"],
        )
        assert result.exit_code != 0

    def test_template_list_command_runs(self):
        runner = CliRunner()
        result = runner.invoke(main, ["skill", "template", "list"])
        assert result.exit_code == 0
        assert "prompt_only" in result.output
        assert "tool_enabled" in result.output
        assert "agent_based" in result.output