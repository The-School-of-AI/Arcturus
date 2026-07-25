# marketplace/admin.py
"""
marketplace/admin.py
---------------------
Admin facade for the Bazaar marketplace.

Composes VersionManager, ModerationQueue, and AbuseController
into a single interface for CLI and dashboard use.

Usage:
    from marketplace.admin import AdminDashboard

    admin = AdminDashboard(skills_dir=Path("marketplace/skills"))
    status = admin.get_status_summary()
    print(status)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from marketplace.moderation import (
    ModerationQueue,
    ModerationRecord,
    FlagReason,
    SkillStatus,
    ModerationResult,
)
from marketplace.version_manager import (
    VersionManager,
    SkillVersionInfo,
    RollbackResult,
)
from marketplace.abuse import (
    AbuseController,
    AbuseEvent,
    AbuseEventType,
)

logger = logging.getLogger("bazaar")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StatusSummary:
    """Overview of the marketplace state."""
    total_skills: int = 0
    active_skills: int = 0
    flagged_skills: int = 0
    under_review_skills: int = 0
    suspended_skills: int = 0
    pinned_skills: int = 0
    total_abuse_events: int = 0
    circuit_tripped_skills: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_skills": self.total_skills,
            "active_skills": self.active_skills,
            "flagged_skills": self.flagged_skills,
            "under_review_skills": self.under_review_skills,
            "suspended_skills": self.suspended_skills,
            "pinned_skills": self.pinned_skills,
            "total_abuse_events": self.total_abuse_events,
            "circuit_tripped_skills": self.circuit_tripped_skills,
        }


@dataclass
class SkillReport:
    """Detailed report for a single skill."""
    skill_name: str
    version_info: Optional[SkillVersionInfo] = None
    moderation_record: Optional[ModerationRecord] = None
    abuse_events: List[AbuseEvent] = field(default_factory=list)
    daily_call_count: int = 0
    circuit_tripped: bool = False

    def to_dict(self) -> dict:
        return {
            "skill_name": self.skill_name,
            "version_info": self.version_info.to_dict() if self.version_info else None,
            "moderation_record": self.moderation_record.to_dict() if self.moderation_record else None,
            "abuse_events": [e.to_dict() for e in self.abuse_events],
            "daily_call_count": self.daily_call_count,
            "circuit_tripped": self.circuit_tripped,
        }


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------

class AdminDashboard:
    """
    Facade over marketplace management systems.

    Provides query and action methods for the CLI and future web dashboard.
    """

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.versions = VersionManager(skills_dir=skills_dir)
        self.moderation = ModerationQueue(skills_dir=skills_dir)
        self.abuse = AbuseController(skills_dir=skills_dir)

    # ---- queries ----

    def get_status_summary(self) -> StatusSummary:
        """
        Build a high-level overview of the marketplace.

        Scans all three subsystems and returns counts.
        """
        summary = StatusSummary()

        # Count skills from version ledger
        # (iterate over the internal _skills dict)
        for name, info in self.versions._skills.items():
            summary.total_skills += 1
            if info.pinned:
                summary.pinned_skills += 1

        # Count moderation states
        for rec in self.moderation._records.values():
            status = rec.status
            if status == SkillStatus.FLAGGED.value:
                summary.flagged_skills += 1
            elif status == SkillStatus.UNDER_REVIEW.value:
                summary.under_review_skills += 1
            elif status == SkillStatus.SUSPENDED.value:
                summary.suspended_skills += 1
            elif status == SkillStatus.ACTIVE.value:
                summary.active_skills += 1

        # Skills with no moderation record are assumed active
        known_moderated = set(self.moderation._records.keys())
        known_versioned = set(self.versions._skills.keys())
        unmoderated = known_versioned - known_moderated
        summary.active_skills += len(unmoderated)

        # Abuse events
        summary.total_abuse_events = len(self.abuse.get_events())

        # Tripped circuits
        for name, circuit in self.abuse._circuits.items():
            if circuit.tripped:
                summary.circuit_tripped_skills.append(name)

        return summary

    def get_skill_report(self, name: str) -> SkillReport:
        """
        Build a detailed report for one skill.

        Combines version info, moderation record, and abuse events.
        """
        report = SkillReport(skill_name=name)
        report.version_info = self.versions.get_info(name)
        report.moderation_record = self.moderation.get_record(name)
        report.abuse_events = self.abuse.get_events(skill_name=name)
        report.daily_call_count = self.abuse.get_daily_count(name)

        circuit = self.abuse.get_circuit_state(name)
        report.circuit_tripped = circuit.tripped

        return report

    def get_moderation_queue(self) -> List[ModerationRecord]:
        """Return all flagged skills in the moderation queue."""
        return self.moderation.list_flagged()

    def get_abuse_report(
        self,
        skill_name: Optional[str] = None,
        event_type: Optional[AbuseEventType] = None,
    ) -> List[AbuseEvent]:
        """Return filtered abuse events."""
        return self.abuse.get_events(
            skill_name=skill_name,
            event_type=event_type,
        )

    # ---- moderation actions ----

    def flag_skill(
        self,
        name: str,
        reason: FlagReason,
        reporter: str = "admin",
        detail: str = "",
    ) -> ModerationResult:
        """Flag a skill for review."""
        return self.moderation.flag_skill(name, reason, reporter, detail)

    def start_review(self, name: str, moderator: str) -> ModerationResult:
        """Start reviewing a flagged skill."""
        return self.moderation.start_review(name, moderator)

    def approve_skill(
        self,
        name: str,
        moderator: str,
        reason: str = "Approved after review",
    ) -> ModerationResult:
        """Approve a skill after review."""
        return self.moderation.approve(name, moderator, reason)

    def suspend_skill(
        self,
        name: str,
        moderator: str,
        reason: str = "Suspended after review",
    ) -> ModerationResult:
        """Suspend a skill."""
        return self.moderation.suspend(name, moderator, reason)

    # ---- abuse actions ----

    def reset_abuse(self, name: str) -> None:
        """Reset abuse counters for a skill (keeps audit trail)."""
        self.abuse.reset_skill(name)


# ---------------------------------------------------------------------------
# Formatters (for CLI output)
# ---------------------------------------------------------------------------

def format_status_summary(summary: StatusSummary) -> str:
    """Format a StatusSummary as a human-readable table."""
    lines = [
        "",
        "📊  Marketplace Status",
        "═" * 40,
        f"  Total skills:      {summary.total_skills}",
        f"  Active:            {summary.active_skills}",
        f"  Flagged:           {summary.flagged_skills}",
        f"  Under review:      {summary.under_review_skills}",
        f"  Suspended:         {summary.suspended_skills}",
        f"  Pinned:            {summary.pinned_skills}",
        "─" * 40,
        f"  Abuse events:      {summary.total_abuse_events}",
    ]
    if summary.circuit_tripped_skills:
        lines.append(
            f"  ⚠️  Circuits open:  {', '.join(summary.circuit_tripped_skills)}"
        )
    lines.append("═" * 40)
    lines.append("")
    return "\n".join(lines)


def format_skill_report(report: SkillReport) -> str:
    """Format a SkillReport as a human-readable block."""
    lines = [
        "",
        f"📋  Skill Report: {report.skill_name}",
        "═" * 50,
    ]

    # Version info
    if report.version_info:
        vi = report.version_info
        lines.append(f"  Version:     v{vi.current_version}")
        lines.append(f"  Pinned:      {'Yes' if vi.pinned else 'No'}")
        lines.append(f"  History:     {len(vi.history)} version(s)")
        for entry in vi.history:
            tag = " ← current" if entry.version == vi.current_version else ""
            lines.append(f"    v{entry.version}  {entry.installed_at}{tag}")
    else:
        lines.append("  Version:     (not tracked)")

    lines.append("─" * 50)

    # Moderation
    if report.moderation_record:
        rec = report.moderation_record
        lines.append(f"  Status:      {rec.status}")
        lines.append(f"  Flags:       {len(rec.flags)}")
        for flag in rec.flags:
            lines.append(f"    [{flag.reason}] by {flag.reporter}: {flag.detail}")
        if rec.resolution:
            lines.append(f"  Resolution:  {rec.resolution} by {rec.resolved_by}")
            lines.append(f"               {rec.resolution_reason}")
    else:
        lines.append("  Moderation:  (clean — no flags)")

    lines.append("─" * 50)

    # Abuse
    lines.append(f"  Calls today: {report.daily_call_count}")
    lines.append(f"  Circuit:     {'⚠️ OPEN' if report.circuit_tripped else '✅ Closed'}")
    if report.abuse_events:
        lines.append(f"  Abuse events: {len(report.abuse_events)}")
        for ev in report.abuse_events[-5:]:  # show last 5
            lines.append(f"    [{ev.event_type}] {ev.detail}")
        if len(report.abuse_events) > 5:
            lines.append(f"    ... and {len(report.abuse_events) - 5} more")
    else:
        lines.append("  Abuse events: 0")

    lines.append("═" * 50)
    lines.append("")
    return "\n".join(lines)


def format_moderation_queue(queue: List[ModerationRecord]) -> str:
    """Format the moderation queue as a table."""
    if not queue:
        return "\n  ✅  Moderation queue is empty — no flagged skills.\n"

    lines = [
        "",
        "🚩  Moderation Queue",
        "═" * 60,
        f"  {'Skill':<20} {'Flags':<8} {'Latest reason':<30}",
        "─" * 60,
    ]
    for rec in queue:
        latest = rec.flags[-1] if rec.flags else None
        reason = latest.reason if latest else "—"
        lines.append(f"  {rec.skill_name:<20} {len(rec.flags):<8} {reason:<30}")

    lines.append("─" * 60)
    lines.append(f"  Total: {len(queue)} skill(s) awaiting review")
    lines.append("")
    return "\n".join(lines)


def format_abuse_report(events: List[AbuseEvent]) -> str:
    """Format abuse events as a log."""
    if not events:
        return "\n  ✅  No abuse events recorded.\n"

    lines = [
        "",
        "🔍  Abuse Report",
        "═" * 70,
        f"  {'Timestamp':<26} {'Type':<18} {'Skill':<16} {'Detail'}",
        "─" * 70,
    ]
    for ev in events[-20:]:  # show last 20
        ts = ev.timestamp[:19] if len(ev.timestamp) > 19 else ev.timestamp
        lines.append(
            f"  {ts:<26} {ev.event_type:<18} {ev.skill_name:<16} {ev.detail[:40]}"
        )

    if len(events) > 20:
        lines.append(f"  ... and {len(events) - 20} earlier events")

    lines.append("─" * 70)
    lines.append(f"  Total: {len(events)} event(s)")
    lines.append("")
    return "\n".join(lines)
