import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from marketplace.abuse import (
    AbuseConfig,
    AbuseController,
    AbuseEvent,
    AbuseEventType,
    CircuitOpenError,
    CircuitState,
    QuotaExceededError,
    RateLimitError,
)


def make_controller(tmp_path: Path, **kwargs) -> AbuseController:
    """Helper to create a controller with a custom config."""
    config = AbuseConfig(**kwargs)
    return AbuseController(skills_dir=tmp_path, config=config)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig:

    def test_default_config(self):
        c = AbuseConfig()
        assert c.rate_limit_calls == 60
        assert c.daily_quota == 1000

    def test_serialization(self):
        c1 = AbuseConfig(rate_limit_calls=10, daily_quota=50)
        d = c1.to_dict()
        c2 = AbuseConfig.from_dict(d)
        assert c2.rate_limit_calls == 10
        assert c2.daily_quota == 50


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

class TestRateLimit:

    def test_within_limit_passes(self, tmp_path):
        ac = make_controller(tmp_path, rate_limit_calls=3)
        ac.check_rate_limit("skill_a")
        ac.check_rate_limit("skill_a")
        ac.check_rate_limit("skill_a")  # should not raise

    def test_exceeding_limit_raises(self, tmp_path):
        ac = make_controller(tmp_path, rate_limit_calls=2)
        ac.check_rate_limit("skill_a")
        ac.check_rate_limit("skill_a")

        with pytest.raises(RateLimitError):
            ac.check_rate_limit("skill_a")

    def test_limits_are_isolated_by_skill(self, tmp_path):
        ac = make_controller(tmp_path, rate_limit_calls=1)
        ac.check_rate_limit("skill_a")

        # skill_b should still be allowed
        ac.check_rate_limit("skill_b")

    def test_sliding_window_expires(self, tmp_path):
        # 1 call per second
        ac = make_controller(tmp_path, rate_limit_calls=1, rate_limit_window_seconds=1)
        ac.check_rate_limit("skill_a")

        # Second call immediately fails
        with pytest.raises(RateLimitError):
            ac.check_rate_limit("skill_a")

        # Wait for window to slide
        time.sleep(1.1)

        # Call succeeds again
        ac.check_rate_limit("skill_a")

    def test_rate_limit_logs_event(self, tmp_path):
        ac = make_controller(tmp_path, rate_limit_calls=1)
        ac.check_rate_limit("skill_a")

        try:
            ac.check_rate_limit("skill_a", tool_name="tool_1")
        except RateLimitError:
            pass

        events = ac.get_events()
        assert len(events) == 1
        assert events[0].event_type == AbuseEventType.RATE_LIMITED
        assert events[0].tool_name == "tool_1"


# ---------------------------------------------------------------------------
# Quota
# ---------------------------------------------------------------------------

class TestQuota:

    def test_within_quota_passes(self, tmp_path):
        ac = make_controller(tmp_path, daily_quota=2)
        ac.check_quota("skill_a")
        ac.check_quota("skill_a")  # should not raise

    def test_exceeding_quota_raises(self, tmp_path):
        ac = make_controller(tmp_path, daily_quota=1)
        ac.check_quota("skill_a")

        with pytest.raises(QuotaExceededError):
            ac.check_quota("skill_a")

    def test_quotas_are_isolated_by_skill(self, tmp_path):
        ac = make_controller(tmp_path, daily_quota=1)
        ac.check_quota("skill_a")

        # skill_b still allowed
        ac.check_quota("skill_b")

    def test_get_daily_count(self, tmp_path):
        ac = make_controller(tmp_path, daily_quota=5)
        ac.check_quota("skill_a")
        ac.check_quota("skill_a")
        assert ac.get_daily_count("skill_a") == 2
        assert ac.get_daily_count("skill_b") == 0

    def test_quota_logs_event(self, tmp_path):
        ac = make_controller(tmp_path, daily_quota=1)
        ac.check_quota("skill_a")

        try:
            ac.check_quota("skill_a")
        except QuotaExceededError:
            pass

        events = ac.get_events()
        assert len(events) == 1
        assert events[0].event_type == AbuseEventType.QUOTA_EXCEEDED


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:

    def test_initial_state_is_closed(self, tmp_path):
        ac = make_controller(tmp_path)
        ac.check_circuit("skill_a")  # should not raise

    def test_trips_at_threshold(self, tmp_path):
        ac = make_controller(tmp_path, circuit_error_threshold=2)
        ac.record_error("skill_a", "tool_1", error="err1")
        ac.check_circuit("skill_a")  # 1 error, still closed

        ac.record_error("skill_a", "tool_1", error="err2")

        with pytest.raises(CircuitOpenError):
            ac.check_circuit("skill_a")

    def test_cooldown_recovery(self, tmp_path):
        ac = make_controller(
            tmp_path,
            circuit_error_threshold=1,
            circuit_cooldown_seconds=1,
        )
        ac.record_error("skill_a", "tool_1", "crash")

        with pytest.raises(CircuitOpenError):
            ac.check_circuit("skill_a")

        # Wait for cooldown
        time.sleep(1.1)

        # First call after cooldown should pass and reset state (half-open -> closed)
        ac.check_circuit("skill_a")

    def test_success_resets_consecutive_errors(self, tmp_path):
        ac = make_controller(tmp_path, circuit_error_threshold=2)
        ac.record_error("skill_a", "tool_1", "err")
        ac.record_success("skill_a", "tool_1")
        ac.record_error("skill_a", "tool_1", "err")

        # Should be open if consecutive, but success reset it
        ac.check_circuit("skill_a")

    def test_circuits_are_isolated(self, tmp_path):
        ac = make_controller(tmp_path, circuit_error_threshold=1)
        ac.record_error("skill_a", "tool_1", "err")

        with pytest.raises(CircuitOpenError):
            ac.check_circuit("skill_a")

        ac.check_circuit("skill_b")  # b is still closed

    def test_circuit_tripped_logs_events(self, tmp_path):
        ac = make_controller(tmp_path, circuit_error_threshold=1)
        ac.record_error("skill_a", "tool_1", "crash")

        events = ac.get_events()
        assert len(events) == 2  # ERROR_RECORDED + CIRCUIT_TRIPPED
        assert events[0].event_type == AbuseEventType.ERROR_RECORDED
        assert events[1].event_type == AbuseEventType.CIRCUIT_TRIPPED
        assert events[1].tool_name == "tool_1"

    def test_get_circuit_state(self, tmp_path):
        ac = make_controller(tmp_path, circuit_error_threshold=3)
        ac.record_error("skill_a", "tool_1", "err")
        state = ac.get_circuit_state("skill_a")
        assert state.consecutive_errors == 1
        assert state.tripped is False


