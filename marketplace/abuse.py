# marketplace/abuse.py
"""
marketplace/abuse.py
---------------------
Runtime abuse controls for the Bazaar marketplace.

Provides three protection mechanisms:
  1. Rate limiting   — caps tool calls per time window
  2. Quota tracking  — caps total tool calls per day
  3. Circuit breaker — disables skills that error repeatedly

All events are logged to ``<skills_dir>/.abuse_log.json`` for
moderator review.

Usage:
    from marketplace.abuse import AbuseController

    ac = AbuseController(skills_dir=Path("marketplace/skills"))
    ac.check_rate_limit("my_skill", "my_tool")   # raises RateLimitError
    ac.check_quota("my_skill")                    # raises QuotaExceededError
    ac.record_success("my_skill", "my_tool")
    ac.record_error("my_skill", "my_tool", error="timeout")
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("bazaar")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RateLimitError(Exception):
    """Raised when a tool call exceeds the rate limit."""
    pass


class QuotaExceededError(Exception):
    """Raised when a skill exceeds its daily quota."""
    pass


class CircuitOpenError(Exception):
    """Raised when a skill's circuit breaker is open (too many errors)."""
    pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class AbuseConfig:
    """Configuration for abuse controls."""
    # Rate limiting
    rate_limit_calls: int = 60          # max calls per window
    rate_limit_window_seconds: int = 60  # window size in seconds

    # Quota
    daily_quota: int = 1000              # max calls per skill per day

    # Circuit breaker
    circuit_error_threshold: int = 5     # consecutive errors to trip
    circuit_cooldown_seconds: int = 300  # 5 minutes cooldown

    def to_dict(self) -> dict:
        return {
            "rate_limit_calls": self.rate_limit_calls,
            "rate_limit_window_seconds": self.rate_limit_window_seconds,
            "daily_quota": self.daily_quota,
            "circuit_error_threshold": self.circuit_error_threshold,
            "circuit_cooldown_seconds": self.circuit_cooldown_seconds,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AbuseConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class AbuseEventType(str, Enum):
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    CIRCUIT_TRIPPED = "circuit_tripped"
    CIRCUIT_RECOVERED = "circuit_recovered"
    ERROR_RECORDED = "error_recorded"


@dataclass
class AbuseEvent:
    """A single recorded abuse event."""
    event_type: str
    skill_name: str
    tool_name: str
    detail: str
    timestamp: str   # ISO-8601

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "skill_name": self.skill_name,
            "tool_name": self.tool_name,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AbuseEvent":
        return cls(**d)


# ---------------------------------------------------------------------------
# Circuit breaker state
# ---------------------------------------------------------------------------

@dataclass
class CircuitState:
    """State for one skill's circuit breaker."""
    consecutive_errors: int = 0
    tripped: bool = False
    tripped_at: Optional[float] = None   # time.monotonic() when tripped
    last_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Abuse Controller
# ---------------------------------------------------------------------------

class AbuseController:
    """
    Runtime abuse protection for marketplace skills.

    Combines rate limiting, quota tracking, and circuit breaking.
    All events are persisted to an audit log for moderator review.
    """

    AUDIT_FILENAME = ".abuse_log.json"

    def __init__(
        self,
        skills_dir: Path,
        config: Optional[AbuseConfig] = None,
    ):
        self.skills_dir = skills_dir
        self.config = config or AbuseConfig()
        self._audit_path = skills_dir / self.AUDIT_FILENAME

        # Rate limiter: skill_name → list of timestamps (monotonic)
        self._call_timestamps: Dict[str, List[float]] = defaultdict(list)

        # Quota: skill_name → {date_str: count}
        self._daily_counts: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        # Circuit breaker: skill_name → CircuitState
        self._circuits: Dict[str, CircuitState] = defaultdict(CircuitState)

        # Audit log (in-memory + persisted)
        self._events: List[AbuseEvent] = []
        self._load_audit()

    # ---- audit persistence ----

    def _load_audit(self) -> None:
        """Load existing audit events from disk."""
        if self._audit_path.exists():
            try:
                data = json.loads(self._audit_path.read_text(encoding="utf-8"))
                self._events = [
                    AbuseEvent.from_dict(e) for e in data.get("events", [])
                ]
            except (json.JSONDecodeError, KeyError):
                self._events = []

    def _save_audit(self) -> None:
        """Persist audit events to disk."""
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"events": [e.to_dict() for e in self._events]}
        self._audit_path.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def _log_event(
        self,
        event_type: AbuseEventType,
        skill_name: str,
        tool_name: str = "",
        detail: str = "",
    ) -> AbuseEvent:
        """Record an abuse event."""
        event = AbuseEvent(
            event_type=event_type.value,
            skill_name=skill_name,
            tool_name=tool_name,
            detail=detail,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._events.append(event)
        self._save_audit()
        logger.warning(
            "ABUSE [%s] skill=%s tool=%s: %s",
            event_type.value, skill_name, tool_name, detail,
        )
        return event

    # ---- rate limiting ----

    def check_rate_limit(self, skill_name: str, tool_name: str = "") -> None:
        """
        Check if a tool call is within the rate limit.

        Uses a sliding window: keeps timestamps of recent calls and
        removes those outside the window before counting.

        Args:
            skill_name: Name of the skill.
            tool_name:  Name of the tool (for logging).

        Raises:
            RateLimitError: If the rate limit is exceeded.
        """
        now = time.monotonic()
        window = self.config.rate_limit_window_seconds
        timestamps = self._call_timestamps[skill_name]

        # Prune expired timestamps
        cutoff = now - window
        self._call_timestamps[skill_name] = [
            t for t in timestamps if t > cutoff
        ]
        timestamps = self._call_timestamps[skill_name]

        if len(timestamps) >= self.config.rate_limit_calls:
            self._log_event(
                AbuseEventType.RATE_LIMITED, skill_name, tool_name,
                f"{len(timestamps)} calls in {window}s "
                f"(limit: {self.config.rate_limit_calls})",
            )
            raise RateLimitError(
                f"Skill '{skill_name}' exceeded rate limit: "
                f"{self.config.rate_limit_calls} calls per "
                f"{window}s"
            )

        timestamps.append(now)

    # ---- quota ----

    def check_quota(self, skill_name: str) -> None:
        """
        Check if a skill has exceeded its daily quota.

        Args:
            skill_name: Name of the skill.

        Raises:
            QuotaExceededError: If the daily quota is exceeded.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        count = self._daily_counts[skill_name][today]

        if count >= self.config.daily_quota:
            self._log_event(
                AbuseEventType.QUOTA_EXCEEDED, skill_name, "",
                f"{count} calls today (limit: {self.config.daily_quota})",
            )
            raise QuotaExceededError(
                f"Skill '{skill_name}' exceeded daily quota: "
                f"{self.config.daily_quota} calls/day"
            )

        self._daily_counts[skill_name][today] = count + 1

    # ---- circuit breaker ----

    def check_circuit(self, skill_name: str) -> None:
        """
        Check if a skill's circuit breaker is open.

        If the circuit is tripped but the cooldown has passed,
        it automatically recovers (half-open → closed).

        Args:
            skill_name: Name of the skill.

        Raises:
            CircuitOpenError: If the circuit is open and cooldown
                              has not elapsed.
        """
        circuit = self._circuits[skill_name]
        if not circuit.tripped:
            return

        elapsed = time.monotonic() - (circuit.tripped_at or 0)
        if elapsed >= self.config.circuit_cooldown_seconds:
            # Cooldown passed → recover
            circuit.tripped = False
            circuit.consecutive_errors = 0
            circuit.tripped_at = None
            self._log_event(
                AbuseEventType.CIRCUIT_RECOVERED, skill_name, "",
                f"Circuit recovered after {self.config.circuit_cooldown_seconds}s cooldown",
            )
            return

        remaining = int(self.config.circuit_cooldown_seconds - elapsed)
        raise CircuitOpenError(
            f"Skill '{skill_name}' circuit breaker is OPEN "
            f"(too many errors). Retry in {remaining}s."
        )

    def record_success(self, skill_name: str, tool_name: str = "") -> None:
        """
        Record a successful tool execution.

        Resets the circuit breaker's consecutive error count.
        """
        circuit = self._circuits[skill_name]
        circuit.consecutive_errors = 0

    def record_error(
        self,
        skill_name: str,
        tool_name: str = "",
        error: str = "",
    ) -> None:
        """
        Record a failed tool execution.

        Increments the consecutive error count. If the threshold is
        reached, trips the circuit breaker.
        """
        circuit = self._circuits[skill_name]
        circuit.consecutive_errors += 1
        circuit.last_error = error

        self._log_event(
            AbuseEventType.ERROR_RECORDED, skill_name, tool_name,
            f"Error #{circuit.consecutive_errors}: {error}",
        )

        if circuit.consecutive_errors >= self.config.circuit_error_threshold:
            circuit.tripped = True
            circuit.tripped_at = time.monotonic()
            self._log_event(
                AbuseEventType.CIRCUIT_TRIPPED, skill_name, tool_name,
                f"Circuit tripped after {circuit.consecutive_errors} "
                f"consecutive errors",
            )

    # ---- combined pre-call check ----

    def pre_call_check(self, skill_name: str, tool_name: str = "") -> None:
        """
        Run all abuse checks before executing a tool.

        Call this before every tool invocation. It checks
        (in order): circuit breaker → rate limit → quota.

        Args:
            skill_name: Name of the skill.
            tool_name:  Name of the tool.

        Raises:
            CircuitOpenError:   If the circuit breaker is open.
            RateLimitError:     If the rate limit is exceeded.
            QuotaExceededError: If the daily quota is exceeded.
        """
        self.check_circuit(skill_name)
        self.check_rate_limit(skill_name, tool_name)
        self.check_quota(skill_name)

    # ---- queries ----

    def get_events(
        self,
        skill_name: Optional[str] = None,
        event_type: Optional[AbuseEventType] = None,
    ) -> List[AbuseEvent]:
        """
        Query audit events with optional filters.

        Args:
            skill_name: Filter by skill name (None = all).
            event_type: Filter by event type (None = all).

        Returns:
            List of matching AbuseEvent objects.
        """
        events = self._events
        if skill_name:
            events = [e for e in events if e.skill_name == skill_name]
        if event_type:
            events = [e for e in events if e.event_type == event_type.value]
        return events

    def get_circuit_state(self, skill_name: str) -> CircuitState:
        """Return the circuit breaker state for a skill."""
        return self._circuits[skill_name]

    def get_daily_count(self, skill_name: str) -> int:
        """Return the number of calls today for a skill."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._daily_counts[skill_name][today]

    def reset_skill(self, skill_name: str) -> None:
        """
        Reset all abuse state for a skill.

        Clears rate limit timestamps, daily counts, and circuit breaker.
        Does NOT clear audit events (those are permanent).
        """
        self._call_timestamps.pop(skill_name, None)
        self._daily_counts.pop(skill_name, None)
        self._circuits.pop(skill_name, None)
        logger.info("Reset abuse state for skill '%s'", skill_name)
