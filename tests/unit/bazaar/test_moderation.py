"""
Unit tests for marketplace.moderation.

Covers:
  - FlagEntry / ModerationRecord serialization round-trips
  - flag_skill() creates record and sets FLAGGED status
  - start_review() transitions FLAGGED → UNDER_REVIEW
  - approve() transitions UNDER_REVIEW → ACTIVE
  - suspend() transitions UNDER_REVIEW → SUSPENDED
  - Invalid transitions are rejected
  - is_installable() blocks flagged and suspended skills
  - Auto-flag rules detect high-risk permissions
  - Auto-flag rules detect excessive permissions
  - Auto-flag rules detect reserved names
  - list_flagged() / list_suspended() filter correctly
  - Moderation record persists across instances (disk round-trip)
  - Flagging an already-suspended skill records flag but keeps status
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from marketplace.moderation import (
    ModerationQueue,
    ModerationRecord,
    FlagEntry,
    FlagReason,
    SkillStatus,
    ModerationResult,
    check_auto_flag_rules,
    HIGH_RISK_PERMISSIONS,
    MAX_PERMISSIONS_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_manifest(
    name: str = "test_skill",
    permissions: list = None,
) -> MagicMock:
    """Create a mock SkillManifest."""
    m = MagicMock()
    m.name = name
    m.permissions = permissions or []
    return m


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:

    def test_flag_entry_round_trip(self):
        entry = FlagEntry(
            reason="community_report",
            reporter="user42",
            detail="spam",
            created_at="2026-01-01T00:00:00+00:00",
        )
        restored = FlagEntry.from_dict(entry.to_dict())
        assert restored.reason == "community_report"
        assert restored.reporter == "user42"

    def test_moderation_record_round_trip(self):
        rec = ModerationRecord(
            skill_name="bad_skill",
            status=SkillStatus.FLAGGED.value,
            flags=[FlagEntry(
                reason="suspicious_code",
                reporter="system",
                detail="obfuscated",
                created_at="2026-01-01",
            )],
        )
        restored = ModerationRecord.from_dict(rec.to_dict())
        assert restored.skill_name == "bad_skill"
        assert restored.status == "flagged"
        assert len(restored.flags) == 1


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------

class TestFlagSkill:

    def test_flag_creates_record(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        result = mq.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT,
                               reporter="user1", detail="broken")
        assert result.success is True
        assert mq.get_status("my_skill") == SkillStatus.FLAGGED

    def test_flag_adds_to_existing_record(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT,
                      reporter="user1", detail="first")
        mq.flag_skill("my_skill", FlagReason.SUSPICIOUS_CODE,
                      reporter="user2", detail="second")

        rec = mq.get_record("my_skill")
        assert len(rec.flags) == 2

    def test_flag_suspended_skill_keeps_suspended(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT, reporter="u1")
        mq.start_review("my_skill", moderator="admin")
        mq.suspend("my_skill", moderator="admin", reason="bad")

        # Flag again — status should remain SUSPENDED
        mq.flag_skill("my_skill", FlagReason.SUSPICIOUS_CODE, reporter="u2")
        assert mq.get_status("my_skill") == SkillStatus.SUSPENDED


class TestStartReview:

    def test_flagged_to_under_review(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT, reporter="u1")

        result = mq.start_review("my_skill", moderator="admin")
        assert result.success is True
        assert mq.get_status("my_skill") == SkillStatus.UNDER_REVIEW

    def test_review_records_moderator(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT, reporter="u1")
        mq.start_review("my_skill", moderator="alice")

        rec = mq.get_record("my_skill")
        assert rec.review_moderator == "alice"
        assert rec.review_started_at is not None

    def test_review_non_flagged_fails(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        result = mq.start_review("ghost", moderator="admin")
        assert result.success is False


class TestApprove:

    def test_approve_restores_active(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT, reporter="u1")
        mq.start_review("my_skill", moderator="admin")

        result = mq.approve("my_skill", moderator="admin", reason="false alarm")
        assert result.success is True
        assert mq.get_status("my_skill") == SkillStatus.ACTIVE

    def test_approve_records_resolution(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT, reporter="u1")
        mq.start_review("my_skill", moderator="admin")
        mq.approve("my_skill", moderator="admin", reason="cleared")

        rec = mq.get_record("my_skill")
        assert rec.resolution == "approved"
        assert rec.resolved_by == "admin"

    def test_approve_not_under_review_fails(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT, reporter="u1")
        # Not in review — still FLAGGED
        result = mq.approve("my_skill", moderator="admin")
        assert result.success is False


class TestSuspend:

    def test_suspend_blocks_skill(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.SUSPICIOUS_CODE, reporter="u1")
        mq.start_review("my_skill", moderator="admin")

        result = mq.suspend("my_skill", moderator="admin", reason="malicious")
        assert result.success is True
        assert mq.get_status("my_skill") == SkillStatus.SUSPENDED

    def test_suspend_not_under_review_fails(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT, reporter="u1")
        result = mq.suspend("my_skill", moderator="admin")
        assert result.success is False


# ---------------------------------------------------------------------------
# Installability gate
# ---------------------------------------------------------------------------

class TestInstallable:

    def test_unknown_skill_is_installable(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        assert mq.is_installable("brand_new_skill") is True

    def test_active_skill_is_installable(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT, reporter="u1")
        mq.start_review("my_skill", moderator="admin")
        mq.approve("my_skill", moderator="admin")
        assert mq.is_installable("my_skill") is True

    def test_flagged_skill_is_not_installable(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT, reporter="u1")
        assert mq.is_installable("my_skill") is False

    def test_suspended_skill_is_not_installable(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.SUSPICIOUS_CODE, reporter="u1")
        mq.start_review("my_skill", moderator="admin")
        mq.suspend("my_skill", moderator="admin", reason="bad")
        assert mq.is_installable("my_skill") is False


# ---------------------------------------------------------------------------
# Auto-flag rules
# ---------------------------------------------------------------------------

class TestAutoFlagRules:

    def test_high_risk_permission_triggers_flag(self):
        manifest = make_manifest(permissions=["network", "execute"])
        flags = check_auto_flag_rules(manifest)
        assert len(flags) >= 1
        assert any("high-risk" in f.detail.lower() for f in flags)

    def test_excessive_permissions_triggers_flag(self):
        many_perms = ["network", "filesystem", "execute", "a", "b", "c"]
        manifest = make_manifest(permissions=many_perms)
        flags = check_auto_flag_rules(manifest)
        assert any(str(MAX_PERMISSIONS_THRESHOLD) in f.detail for f in flags)

    def test_reserved_name_triggers_flag(self):
        manifest = make_manifest(name="system")
        flags = check_auto_flag_rules(manifest)
        assert len(flags) >= 1
        assert any("reserved" in f.detail.lower() for f in flags)

    def test_clean_skill_no_flags(self):
        manifest = make_manifest(name="my_safe_skill", permissions=["network"])
        flags = check_auto_flag_rules(manifest)
        assert len(flags) == 0

    def test_check_and_auto_flag_creates_record(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        manifest = make_manifest(name="system", permissions=["execute"])
        auto_flags = mq.check_and_auto_flag(manifest)
        assert len(auto_flags) >= 1
        assert mq.get_status("system") == SkillStatus.FLAGGED


# ---------------------------------------------------------------------------
# List / filter queries
# ---------------------------------------------------------------------------

class TestListQueries:

    def test_list_flagged(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("skill_a", FlagReason.COMMUNITY_REPORT, reporter="u1")
        mq.flag_skill("skill_b", FlagReason.SUSPICIOUS_CODE, reporter="u2")
        mq.flag_skill("skill_c", FlagReason.POLICY_VIOLATION, reporter="u3")
        # Move skill_c to review
        mq.start_review("skill_c", moderator="admin")

        flagged = mq.list_flagged()
        assert len(flagged) == 2
        names = {r.skill_name for r in flagged}
        assert names == {"skill_a", "skill_b"}

    def test_list_suspended(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("bad", FlagReason.SUSPICIOUS_CODE, reporter="u1")
        mq.start_review("bad", moderator="admin")
        mq.suspend("bad", moderator="admin", reason="evil")

        suspended = mq.list_suspended()
        assert len(suspended) == 1
        assert suspended[0].skill_name == "bad"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:

    def test_records_survive_reload(self, tmp_path):
        mq1 = ModerationQueue(skills_dir=tmp_path)
        mq1.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT, reporter="u1")

        mq2 = ModerationQueue(skills_dir=tmp_path)
        assert mq2.get_status("my_skill") == SkillStatus.FLAGGED
        assert len(mq2.get_record("my_skill").flags) == 1


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------

class TestRemove:

    def test_remove_clears_record(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("my_skill", FlagReason.COMMUNITY_REPORT, reporter="u1")
        mq.remove("my_skill")
        assert mq.get_status("my_skill") is None

    def test_remove_unknown_is_noop(self, tmp_path):
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.remove("nonexistent")  # should not raise
