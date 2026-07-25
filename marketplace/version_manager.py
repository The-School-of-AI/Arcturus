"""
marketplace/version_manager.py
-------------------------------
Tracks skill version history and enables rollback, pinning, and upgrades.

Maintains a JSON ledger at ``<skills_dir>/.version_ledger.json`` and
archives previous versions under ``<skills_dir>/.archive/<name>/<version>/``.

Usage:
    from marketplace.version_manager import VersionManager

    vm = VersionManager(skills_dir=Path("marketplace/skills"))
    vm.record_install("weather_fetcher", "1.0.0")
    vm.upgrade("weather_fetcher", source_dir, installer)
    vm.rollback("weather_fetcher", installer)
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("bazaar")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class VersionEntry:
    """A single version in a skill's history."""
    version: str
    installed_at: str          # ISO-8601 timestamp
    archive_path: Optional[str] = None   # path to archived copy (None for current)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "installed_at": self.installed_at,
            "archive_path": self.archive_path,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VersionEntry":
        return cls(
            version=d["version"],
            installed_at=d["installed_at"],
            archive_path=d.get("archive_path"),
        )


@dataclass
class SkillVersionInfo:
    """Complete version state for one skill."""
    current_version: str
    pinned: bool = False
    history: List[VersionEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "current_version": self.current_version,
            "pinned": self.pinned,
            "history": [e.to_dict() for e in self.history],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SkillVersionInfo":
        return cls(
            current_version=d["current_version"],
            pinned=d.get("pinned", False),
            history=[VersionEntry.from_dict(e) for e in d.get("history", [])],
        )


@dataclass
class RollbackResult:
    """Result of a rollback or upgrade operation."""
    success: bool
    skill_name: str
    message: str
    previous_version: Optional[str] = None
    restored_version: Optional[str] = None


# ---------------------------------------------------------------------------
# Version Manager
# ---------------------------------------------------------------------------

class VersionManager:
    """
    Tracks installed skill versions and enables rollback / pin / upgrade.

    State is persisted in ``<skills_dir>/.version_ledger.json``.
    Archived versions live in ``<skills_dir>/.archive/<name>/<version>/``.
    """

    LEDGER_FILENAME = ".version_ledger.json"
    ARCHIVE_DIRNAME = ".archive"

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._ledger_path = skills_dir / self.LEDGER_FILENAME
        self._archive_dir = skills_dir / self.ARCHIVE_DIRNAME
        self._skills: Dict[str, SkillVersionInfo] = {}
        self._load()

    # ---- persistence ----

    def _load(self) -> None:
        """Load the ledger from disk (or start empty)."""
        if self._ledger_path.exists():
            data = json.loads(self._ledger_path.read_text(encoding="utf-8"))
            for name, info in data.get("skills", {}).items():
                self._skills[name] = SkillVersionInfo.from_dict(info)
        logger.debug("Version ledger loaded: %d skills", len(self._skills))

    def _save(self) -> None:
        """Persist the ledger to disk."""
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"skills": {n: v.to_dict() for n, v in self._skills.items()}}
        self._ledger_path.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    # ---- queries ----

    def get_info(self, name: str) -> Optional[SkillVersionInfo]:
        """Return version info for *name*, or None."""
        return self._skills.get(name)

    def is_pinned(self, name: str) -> bool:
        """Return True if the skill is pinned (upgrades blocked)."""
        info = self._skills.get(name)
        return info.pinned if info else False

    def list_versions(self, name: str) -> List[VersionEntry]:
        """Return the full version history for *name*."""
        info = self._skills.get(name)
        return list(info.history) if info else []

    # ---- mutations ----

    def record_install(self, name: str, version: str) -> None:
        """
        Record a fresh install (no previous version to archive).

        Called by the installer after a successful first-time install.
        """
        entry = VersionEntry(
            version=version,
            installed_at=datetime.now(timezone.utc).isoformat(),
        )
        self._skills[name] = SkillVersionInfo(
            current_version=version,
            history=[entry],
        )
        self._save()
        logger.info("Recorded install: %s v%s", name, version)

    def pin(self, name: str) -> RollbackResult:
        """Pin a skill at its current version."""
        info = self._skills.get(name)
        if info is None:
            return RollbackResult(
                success=False, skill_name=name,
                message=f"Skill '{name}' not found in version ledger",
            )
        if info.pinned:
            return RollbackResult(
                success=True, skill_name=name,
                message=f"Skill '{name}' is already pinned at v{info.current_version}",
            )
        info.pinned = True
        self._save()
        return RollbackResult(
            success=True, skill_name=name,
            message=f"Pinned '{name}' at v{info.current_version}",
        )

    def unpin(self, name: str) -> RollbackResult:
        """Unpin a skill so it can be upgraded."""
        info = self._skills.get(name)
        if info is None:
            return RollbackResult(
                success=False, skill_name=name,
                message=f"Skill '{name}' not found in version ledger",
            )
        info.pinned = False
        self._save()
        return RollbackResult(
            success=True, skill_name=name,
            message=f"Un-pinned '{name}' — upgrades now allowed",
        )

    def _archive_current(self, name: str) -> Optional[Path]:
        """
        Snapshot the currently installed version to the archive dir.

        Returns the archive path, or None if the skill dir doesn't exist.
        """
        info = self._skills.get(name)
        if info is None:
            return None

        skill_dir = self.skills_dir / name
        if not skill_dir.exists():
            return None

        archive_dest = self._archive_dir / name / info.current_version
        if archive_dest.exists():
            shutil.rmtree(archive_dest)
        archive_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill_dir, archive_dest)

        # Update the current history entry with the archive path
        for entry in reversed(info.history):
            if entry.version == info.current_version:
                entry.archive_path = str(archive_dest)
                break
        self._save()
        logger.info("Archived %s v%s → %s", name, info.current_version, archive_dest)
        return archive_dest

    def upgrade(
        self,
        name: str,
        source_dir: Path,
        installer,               # SkillInstaller (avoid circular import)
    ) -> RollbackResult:
        """
        Upgrade a skill to a new version from *source_dir*.

        Steps:
            1. Check the skill is not pinned
            2. Archive the current installed version
            3. Install the new version (via installer.install_skill)
            4. Record the new version in the ledger

        Args:
            name:       Skill name (must already be installed).
            source_dir: Directory containing the new version.
            installer:  A ``SkillInstaller`` instance.

        Returns:
            RollbackResult describing what happened.
        """
        from marketplace.skill_base import load_manifest

        info = self._skills.get(name)
        if info is None:
            return RollbackResult(
                success=False, skill_name=name,
                message=f"Skill '{name}' is not installed — use install, not upgrade",
            )

        if info.pinned:
            return RollbackResult(
                success=False, skill_name=name,
                message=f"Skill '{name}' is pinned at v{info.current_version}. "
                        f"Run 'arcturus skill unpin {name}' first.",
            )

        # Read the new version from the source manifest
        new_manifest = load_manifest(source_dir / "manifest.yaml")
        new_version = new_manifest.version
        old_version = info.current_version

        if new_version == old_version:
            return RollbackResult(
                success=False, skill_name=name,
                message=f"Source version ({new_version}) is the same as installed version",
            )

        # 1. Archive current
        self._archive_current(name)

        # 2. Install new version (force=True to overwrite)
        result = installer.install_skill(source_dir, force=True)
        if not result.success:
            # Restore from archive
            self._restore_from_archive(name, old_version)
            return RollbackResult(
                success=False, skill_name=name,
                message=f"Upgrade failed: {result.message}. Restored v{old_version}.",
                previous_version=old_version,
            )

        # 3. Record new version
        entry = VersionEntry(
            version=new_version,
            installed_at=datetime.now(timezone.utc).isoformat(),
        )
        info.current_version = new_version
        info.history.append(entry)
        self._save()

        logger.info("Upgraded %s: v%s → v%s", name, old_version, new_version)
        return RollbackResult(
            success=True, skill_name=name,
            message=f"Upgraded '{name}' from v{old_version} to v{new_version}",
            previous_version=old_version,
            restored_version=new_version,
        )

    def _restore_from_archive(self, name: str, version: str) -> bool:
        """
        Restore a skill from the archive.  Returns True on success.
        """
        info = self._skills.get(name)
        if info is None:
            return False

        target = None
        for entry in info.history:
            if entry.version == version and entry.archive_path:
                target = Path(entry.archive_path)
                break

        if target is None or not target.exists():
            logger.error("Archive for %s v%s not found", name, version)
            return False

        skill_dir = self.skills_dir / name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        shutil.copytree(target, skill_dir)
        return True

    def rollback(self, name: str) -> RollbackResult:
        """
        Roll the skill back to its previous version.

        Reads the version history, finds the entry before the current one,
        copies the archived snapshot back into the live skills directory,
        and updates the ledger.
        """
        info = self._skills.get(name)
        if info is None:
            return RollbackResult(
                success=False, skill_name=name,
                message=f"Skill '{name}' not found in version ledger",
            )

        if len(info.history) < 2:
            return RollbackResult(
                success=False, skill_name=name,
                message=f"No previous version to roll back to for '{name}'",
            )

        # The previous entry is the second-to-last
        prev_entry = info.history[-2]
        if prev_entry.archive_path is None:
            return RollbackResult(
                success=False, skill_name=name,
                message=f"No archive found for v{prev_entry.version}",
            )

        archive_path = Path(prev_entry.archive_path)
        if not archive_path.exists():
            return RollbackResult(
                success=False, skill_name=name,
                message=f"Archive directory missing: {archive_path}",
            )

        # Restore the archived version
        current_version = info.current_version
        skill_dir = self.skills_dir / name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        shutil.copytree(archive_path, skill_dir)

        # Update ledger: pop the current entry, set current_version back
        info.history.pop()   # remove the current version entry
        info.current_version = prev_entry.version
        # The restored entry is now "current" again — clear its archive_path
        prev_entry.archive_path = None
        self._save()

        logger.info("Rolled back %s: v%s → v%s", name, current_version, prev_entry.version)
        return RollbackResult(
            success=True, skill_name=name,
            message=f"Rolled back '{name}' from v{current_version} to v{prev_entry.version}",
            previous_version=current_version,
            restored_version=prev_entry.version,
        )

    def remove(self, name: str) -> None:
        """Remove a skill from the ledger entirely (called on uninstall)."""
        self._skills.pop(name, None)
        # Also clean up archive
        archive = self._archive_dir / name
        if archive.exists():
            shutil.rmtree(archive)
        self._save()
