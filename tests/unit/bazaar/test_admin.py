import sys
from pathlib import Path
from typing import List

import click
import pytest
from click.testing import CliRunner

from marketplace.abuse import AbuseEvent, AbuseEventType
from marketplace.admin import (
    AdminDashboard,
    SkillReport,
    StatusSummary,
    format_abuse_report,
    format_moderation_queue,
    format_skill_report,
    format_status_summary,
)
from marketplace.moderation import FlagReason, ModerationRecord, SkillStatus
from marketplace.sdk.cli import admin as admin_cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def setup_dashboard(tmp_path: Path) -> AdminDashboard:
    """Create an AdminDashboard with an empty skills dir."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return AdminDashboard(skills_dir=skills_dir)


def setup_populated_dashboard(tmp_path: Path) -> AdminDashboard:
    """Create a dashboard with some skills in various states."""
    dashboard = setup_dashboard(tmp_path)

    # Record some skills in version ledger
    dashboard.versions.record_install("skill_alpha", "1.0.0")
    dashboard.versions.record_install("skill_beta", "2.0.0")
    dashboard.versions.record_install("skill_gamma", "1.5.0")
    dashboard.versions.pin("skill_gamma")

    # Flag one skill
    dashboard.moderation.flag_skill(
        "skill_beta", FlagReason.COMMUNITY_REPORT,
        reporter="user1", detail="suspicious behavior",
    )

    return dashboard


# ---------------------------------------------------------------------------
# AdminDashboard — queries
# ---------------------------------------------------------------------------

class TestStatusSummary:

    def test_empty_marketplace(self, tmp_path):
        dashboard = setup_dashboard(tmp_path)
        summary = dashboard.get_status_summary()
        assert summary.total_skills == 0
        assert summary.flagged_skills == 0

    def test_counts_skills(self, tmp_path):
        dashboard = setup_populated_dashboard(tmp_path)
        summary = dashboard.get_status_summary()
        assert summary.total_skills == 3
        assert summary.pinned_skills == 1

    def test_counts_flagged(self, tmp_path):
        dashboard = setup_populated_dashboard(tmp_path)
        summary = dashboard.get_status_summary()
        assert summary.flagged_skills == 1

    def test_counts_active(self, tmp_path):
        dashboard = setup_populated_dashboard(tmp_path)
        summary = dashboard.get_status_summary()
        # skill_alpha and skill_gamma have no moderation record → active
        # skill_beta is flagged
        assert summary.active_skills == 2

    def test_summary_to_dict(self, tmp_path):
        dashboard = setup_dashboard(tmp_path)
        summary = dashboard.get_status_summary()
        d = summary.to_dict()
        assert "total_skills" in d
        assert "circuit_tripped_skills" in d


class TestSkillReport:

    def test_report_for_known_skill(self, tmp_path):
        dashboard = setup_populated_dashboard(tmp_path)
        report = dashboard.get_skill_report("skill_alpha")

        assert report.skill_name == "skill_alpha"
        assert report.version_info is not None
        assert report.version_info.current_version == "1.0.0"

    def test_report_for_unknown_skill(self, tmp_path):
        dashboard = setup_dashboard(tmp_path)
        report = dashboard.get_skill_report("nonexistent")

        assert report.skill_name == "nonexistent"
        assert report.version_info is None
        assert report.moderation_record is None

    def test_report_includes_moderation(self, tmp_path):
        dashboard = setup_populated_dashboard(tmp_path)
        report = dashboard.get_skill_report("skill_beta")

        assert report.moderation_record is not None
        assert report.moderation_record.status == SkillStatus.FLAGGED.value

    def test_report_to_dict(self, tmp_path):
        dashboard = setup_populated_dashboard(tmp_path)
        report = dashboard.get_skill_report("skill_alpha")
        d = report.to_dict()
        assert d["skill_name"] == "skill_alpha"


class TestModerationQueue:

    def test_empty_queue(self, tmp_path):
        dashboard = setup_dashboard(tmp_path)
        queue = dashboard.get_moderation_queue()
        assert len(queue) == 0

    def test_queue_contains_flagged(self, tmp_path):
        dashboard = setup_populated_dashboard(tmp_path)
        queue = dashboard.get_moderation_queue()
        assert len(queue) == 1
        assert queue[0].skill_name == "skill_beta"


# ---------------------------------------------------------------------------
# AdminDashboard — actions
# ---------------------------------------------------------------------------

class TestAdminActions:

    def test_flag_skill(self, tmp_path):
        dashboard = setup_dashboard(tmp_path)
        result = dashboard.flag_skill(
            "some_skill", FlagReason.SUSPICIOUS_CODE,
            reporter="admin", detail="looks fishy",
        )
        assert result.success is True

    def test_full_moderation_flow(self, tmp_path):
        dashboard = setup_populated_dashboard(tmp_path)

        # skill_beta is already flagged
        result = dashboard.start_review("skill_beta", moderator="alice")
        assert result.success is True

        result = dashboard.approve_skill(
            "skill_beta", moderator="alice", reason="false alarm"
        )
        assert result.success is True

    def test_suspend_flow(self, tmp_path):
        dashboard = setup_populated_dashboard(tmp_path)
        dashboard.start_review("skill_beta", moderator="alice")
        result = dashboard.suspend_skill("skill_beta", moderator="alice")
        assert result.success is True
        assert dashboard.get_skill_report("skill_beta").moderation_record.status == SkillStatus.SUSPENDED.value

    def test_reset_abuse(self, tmp_path):
        dashboard = setup_dashboard(tmp_path)
        dashboard.abuse.record_error("skill_a", error="err")
        assert dashboard.abuse.get_circuit_state("skill_a").consecutive_errors == 1

        dashboard.reset_abuse("skill_a")
        assert dashboard.abuse.get_circuit_state("skill_a").consecutive_errors == 0


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class TestFormatters:

    def test_format_status_summary(self, tmp_path):
        dashboard = setup_populated_dashboard(tmp_path)
        dashboard.abuse.record_error("skill_a", error="err")
        dashboard.abuse.record_error("skill_a", error="err")
        dashboard.abuse.record_error("skill_a", error="err")
        dashboard.abuse.record_error("skill_a", error="err")
        dashboard.abuse.record_error("skill_a", error="err") # should trip at 5 by default config

        summary = dashboard.get_status_summary()
        out = format_status_summary(summary)
        assert "Total skills:      3" in out
        assert "skill_a" in out

    def test_format_skill_report(self, tmp_path):
        dashboard = setup_populated_dashboard(tmp_path)
        report = dashboard.get_skill_report("skill_beta")
        out = format_skill_report(report)
        assert "Skill Report: skill_beta" in out
        assert "Version:     v2.0.0" in out
        assert "Status:      flagged" in out

        empty_report = dashboard.get_skill_report("unknown")
        empty_out = format_skill_report(empty_report)
        assert "(not tracked)" in empty_out
        assert "clean — no flags" in empty_out

    def test_format_moderation_queue(self, tmp_path):
        dashboard = setup_populated_dashboard(tmp_path)
        queue = dashboard.get_moderation_queue()
        out = format_moderation_queue(queue)
        assert "skill_beta" in out
        assert "Total: 1" in out

        dashboard2 = setup_dashboard(tmp_path / "empty")
        queue2 = dashboard2.get_moderation_queue()
        out2 = format_moderation_queue(queue2)
        assert "empty" in out2

    def test_format_abuse_report(self, tmp_path):
        dashboard = setup_dashboard(tmp_path)
        dashboard.abuse.record_error("skill_a", tool_name="tool_1", error="err")
        events = dashboard.get_abuse_report()
        out = format_abuse_report(events)
        assert "error_recorded" in out
        assert "skill_a" in out

        out2 = format_abuse_report([])
        assert "No abuse events recorded." in out2


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------

class TestCLICommands:

    @pytest.fixture
    def populated_dir(self, tmp_path: Path):
        setup_populated_dashboard(tmp_path)
        return tmp_path / "skills"

    def test_admin_status(self, populated_dir):
        runner = CliRunner()
        result = runner.invoke(admin_cli, ["status", "--skills-root", str(populated_dir)])
        assert result.exit_code == 0
        assert "Total skills:" in result.output

    def test_admin_info(self, populated_dir):
        runner = CliRunner()
        result = runner.invoke(admin_cli, ["info", "skill_beta", "--skills-root", str(populated_dir)])
        assert result.exit_code == 0
        assert "Skill Report: skill_beta" in result.output

    def test_admin_queue(self, populated_dir):
        runner = CliRunner()
        result = runner.invoke(admin_cli, ["queue", "--skills-root", str(populated_dir)])
        assert result.exit_code == 0
        assert "skill_beta" in result.output

    def test_admin_flag(self, populated_dir):
        runner = CliRunner()
        result = runner.invoke(
            admin_cli,
            ["flag", "skill_alpha", "--reason", "suspicious_code", "--detail", "bad", "--skills-root", str(populated_dir)]
        )
        assert result.exit_code == 0
        assert "🚩" in result.output

    def test_admin_review_and_approve(self, populated_dir):
        runner = CliRunner()
        result1 = runner.invoke(
            admin_cli,
            ["review", "skill_beta", "--moderator", "admin", "--skills-root", str(populated_dir)]
        )
        assert result1.exit_code == 0
        assert "🔍" in result1.output

        result2 = runner.invoke(
            admin_cli,
            ["approve", "skill_beta", "--moderator", "admin", "--skills-root", str(populated_dir)]
        )
        assert result2.exit_code == 0
        assert "✅" in result2.output

    def test_admin_review_and_suspend(self, populated_dir):
        runner = CliRunner()
        runner.invoke(
            admin_cli,
            ["review", "skill_beta", "--moderator", "admin", "--skills-root", str(populated_dir)]
        )
        result2 = runner.invoke(
            admin_cli,
            ["suspend", "skill_beta", "--moderator", "admin", "--skills-root", str(populated_dir)]
        )
        assert result2.exit_code == 0
        assert "🚫" in result2.output

    def test_admin_abuse_report(self, populated_dir):
        from marketplace.abuse import AbuseController
        ac = AbuseController(skills_dir=populated_dir)
        ac.record_error("skill_beta", "tool_1", "crash")

        runner = CliRunner()
        result = runner.invoke(admin_cli, ["abuse-report", "--skills-root", str(populated_dir)])
        assert result.exit_code == 0
        assert "Abuse Report" in result.output

    def test_admin_reset_abuse(self, populated_dir):
        runner = CliRunner()
        result = runner.invoke(admin_cli, ["reset-abuse", "skill_alpha", "--skills-root", str(populated_dir)])
        assert result.exit_code == 0
        assert "🔄" in result.output
