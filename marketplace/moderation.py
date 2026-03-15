# marketplace/moderation.py
"""
marketplace/moderation.py
--------------------------
Moderation queue and skill flagging for the Bazaar marketplace.

Tracks skill status through a lifecycle:
    active → flagged → under_review → approved (back to active) | suspended

Persists state in a JSON file at ``<skills_dir>/.moderation.json``.

Usage:
    from marketplace.moderation import ModerationQueue, FlagReason

    mq = ModerationQueue(skills_dir=Path("marketplace/skills"))
    mq.flag_skill("bad_skill", FlagReason.COMMUNITY_REPORT, reporter="user42",
                  detail="Skill makes unexpected network calls")
    status = mq.get_status("bad_skill")      # SkillStatus.FLAGGED
    mq.start_review("bad_skill", moderator="admin")
    mq.suspend("bad_skill", moderator="admin", reason="Confirmed malicious")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("bazaar")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SkillStatus(str, Enum):
    """Lifecycle status for a marketplace skill."""
    ACTIVE = "active"
    FLAGGED = "flagged"
    UNDER_REVIEW = "under_review"
    SUSPENDED = "suspended"


class FlagReason(str, Enum):
    """Reasons a skill can be flagged."""
    COMMUNITY_REPORT = "community_report"
    EXCESSIVE_PERMISSIONS = "excessive_permissions"
    SUSPICIOUS_CODE = "suspicious_code"
    POLICY_VIOLATION = "policy_violation"
    COPYCAT = "copycat"
    AUTO_SCAN = "auto_scan"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FlagEntry:
    """A single flag report against a skill."""
    reason: str               # FlagReason value
    reporter: str             # who filed the flag ("system" for auto-flags)
    detail: str               # free-text explanation
    created_at: str           # ISO-8601 timestamp

    def to_dict(self) -> dict:
        return {
            "reason": self.reason,
            "reporter": self.reporter,
            "detail": self.detail,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FlagEntry":
        return cls(**d)


@dataclass
class ModerationRecord:
    """Complete moderation state for one skill."""
    skill_name: str
    status: str = SkillStatus.ACTIVE.value
    flags: List[FlagEntry] = field(default_factory=list)
    review_moderator: Optional[str] = None
    review_started_at: Optional[str] = None
    resolution: Optional[str] = None          # "approved" or "suspended"
    resolution_reason: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "status": self.status,
            "flags": [f.to_dict() for f in self.flags],
            "review_moderator": self.review_moderator,
            "review_started_at": self.review_started_at,
            "resolution": self.resolution,
            "resolution_reason": self.resolution_reason,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ModerationRecord":
        flags = [FlagEntry.from_dict(f) for f in d.get("flags", [])]
        return cls(
            skill_name=d["skill_name"],
            status=d.get("status", SkillStatus.ACTIVE.value),
            flags=flags,
            review_moderator=d.get("review_moderator"),
            review_started_at=d.get("review_started_at"),
            resolution=d.get("resolution"),
            resolution_reason=d.get("resolution_reason"),
            resolved_at=d.get("resolved_at"),
            resolved_by=d.get("resolved_by"),
        )


@dataclass
class ModerationResult:
    """Result of a moderation action."""
    success: bool
    skill_name: str
    message: str
    new_status: Optional[str] = None


# ---------------------------------------------------------------------------
# Auto-flag rules
# ---------------------------------------------------------------------------

# Permissions considered high-risk — skills requesting these get auto-flagged
HIGH_RISK_PERMISSIONS = {"execute", "kernel", "raw_socket"}

# Maximum number of permissions before auto-flag triggers
MAX_PERMISSIONS_THRESHOLD = 5


def check_auto_flag_rules(manifest) -> List[FlagEntry]:
    """
    Run automatic checks on a skill manifest and return any triggered flags.

    Rules:
        1. Skill requests high-risk permissions → FlagReason.EXCESSIVE_PERMISSIONS
        2. Skill requests more than MAX_PERMISSIONS_THRESHOLD → FlagReason.EXCESSIVE_PERMISSIONS
        3. Skill name looks like a known reserved/system name → FlagReason.POLICY_VIOLATION

    Args:
        manifest: A SkillManifest object.

    Returns:
        List of FlagEntry objects (empty if no rules triggered).
    """
    now = datetime.now(timezone.utc).isoformat()
    flags: List[FlagEntry] = []

    # Rule 1: High-risk permissions
    risky = set(manifest.permissions) & HIGH_RISK_PERMISSIONS
    if risky:
        flags.append(FlagEntry(
            reason=FlagReason.EXCESSIVE_PERMISSIONS.value,
            reporter="system",
            detail=f"Skill requests high-risk permissions: {sorted(risky)}",
            created_at=now,
        ))

    # Rule 2: Too many permissions
    if len(manifest.permissions) > MAX_PERMISSIONS_THRESHOLD:
        flags.append(FlagEntry(
            reason=FlagReason.EXCESSIVE_PERMISSIONS.value,
            reporter="system",
            detail=f"Skill requests {len(manifest.permissions)} permissions "
                   f"(threshold: {MAX_PERMISSIONS_THRESHOLD})",
            created_at=now,
        ))

    # Rule 3: Reserved names
    reserved = {"system", "admin", "marketplace", "arcturus", "core", "root"}
    if manifest.name.lower() in reserved:
        flags.append(FlagEntry(
            reason=FlagReason.POLICY_VIOLATION.value,
            reporter="system",
            detail=f"Skill name '{manifest.name}' is reserved",
            created_at=now,
        ))

    return flags


# ---------------------------------------------------------------------------
# Moderation Queue
# ---------------------------------------------------------------------------

class ModerationQueue:
    """
    Manages the moderation lifecycle for marketplace skills.

    Persists state in ``<skills_dir>/.moderation.json``.
    """

    MODERATION_FILENAME = ".moderation.json"

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._moderation_path = skills_dir / self.MODERATION_FILENAME
        self._records: Dict[str, ModerationRecord] = {}
        self._load()

    # ---- persistence ----

    def _load(self) -> None:
        """Load moderation records from disk."""
        if self._moderation_path.exists():
            data = json.loads(self._moderation_path.read_text(encoding="utf-8"))
            for name, rec in data.get("skills", {}).items():
                self._records[name] = ModerationRecord.from_dict(rec)
        logger.debug("Moderation queue loaded: %d records", len(self._records))

    def _save(self) -> None:
        """Persist moderation records to disk."""
        self._moderation_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"skills": {n: r.to_dict() for n, r in self._records.items()}}
        self._moderation_path.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    # ---- queries ----

    def get_status(self, name: str) -> Optional[SkillStatus]:
        """Return the moderation status for a skill, or None if not tracked."""
        rec = self._records.get(name)
        if rec is None:
            return None
        return SkillStatus(rec.status)

    def get_record(self, name: str) -> Optional[ModerationRecord]:
        """Return the full moderation record for a skill."""
        return self._records.get(name)

    def is_installable(self, name: str) -> bool:
        """Return True if the skill is allowed to be installed.

        A skill is installable if it has no moderation record (new skill)
        or its status is ACTIVE.
        """
        status = self.get_status(name)
        if status is None:
            return True   # unknown skills are allowed (not yet moderated)
        return status == SkillStatus.ACTIVE

    def list_flagged(self) -> List[ModerationRecord]:
        """Return all skills with FLAGGED status."""
        return [r for r in self._records.values()
                if r.status == SkillStatus.FLAGGED.value]

    def list_under_review(self) -> List[ModerationRecord]:
        """Return all skills currently under review."""
        return [r for r in self._records.values()
                if r.status == SkillStatus.UNDER_REVIEW.value]

    def list_suspended(self) -> List[ModerationRecord]:
        """Return all suspended skills."""
        return [r for r in self._records.values()
                if r.status == SkillStatus.SUSPENDED.value]

    # ---- lifecycle mutations ----

    def flag_skill(
        self,
        name: str,
        reason: FlagReason,
        reporter: str = "system",
        detail: str = "",
    ) -> ModerationResult:
        """
        Flag a skill for moderation review.

        Creates a new moderation record if one doesn't exist.
        Adds the flag to the record and sets status to FLAGGED.
        If the skill is already SUSPENDED, the flag is recorded but
        status remains SUSPENDED.

        Args:
            name:     Skill name.
            reason:   Why the skill is being flagged.
            reporter: Who is filing the flag.
            detail:   Free-text explanation.

        Returns:
            ModerationResult.
        """
        now = datetime.now(timezone.utc).isoformat()
        flag = FlagEntry(
            reason=reason.value,
            reporter=reporter,
            detail=detail,
            created_at=now,
        )

        rec = self._records.get(name)
        if rec is None:
            rec = ModerationRecord(skill_name=name)
            self._records[name] = rec

        rec.flags.append(flag)

        # Don't downgrade a SUSPENDED skill
        if rec.status != SkillStatus.SUSPENDED.value:
            rec.status = SkillStatus.FLAGGED.value

        self._save()
        logger.info("Flagged skill '%s': %s (by %s)", name, reason.value, reporter)
        return ModerationResult(
            success=True,
            skill_name=name,
            message=f"Skill '{name}' flagged for {reason.value}",
            new_status=rec.status,
        )

    def start_review(
        self,
        name: str,
        moderator: str,
    ) -> ModerationResult:
        """
        Begin moderator review of a flagged skill.

        Transitions: FLAGGED → UNDER_REVIEW.

        Args:
            name:      Skill name.
            moderator: Who is performing the review.

        Returns:
            ModerationResult.
        """
        rec = self._records.get(name)
        if rec is None:
            return ModerationResult(
                success=False, skill_name=name,
                message=f"No moderation record for '{name}'",
            )

        if rec.status != SkillStatus.FLAGGED.value:
            return ModerationResult(
                success=False, skill_name=name,
                message=f"Skill '{name}' is {rec.status}, expected 'flagged'",
            )

        rec.status = SkillStatus.UNDER_REVIEW.value
        rec.review_moderator = moderator
        rec.review_started_at = datetime.now(timezone.utc).isoformat()
        self._save()

        logger.info("Review started for '%s' by %s", name, moderator)
        return ModerationResult(
            success=True, skill_name=name,
            message=f"Review started by {moderator}",
            new_status=SkillStatus.UNDER_REVIEW.value,
        )

    def approve(
        self,
        name: str,
        moderator: str,
        reason: str = "Approved after review",
    ) -> ModerationResult:
        """
        Approve a skill after review — returns it to ACTIVE status.

        Transitions: UNDER_REVIEW → ACTIVE.

        Args:
            name:      Skill name.
            moderator: Who approved.
            reason:    Explanation.

        Returns:
            ModerationResult.
        """
        rec = self._records.get(name)
        if rec is None:
            return ModerationResult(
                success=False, skill_name=name,
                message=f"No moderation record for '{name}'",
            )

        if rec.status != SkillStatus.UNDER_REVIEW.value:
            return ModerationResult(
                success=False, skill_name=name,
                message=f"Skill '{name}' is {rec.status}, expected 'under_review'",
            )

        now = datetime.now(timezone.utc).isoformat()
        rec.status = SkillStatus.ACTIVE.value
        rec.resolution = "approved"
        rec.resolution_reason = reason
        rec.resolved_at = now
        rec.resolved_by = moderator
        self._save()

        logger.info("Skill '%s' approved by %s", name, moderator)
        return ModerationResult(
            success=True, skill_name=name,
            message=f"Skill '{name}' approved and restored to active",
            new_status=SkillStatus.ACTIVE.value,
        )

    def suspend(
        self,
        name: str,
        moderator: str,
        reason: str = "Suspended after review",
    ) -> ModerationResult:
        """
        Suspend a skill — permanently blocks it from installation.

        Transitions: UNDER_REVIEW → SUSPENDED.

        Args:
            name:      Skill name.
            moderator: Who suspended.
            reason:    Explanation.

        Returns:
            ModerationResult.
        """
        rec = self._records.get(name)
        if rec is None:
            return ModerationResult(
                success=False, skill_name=name,
                message=f"No moderation record for '{name}'",
            )

        if rec.status != SkillStatus.UNDER_REVIEW.value:
            return ModerationResult(
                success=False, skill_name=name,
                message=f"Skill '{name}' is {rec.status}, expected 'under_review'",
            )

        now = datetime.now(timezone.utc).isoformat()
        rec.status = SkillStatus.SUSPENDED.value
        rec.resolution = "suspended"
        rec.resolution_reason = reason
        rec.resolved_at = now
        rec.resolved_by = moderator
        self._save()

        logger.info("Skill '%s' SUSPENDED by %s: %s", name, moderator, reason)
        return ModerationResult(
            success=True, skill_name=name,
            message=f"Skill '{name}' suspended: {reason}",
            new_status=SkillStatus.SUSPENDED.value,
        )

    def check_and_auto_flag(self, manifest) -> List[FlagEntry]:
        """
        Run auto-flag rules on a manifest and flag if any trigger.

        Called during publish or install to catch obvious problems
        before a human review is needed.

        Args:
            manifest: A SkillManifest object.

        Returns:
            List of FlagEntry objects that were triggered (empty if clean).
        """
        auto_flags = check_auto_flag_rules(manifest)
        for af in auto_flags:
            self.flag_skill(
                name=manifest.name,
                reason=FlagReason(af.reason),
                reporter=af.reporter,
                detail=af.detail,
            )
        return auto_flags

    def remove(self, name: str) -> None:
        """Remove a skill's moderation record entirely."""
        self._records.pop(name, None)
        self._save()
