"""
Unit tests for marketplace.version_manager.

Covers:
  - record_install() creates a ledger entry
  - pin() / unpin() toggle the pinned flag
  - upgrade() archives old version and installs new one
  - upgrade() is blocked when skill is pinned
  - rollback() restores the previous version from archive
  - rollback() fails gracefully when no history exists
  - remove() cleans up ledger and archive
  - Ledger persists across VersionManager instances (disk round-trip)
  - CLI commands (rollback, pin, unpin) exit correctly
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from click.testing import CliRunner

from marketplace.version_manager import (
    VersionManager,
    VersionEntry,
    SkillVersionInfo,
    RollbackResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_skill_dir(base: Path, name: str, version: str = "1.0.0") -> Path:
    """Create a minimal skill directory with a manifest."""
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "version": version,
        "description": f"Test skill {name}",
        "author": "tester",
        "category": "general",
        "permissions": [],
        "dependencies": [],
        "skill_dependencies": [],
        "intent_triggers": [],
        "tools": [],
        "checksum": "",
    }
    (skill_dir / "manifest.yaml").write_text(yaml.dump(manifest))
    (skill_dir / "main.py").write_text(f"# {name} v{version}\n")
    return skill_dir


def make_mock_installer(success: bool = True) -> MagicMock:
    """Return a mock SkillInstaller that succeeds or fails."""
    installer = MagicMock()
    result = MagicMock()
    result.success = success
    result.message = "ok" if success else "install failed"
    installer.install_skill.return_value = result
    return installer


# ---------------------------------------------------------------------------
# Tests — VersionEntry / SkillVersionInfo serialization
# ---------------------------------------------------------------------------

class TestSerialization:

    def test_version_entry_round_trip(self):
        entry = VersionEntry(version="1.0.0", installed_at="2026-01-01T00:00:00+00:00")
        d = entry.to_dict()
        restored = VersionEntry.from_dict(d)
        assert restored.version == "1.0.0"
        assert restored.archive_path is None

    def test_skill_version_info_round_trip(self):
        info = SkillVersionInfo(
            current_version="2.0.0",
            pinned=True,
            history=[
                VersionEntry(version="1.0.0", installed_at="2026-01-01",
                             archive_path="/archive/s/1.0.0"),
                VersionEntry(version="2.0.0", installed_at="2026-01-02"),
            ],
        )
        d = info.to_dict()
        restored = SkillVersionInfo.from_dict(d)
        assert restored.current_version == "2.0.0"
        assert restored.pinned is True
        assert len(restored.history) == 2


# ---------------------------------------------------------------------------
# Tests — VersionManager core operations
# ---------------------------------------------------------------------------

class TestRecordInstall:

    def test_record_creates_entry(self, tmp_path):
        vm = VersionManager(skills_dir=tmp_path)
        vm.record_install("my_skill", "1.0.0")
        info = vm.get_info("my_skill")
        assert info is not None
        assert info.current_version == "1.0.0"
        assert len(info.history) == 1

    def test_record_persists_to_disk(self, tmp_path):
        vm1 = VersionManager(skills_dir=tmp_path)
        vm1.record_install("my_skill", "1.0.0")

        # New instance should load from disk
        vm2 = VersionManager(skills_dir=tmp_path)
        info = vm2.get_info("my_skill")
        assert info is not None
        assert info.current_version == "1.0.0"

    def test_record_not_pinned_by_default(self, tmp_path):
        vm = VersionManager(skills_dir=tmp_path)
        vm.record_install("my_skill", "1.0.0")
        assert vm.is_pinned("my_skill") is False


class TestPinUnpin:

    def test_pin_sets_flag(self, tmp_path):
        vm = VersionManager(skills_dir=tmp_path)
        vm.record_install("my_skill", "1.0.0")

        result = vm.pin("my_skill")
        assert result.success is True
        assert vm.is_pinned("my_skill") is True

    def test_pin_idempotent(self, tmp_path):
        vm = VersionManager(skills_dir=tmp_path)
        vm.record_install("my_skill", "1.0.0")
        vm.pin("my_skill")

        result = vm.pin("my_skill")
        assert result.success is True
        assert "already pinned" in result.message

    def test_unpin_clears_flag(self, tmp_path):
        vm = VersionManager(skills_dir=tmp_path)
        vm.record_install("my_skill", "1.0.0")
        vm.pin("my_skill")

        result = vm.unpin("my_skill")
        assert result.success is True
        assert vm.is_pinned("my_skill") is False

    def test_pin_unknown_skill_fails(self, tmp_path):
        vm = VersionManager(skills_dir=tmp_path)
        result = vm.pin("ghost")
        assert result.success is False
        assert "not found" in result.message


class TestUpgrade:

    def test_upgrade_archives_old_and_installs_new(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Simulate v1.0.0 already installed
        make_skill_dir(skills_dir, "my_skill", "1.0.0")
        vm = VersionManager(skills_dir=skills_dir)
        vm.record_install("my_skill", "1.0.0")

        # Prepare v2.0.0 source
        source = make_skill_dir(tmp_path / "source", "my_skill", "2.0.0")
        installer = make_mock_installer(success=True)

        result = vm.upgrade("my_skill", source, installer)

        assert result.success is True
        assert result.previous_version == "1.0.0"
        assert result.restored_version == "2.0.0"

        info = vm.get_info("my_skill")
        assert info.current_version == "2.0.0"
        assert len(info.history) == 2

        # Archive should exist
        archive_path = Path(info.history[0].archive_path)
        assert archive_path.exists()

    def test_upgrade_blocked_when_pinned(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        make_skill_dir(skills_dir, "my_skill", "1.0.0")

        vm = VersionManager(skills_dir=skills_dir)
        vm.record_install("my_skill", "1.0.0")
        vm.pin("my_skill")

        source = make_skill_dir(tmp_path / "source", "my_skill", "2.0.0")
        installer = make_mock_installer()

        result = vm.upgrade("my_skill", source, installer)
        assert result.success is False
        assert "pinned" in result.message

    def test_upgrade_same_version_is_rejected(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        make_skill_dir(skills_dir, "my_skill", "1.0.0")

        vm = VersionManager(skills_dir=skills_dir)
        vm.record_install("my_skill", "1.0.0")

        source = make_skill_dir(tmp_path / "source", "my_skill", "1.0.0")
        installer = make_mock_installer()

        result = vm.upgrade("my_skill", source, installer)
        assert result.success is False
        assert "same" in result.message.lower()

    def test_upgrade_not_installed_fails(self, tmp_path):
        vm = VersionManager(skills_dir=tmp_path)
        source = make_skill_dir(tmp_path / "source", "ghost", "1.0.0")
        installer = make_mock_installer()

        result = vm.upgrade("ghost", source, installer)
        assert result.success is False
        assert "not installed" in result.message.lower()

    def test_upgrade_failure_restores_archive(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        make_skill_dir(skills_dir, "my_skill", "1.0.0")

        vm = VersionManager(skills_dir=skills_dir)
        vm.record_install("my_skill", "1.0.0")

        source = make_skill_dir(tmp_path / "source", "my_skill", "2.0.0")
        installer = make_mock_installer(success=False)

        result = vm.upgrade("my_skill", source, installer)
        assert result.success is False
        assert "Restored" in result.message

        # Skill dir should still contain v1.0.0 contents
        assert (skills_dir / "my_skill" / "main.py").exists()


class TestRollback:

    def test_rollback_restores_previous_version(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Install v1.0.0, upgrade to v2.0.0
        make_skill_dir(skills_dir, "my_skill", "1.0.0")
        vm = VersionManager(skills_dir=skills_dir)
        vm.record_install("my_skill", "1.0.0")

        source = make_skill_dir(tmp_path / "source", "my_skill", "2.0.0")
        installer = make_mock_installer(success=True)
        vm.upgrade("my_skill", source, installer)

        # Rollback
        result = vm.rollback("my_skill")
        assert result.success is True
        assert result.previous_version == "2.0.0"
        assert result.restored_version == "1.0.0"

        info = vm.get_info("my_skill")
        assert info.current_version == "1.0.0"
        assert len(info.history) == 1

    def test_rollback_no_history_fails(self, tmp_path):
        vm = VersionManager(skills_dir=tmp_path)
        vm.record_install("my_skill", "1.0.0")

        result = vm.rollback("my_skill")
        assert result.success is False
        assert "no previous" in result.message.lower()

    def test_rollback_unknown_skill_fails(self, tmp_path):
        vm = VersionManager(skills_dir=tmp_path)
        result = vm.rollback("nonexistent")
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_rollback_restores_files_on_disk(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # Install v1.0.0
        v1_dir = make_skill_dir(skills_dir, "my_skill", "1.0.0")
        (v1_dir / "unique_v1_file.txt").write_text("v1 marker")

        vm = VersionManager(skills_dir=skills_dir)
        vm.record_install("my_skill", "1.0.0")

        # Upgrade to v2.0.0
        source = make_skill_dir(tmp_path / "source", "my_skill", "2.0.0")
        installer = make_mock_installer(success=True)
        vm.upgrade("my_skill", source, installer)

        # Rollback — the v1 marker file should be restored
        vm.rollback("my_skill")
        assert (skills_dir / "my_skill" / "unique_v1_file.txt").exists()
        assert (skills_dir / "my_skill" / "unique_v1_file.txt").read_text() == "v1 marker"


class TestRemove:

    def test_remove_cleans_ledger(self, tmp_path):
        vm = VersionManager(skills_dir=tmp_path)
        vm.record_install("my_skill", "1.0.0")
        vm.remove("my_skill")
        assert vm.get_info("my_skill") is None

    def test_remove_cleans_archive(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        make_skill_dir(skills_dir, "my_skill", "1.0.0")

        vm = VersionManager(skills_dir=skills_dir)
        vm.record_install("my_skill", "1.0.0")
        # Simulate archive creation
        vm._archive_current("my_skill")

        archive_dir = skills_dir / ".archive" / "my_skill"
        assert archive_dir.exists()

        vm.remove("my_skill")
        assert not archive_dir.exists()

    def test_remove_unknown_skill_is_noop(self, tmp_path):
        vm = VersionManager(skills_dir=tmp_path)
        vm.remove("nonexistent")  # should not raise


class TestListVersions:

    def test_list_versions_returns_history(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        make_skill_dir(skills_dir, "my_skill", "1.0.0")

        vm = VersionManager(skills_dir=skills_dir)
        vm.record_install("my_skill", "1.0.0")

        source = make_skill_dir(tmp_path / "source", "my_skill", "2.0.0")
        vm.upgrade("my_skill", source, make_mock_installer())

        versions = vm.list_versions("my_skill")
        assert len(versions) == 2
        assert versions[0].version == "1.0.0"
        assert versions[1].version == "2.0.0"

    def test_list_versions_unknown_skill_empty(self, tmp_path):
        vm = VersionManager(skills_dir=tmp_path)
        assert vm.list_versions("ghost") == []


# ---------------------------------------------------------------------------
# Tests — CLI commands
# ---------------------------------------------------------------------------

class TestCLI:

    def test_pin_command_exits_zero(self, tmp_path):
        from marketplace.sdk.cli import main

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        vm = VersionManager(skills_dir=skills_dir)
        vm.record_install("my_skill", "1.0.0")

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["skill", "pin", "my_skill", "--skills-root", str(skills_dir)],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "📌" in result.output or "Pinned" in result.output

    def test_rollback_no_history_exits_nonzero(self, tmp_path):
        from marketplace.sdk.cli import main

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        vm = VersionManager(skills_dir=skills_dir)
        vm.record_install("my_skill", "1.0.0")

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["skill", "rollback", "my_skill", "--skills-root", str(skills_dir)],
        )
        assert result.exit_code != 0