# ---------------------------------------------------------------------------
# pre_call_check (combined)
# ---------------------------------------------------------------------------

class TestPreCallCheck:

    def test_pre_call_check_passes_clean(self, tmp_path):
        ac = make_controller(tmp_path)
        ac.pre_call_check("skill_a", "tool_1")  # should not raise

    def test_pre_call_check_rejects_circuit_open(self, tmp_path):
        ac = make_controller(tmp_path, circuit_error_threshold=1)
        ac.record_error("skill_a", "tool_1", "err")

        with pytest.raises(CircuitOpenError):
            ac.pre_call_check("skill_a", "tool_1")

    def test_pre_call_check_rejects_rate_limit(self, tmp_path):
        ac = make_controller(tmp_path, rate_limit_calls=1)
        ac.pre_call_check("skill_a", "tool_1")

        with pytest.raises(RateLimitError):
            ac.pre_call_check("skill_a", "tool_1")

    def test_pre_call_check_rejects_quota(self, tmp_path):
        ac = make_controller(tmp_path, rate_limit_calls=100, daily_quota=1)
        ac.pre_call_check("skill_a", "tool_1")

        with pytest.raises(QuotaExceededError):
            ac.pre_call_check("skill_a", "tool_1")


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class TestAuditLog:

    def test_events_filtered_by_skill(self, tmp_path):
        ac = make_controller(tmp_path, rate_limit_calls=1)
        ac.check_rate_limit("skill_a")
        try:
            ac.check_rate_limit("skill_a")
        except RateLimitError:
            pass

        events = ac.get_events(skill_name="skill_a")
        assert len(events) >= 1
        assert all(e.skill_name == "skill_a" for e in events)

    def test_events_filtered_by_type(self, tmp_path):
        ac = make_controller(tmp_path, circuit_error_threshold=1)
        ac.record_error("skill_a", "tool_1", "crash")

        tripped = ac.get_events(event_type=AbuseEventType.CIRCUIT_TRIPPED)
        errors = ac.get_events(event_type=AbuseEventType.ERROR_RECORDED)
        assert len(tripped) == 1
        assert len(errors) == 1

    def test_audit_persists_across_instances(self, tmp_path):
        ac1 = make_controller(tmp_path, circuit_error_threshold=1)
        ac1.record_error("skill_a", "tool_1", "crash")

        ac2 = AbuseController(skills_dir=tmp_path)
        events = ac2.get_events(skill_name="skill_a")
        assert len(events) >= 1


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:

    def test_reset_clears_rate_and_quota(self, tmp_path):
        ac = make_controller(tmp_path, rate_limit_calls=2, daily_quota=2)
        ac.check_rate_limit("skill_a")
        ac.check_rate_limit("skill_a")
        ac.check_quota("skill_a")
        ac.check_quota("skill_a")

        ac.reset_skill("skill_a")

        # Should be able to call again
        ac.check_rate_limit("skill_a")
        ac.check_quota("skill_a")

    def test_reset_clears_circuit(self, tmp_path):
        ac = make_controller(tmp_path, circuit_error_threshold=1)
        ac.record_error("skill_a", "tool_1", "err")

        ac.reset_skill("skill_a")
        ac.check_circuit("skill_a")  # should not raise

    def test_reset_keeps_audit_events(self, tmp_path):
        ac = make_controller(tmp_path, circuit_error_threshold=1)
        ac.record_error("skill_a", "tool_1", "err")

        events_before = len(ac.get_events())
        ac.reset_skill("skill_a")
        events_after = len(ac.get_events())
        assert events_after == events_before
