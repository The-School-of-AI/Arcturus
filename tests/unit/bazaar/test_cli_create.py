"""
Tests for `marketplace.sdk.cli skill create`.

Uses tmp_path (pytest built‑in) so nothing is written to the real
marketplace/skills/ directory.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from marketplace.sdk.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def invoke_create(runner: CliRunner, name: str,
                  skills_root: str, extra_args: list[str] | None = None):
    """Invoke `arcturus skill create <name>` with a custom --skills-root."""
    args = ["skill", "create", name, "--skills-root", skills_root]
    if extra_args:
        args.extend(extra_args)
    return runner.invoke(main, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScaffold:
    """Happy‑path: valid name produces the expected files."""

    def test_exit_code_zero(self, tmp_path):
        runner = CliRunner()
        result = invoke_create(runner, "demo_skill", str(tmp_path))
        assert result.exit_code == 0, result.output

    def test_manifest_created(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "demo_skill", str(tmp_path))
        assert (tmp_path / "demo_skill" / "manifest.yaml").exists()

    def test_manifest_contains_name(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "demo_skill", str(tmp_path))
        content = (tmp_path / "demo_skill" / "manifest.yaml").read_text()
        assert "name: demo_skill" in content

    def test_src_init_created(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "demo_skill", str(tmp_path))
        assert (tmp_path / "demo_skill" / "src" / "__init__.py").exists()

    def test_tools_main_created(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "demo_skill", str(tmp_path))
        assert (tmp_path / "demo_skill" / "src" / "tools" / "main.py").exists()

    def test_test_file_created(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "demo_skill", str(tmp_path))
        assert (tmp_path / "demo_skill" / "tests" / "test_demo_skill.py").exists()

    def test_readme_created(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "demo_skill", str(tmp_path))
        assert (tmp_path / "demo_skill" / "README.md").exists()

    def test_author_embedded_in_manifest(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "demo_skill", str(tmp_path),
                      extra_args=["--author", "Jane Doe"])
        content = (tmp_path / "demo_skill" / "manifest.yaml").read_text()
        assert "Jane Doe" in content


class TestValidation:
    """Invalid inputs are rejected with a non‑zero exit code."""

    @pytest.mark.parametrize("bad_name", [
        "MySkill",          # uppercase
        "my-skill",         # hyphens
        "my skill",         # space
        "123skill",         # starts with digit
        "",                 # empty
    ])
    def test_invalid_name_rejected(self, tmp_path, bad_name):
        runner = CliRunner()
        result = invoke_create(runner, bad_name, str(tmp_path))
        assert result.exit_code != 0

    def test_duplicate_name_rejected(self, tmp_path):
        runner = CliRunner()
        invoke_create(runner, "demo_skill", str(tmp_path))   # first time ok
        result = invoke_create(runner, "demo_skill", str(tmp_path))  # duplicate
        assert result.exit_code != 0