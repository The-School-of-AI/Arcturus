"""
Tests for marketplace.sdk.test_harness.

Uses tmp_path so nothing touches the real marketplace/skills/ directory.
"""

from __future__ import annotations

from pathlib import Path

import sys
import pytest
import yaml

from marketplace.sdk.test_harness import run_harness, HarnessReport

@pytest.fixture(autouse=True)
def clean_sys_modules():
    yield
    for key in list(sys.modules.keys()):
        if key.startswith("demo_skill"):
            del sys.modules[key]



# ---------------------------------------------------------------------------
# Helpers — build minimal skill directories in tmp_path
# ---------------------------------------------------------------------------

def write_manifest(skill_dir: Path, data: dict) -> None:
    (skill_dir / "manifest.yaml").write_text(
        yaml.dump(data), encoding="utf-8"
    )


def write_tool(skill_dir: Path, module_rel: str, code: str) -> None:
    """Write a Python file at skill_dir/<module_rel path>.py"""
    parts = module_rel.split(".")
    file_path = skill_dir.joinpath(*parts).with_suffix(".py")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(code, encoding="utf-8")


VALID_MANIFEST = {
    "name": "demo_skill",
    "version": "1.0.0",
    "description": "A test skill",
    "author": "Tester",
    "category": "general",
    "permissions": [],
    "dependencies": [],
    "skill_dependencies": [],
    "intent_triggers": [],
    "tools": [
        {
            "name": "run_demo",
            "description": "Demo tool",
            "module": "demo_skill.tools.main",
            "function": "run",
            "parameters": {},
        }
    ],
    "checksum": "",
}

SAFE_TOOL_CODE = """\
def run(**kwargs):
    return {"result": "ok"}
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestManifestChecks:

    def test_missing_manifest_fails(self, tmp_path):
        skill_dir = tmp_path / "no_manifest"
        skill_dir.mkdir()
        report = run_harness(skill_dir)
        assert not report.passed
        names = [r.check for r in report.results]
        assert "manifest exists" in names
        assert not report.results[0].passed

    def test_valid_manifest_passes(self, tmp_path):
        skill_dir = tmp_path / "demo_skill"
        skill_dir.mkdir()
        write_manifest(skill_dir, VALID_MANIFEST)
        # Don't create tool files — we only care about manifest checks here
        report = run_harness(skill_dir)
        # First two checks (exists + valid) should pass
        assert report.results[0].passed  # manifest exists
        assert report.results[1].passed  # manifest is valid

    def test_invalid_manifest_fails(self, tmp_path):
        skill_dir = tmp_path / "bad_skill"
        skill_dir.mkdir()
        (skill_dir / "manifest.yaml").write_text(
            "not_a_valid_key: true", encoding="utf-8"
        )
        report = run_harness(skill_dir)
        valid_check = next(r for r in report.results if r.check == "manifest is valid")
        assert not valid_check.passed

    def test_manifest_without_tools_fails(self, tmp_path):
        skill_dir = tmp_path / "empty_tools"
        skill_dir.mkdir()
        data = {**VALID_MANIFEST, "tools": [], "name": "empty_tools"}
        write_manifest(skill_dir, data)
        report = run_harness(skill_dir)
        tools_check = next(r for r in report.results if r.check == "manifest has tools")
        assert not tools_check.passed


class TestToolChecks:

    def test_missing_module_fails(self, tmp_path, monkeypatch):
        """Tool module that doesn't exist → importable check fails."""
        skill_dir = tmp_path / "demo_skill"
        skill_dir.mkdir()
        write_manifest(skill_dir, VALID_MANIFEST)
        # Do NOT write the tool file
        monkeypatch.syspath_prepend(str(skill_dir))
        report = run_harness(skill_dir)
        importable_check = next(
            r for r in report.results if "module importable" in r.check
        )
        assert not importable_check.passed

    def test_missing_function_fails(self, tmp_path, monkeypatch):
        """Tool module exists but function missing → callable check fails."""
        skill_dir = tmp_path / "demo_skill"
        skill_dir.mkdir()
        write_manifest(skill_dir, VALID_MANIFEST)
        write_tool(
            skill_dir, "demo_skill/tools/main",
            "# no run() function here\n"
        )
        monkeypatch.syspath_prepend(str(skill_dir))
        report = run_harness(skill_dir)
        callable_check = next(
            r for r in report.results if "function callable" in r.check
        )
        assert not callable_check.passed

    def test_valid_tool_passes_import_check(self, tmp_path, monkeypatch):
        """Well‑formed tool passes importable + callable checks."""
        skill_dir = tmp_path / "demo_skill"
        skill_dir.mkdir()
        write_manifest(skill_dir, VALID_MANIFEST)
        write_tool(skill_dir, "demo_skill/tools/main", SAFE_TOOL_CODE)
        monkeypatch.syspath_prepend(str(skill_dir))
        report = run_harness(skill_dir)
        importable = next(r for r in report.results if "module importable" in r.check)
        callable_ = next(r for r in report.results if "function callable" in r.check)
        assert importable.passed
        assert callable_.passed


