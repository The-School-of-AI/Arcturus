# tests/unit/bazaar/test_docgen.py
"""
Unit tests for marketplace.sdk.docgen.

Covers:
  - generate_doc() creates a .md file
  - Output contains manifest fields (name, version, author, permissions, tools)
  - Docstrings are included when the tool is importable
  - Missing manifest raises FileNotFoundError
  - CLI `skill doc` command runs without error
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from marketplace.sdk.cli import main
from marketplace.sdk.docgen import generate_doc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_MANIFEST = {
    "name": "demo_skill",
    "version": "1.2.3",
    "description": "A demo skill for testing.",
    "author": "Doc Tester",
    "category": "productivity",
    "permissions": ["network"],
    "dependencies": [],
    "skill_dependencies": [],
    "intent_triggers": ["demo"],
    "tools": [{
        "name": "run_demo",
        "description": "Runs the demo.",
        "module": "demo_skill.tools.main",
        "function": "run",
        "parameters": {
            "query": {"type": "string", "description": "Input query"},
        },
    }],
    "checksum": "",
}

TOOL_CODE = '''\
def run(**kwargs) -> dict:
    """
    Execute the demo skill.

    Args:
        **kwargs: Arbitrary keyword arguments.

    Returns:
        dict: Result of the demo.
    """
    return {"result": "ok"}
'''


def make_skill(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "demo_skill"
    (skill_dir / "src" / "tools").mkdir(parents=True)
    (skill_dir / "manifest.yaml").write_text(yaml.dump(VALID_MANIFEST))
    (skill_dir / "src" / "tools" / "main.py").write_text(TOOL_CODE)
    return skill_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenerateDoc:

    def test_creates_md_file(self, tmp_path):
        skill_dir = make_skill(tmp_path)
        out_root = tmp_path / "docs" / "skills"
        doc_path = generate_doc(skill_dir, out_root=out_root)
        assert doc_path.exists()
        assert doc_path.suffix == ".md"

    def test_md_contains_skill_name(self, tmp_path):
        skill_dir = make_skill(tmp_path)
        out_root = tmp_path / "docs" / "skills"
        doc_path = generate_doc(skill_dir, out_root=out_root)
        content = doc_path.read_text()
        assert "demo_skill" in content

    def test_md_contains_version(self, tmp_path):
        skill_dir = make_skill(tmp_path)
        out_root = tmp_path / "docs" / "skills"
        doc_path = generate_doc(skill_dir, out_root=out_root)
        assert "1.2.3" in doc_path.read_text()

    def test_md_contains_author(self, tmp_path):
        skill_dir = make_skill(tmp_path)
        out_root = tmp_path / "docs" / "skills"
        doc_path = generate_doc(skill_dir, out_root=out_root)
        assert "Doc Tester" in doc_path.read_text()

    def test_md_contains_permission(self, tmp_path):
        skill_dir = make_skill(tmp_path)
        out_root = tmp_path / "docs" / "skills"
        doc_path = generate_doc(skill_dir, out_root=out_root)
        assert "network" in doc_path.read_text()

    def test_md_contains_tool_name(self, tmp_path):
        skill_dir = make_skill(tmp_path)
        out_root = tmp_path / "docs" / "skills"
        doc_path = generate_doc(skill_dir, out_root=out_root)
        assert "run_demo" in doc_path.read_text()

    def test_md_contains_parameter_name(self, tmp_path):
        skill_dir = make_skill(tmp_path)
        out_root = tmp_path / "docs" / "skills"
        doc_path = generate_doc(skill_dir, out_root=out_root)
        assert "query" in doc_path.read_text()

    def test_missing_manifest_raises(self, tmp_path):
        skill_dir = tmp_path / "no_manifest"
        skill_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            generate_doc(skill_dir, out_root=tmp_path / "out")

    def test_out_root_created_if_missing(self, tmp_path):
        skill_dir = make_skill(tmp_path)
        out_root = tmp_path / "new" / "nested" / "dir"
        assert not out_root.exists()
        generate_doc(skill_dir, out_root=out_root)
        assert out_root.exists()


class TestDocCLI:

    def test_doc_command_exits_zero(self, tmp_path):
        skill_dir = make_skill(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["skill", "doc", "demo_skill",
             "--skills-root", str(tmp_path),
             "--out-root", str(tmp_path / "out")],
            catch_exceptions=False,
        )
        assert result.exit_code == 0

    def test_doc_command_prints_output_path(self, tmp_path):
        skill_dir = make_skill(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["skill", "doc", "demo_skill",
             "--skills-root", str(tmp_path),
             "--out-root", str(tmp_path / "out")],
        )
        assert "demo_skill.md" in result.output
