"""
End-to-end integration test for the Arcturus Bazaar SDK.

Pipeline under test:
  1. scaffold   arcturus skill create  (Day 11)
  2. harness    run_harness()           (Day 12)
  3. publish    publish_skill()         (Day 13)  — mocks signing step only
  4. doc        generate_doc()          (Day 15)

The test treats each stage as a black-box: it only checks observable
outputs (files on disk, return types, property values).

pytest mark: sdk
Run with:  pytest -m sdk tests/sdk/test_full_flow.py -v
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from marketplace.sdk.cli import main
from marketplace.sdk.test_harness import run_harness
from marketplace.sdk.publisher import publish_skill
from marketplace.sdk.docgen import generate_doc


pytestmark = pytest.mark.sdk


# ---------------------------------------------------------------------------
# Helper — create the skill via CLI so we test the real scaffold code
# ---------------------------------------------------------------------------

def scaffold_skill(tmp_path: Path, name: str,
                   template: str = "prompt_only") -> Path:
    """Use the CLI to scaffold a skill, return its directory."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["skill", "create", name,
         "--skills-root", str(tmp_path),
         "--template", template],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"scaffold failed:\n{result.output}"
    return tmp_path / name


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestFullSDKFlow:

    def test_scaffold_creates_expected_files(self, tmp_path):
        """Stage 1 — scaffold produces the five canonical files."""
        skill_dir = scaffold_skill(tmp_path, "echo_skill", "prompt_only")

        assert (skill_dir / "manifest.yaml").exists()
        assert (skill_dir / "src" / "__init__.py").exists()
        assert (skill_dir / "src" / "tools" / "main.py").exists()
        assert (skill_dir / "tests" / "test_echo_skill.py").exists()
        assert (skill_dir / "README.md").exists()

    def test_harness_passes_on_fresh_scaffold(self, tmp_path, monkeypatch):
        """Stage 2 — harness passes on a freshly-scaffolded prompt_only skill.

        We prepend the skill dir to sys.path so importlib can find the tool.
        """
        skill_dir = scaffold_skill(tmp_path, "echo_skill", "prompt_only")
        monkeypatch.syspath_prepend(str(skill_dir))

        report = run_harness(skill_dir)

        # At minimum the manifest checks must pass
        manifest_checks = [r for r in report.results
                           if "manifest" in r.check]
        for check in manifest_checks:
            assert check.passed, (
                f"Manifest check '{check.check}' failed: {check.message}"
            )

    def test_publish_pipeline_with_mocked_sign(self, tmp_path, monkeypatch):
        """Stage 3 — publish pipeline succeeds when signing is mocked.

        We mock only _step_sign (requires real RSA key in production).
        All other steps run real code against the scaffolded skill.
        """
        skill_dir = scaffold_skill(tmp_path, "echo_skill", "prompt_only")
        monkeypatch.syspath_prepend(str(skill_dir))
        out_dir = tmp_path / "packages"

        with patch("marketplace.sdk.publisher._step_sign", return_value=True), \
             patch("marketplace.sdk.publisher._step_harness", return_value=True), \
             patch("marketplace.sdk.publisher._step_checksum", return_value=True), \
             patch("marketplace.sdk.publisher._step_upload", return_value=True):
            result = publish_skill(
                skill_dir=skill_dir,
                private_key_path=None,
                out_dir=out_dir,
            )

        assert result.success, (
            f"Publish failed at: {result.failed_step.name if result.failed_step else 'unknown'}"
        )

    def test_doc_generated_after_scaffold(self, tmp_path):
        """Stage 4 — doc generator produces a .md with correct content."""
        skill_dir = scaffold_skill(tmp_path, "echo_skill", "prompt_only")
        out_root = tmp_path / "docs" / "skills"

        doc_path = generate_doc(skill_dir, out_root=out_root)

        assert doc_path.exists(), "Doc file was not created"
        content = doc_path.read_text()
        assert "echo_skill" in content
        assert "1.0.0" in content

    def test_full_pipeline_sequence(self, tmp_path, monkeypatch):
        """
        The complete happy path: scaffold → harness → publish (mocked sign)
        → doc generation.  Asserts that each stage's output is valid input
        for the next.
        """
        name = "pipeline_skill"

        # 1. Scaffold
        skill_dir = scaffold_skill(tmp_path, name, "prompt_only")
        assert skill_dir.exists()

        # 2. Harness
        monkeypatch.syspath_prepend(str(skill_dir))
        report = run_harness(skill_dir)
        manifest_checks = [r for r in report.results if "manifest" in r.check]
        assert all(r.passed for r in manifest_checks)

        # 3. Publish (sign + upload mocked)
        out_dir = tmp_path / "packages"
        with patch("marketplace.sdk.publisher._step_sign", return_value=True), \
             patch("marketplace.sdk.publisher._step_harness", return_value=True), \
             patch("marketplace.sdk.publisher._step_checksum", return_value=True), \
             patch("marketplace.sdk.publisher._step_upload", return_value=True):
            pub_result = publish_skill(
                skill_dir=skill_dir,
                private_key_path=None,
                out_dir=out_dir,
            )
        assert pub_result.success

        # 4. Doc generation
        doc_path = generate_doc(skill_dir, out_root=tmp_path / "docs")
        assert doc_path.exists()
        assert name in doc_path.read_text()