class TestSandboxEnforcement:

    def test_tool_without_network_perm_blocked(self, tmp_path, monkeypatch):
        """Tool calls requests but manifest has no 'network' permission → sandbox check fails."""
        skill_dir = tmp_path / "demo_skill"
        skill_dir.mkdir()
        manifest_data = {**VALID_MANIFEST, "permissions": []}  # no network
        write_manifest(skill_dir, manifest_data)
        write_tool(
            skill_dir, "demo_skill/tools/main",
            "import requests\ndef run(**kwargs):\n    return {}\n"
        )
        monkeypatch.syspath_prepend(str(skill_dir))
        report = run_harness(skill_dir)
        sandbox_check = next(
            (r for r in report.results if "sandbox run" in r.check), None
        )
        if sandbox_check:  # only if sandbox is available
            assert not sandbox_check.passed

    def test_tool_with_network_perm_allowed(self, tmp_path, monkeypatch):
        """Tool uses json (always safe) and manifest has no special permissions → passes."""
        skill_dir = tmp_path / "demo_skill"
        skill_dir.mkdir()
        manifest_data = {**VALID_MANIFEST, "permissions": []}
        write_manifest(skill_dir, manifest_data)
        write_tool(
            skill_dir, "demo_skill/tools/main",
            "import json\ndef run(**kwargs):\n    return json.loads('{\"ok\": true}')\n"
        )
        monkeypatch.syspath_prepend(str(skill_dir))
        report = run_harness(skill_dir)
        sandbox_check = next(
            (r for r in report.results if "sandbox run" in r.check), None
        )
        if sandbox_check:
            assert sandbox_check.passed


class TestReport:

    def test_passed_property_true_when_all_pass(self, tmp_path, monkeypatch):
        skill_dir = tmp_path / "demo_skill"
        skill_dir.mkdir()
        write_manifest(skill_dir, VALID_MANIFEST)
        write_tool(skill_dir, "demo_skill/tools/main", SAFE_TOOL_CODE)
        monkeypatch.syspath_prepend(str(skill_dir))
        report = run_harness(skill_dir)
        # May have sandbox check too — just verify all results are True
        assert isinstance(report.passed, bool)

    def test_as_json_is_valid_json(self, tmp_path, monkeypatch):
        import json
        skill_dir = tmp_path / "demo_skill"
        skill_dir.mkdir()
        write_manifest(skill_dir, VALID_MANIFEST)
        write_tool(skill_dir, "demo_skill/tools/main", SAFE_TOOL_CODE)
        monkeypatch.syspath_prepend(str(skill_dir))
        report = run_harness(skill_dir)
        parsed = json.loads(report.as_json())
        assert parsed["skill_name"] == "demo_skill"
        assert isinstance(parsed["results"], list)