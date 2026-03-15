"""Unit tests for ops.health.alerts.AlertEvaluator."""

import pytest
from unittest.mock import MagicMock

from ops.health.models import HealthResult
from ops.health.alerts import AlertRule, AlertEvaluator, LogNotifier


def _results(**overrides):
    """Build a standard set of health results with optional status overrides."""
    defaults = {
        "mongodb": "ok",
        "qdrant": "ok",
        "ollama": "ok",
        "mcp_gateway": "ok",
        "neo4j": "ok",
        "agent_core": "ok",
    }
    defaults.update(overrides)
    return [HealthResult(service=svc, status=st) for svc, st in defaults.items()]


class TestAlertEvaluatorStreaks:
    """Tests for consecutive failure tracking behavior."""

    def test_no_alert_below_threshold(self):
        """When consecutive failures < threshold, no alert fires."""
        rules = [AlertRule(service="mongodb", condition="down", consecutive_failures=3)]
        evaluator = AlertEvaluator(rules=rules)

        fired = evaluator.evaluate(_results(mongodb="down"))
        assert fired == []
        fired = evaluator.evaluate(_results(mongodb="down"))
        assert fired == []
        assert evaluator.streaks["mongodb:down"] == 2

    def test_alert_fires_at_threshold(self):
        """When consecutive failures == threshold, alert fires exactly once."""
        mock_notifier = MagicMock()
        rules = [AlertRule(service="mongodb", condition="down", consecutive_failures=3)]
        evaluator = AlertEvaluator(rules=rules, notifiers={"log": mock_notifier})

        evaluator.evaluate(_results(mongodb="down"))
        evaluator.evaluate(_results(mongodb="down"))
        fired = evaluator.evaluate(_results(mongodb="down"))

        assert len(fired) == 1
        assert fired[0].service == "mongodb"
        mock_notifier.notify.assert_called_once()

    def test_alert_does_not_fire_again_after_threshold(self):
        """Once fired, the same alert does not fire again until recovery."""
        mock_notifier = MagicMock()
        rules = [AlertRule(service="qdrant", condition="down", consecutive_failures=2)]
        evaluator = AlertEvaluator(rules=rules, notifiers={"log": mock_notifier})

        evaluator.evaluate(_results(qdrant="down"))
        evaluator.evaluate(_results(qdrant="down"))
        evaluator.evaluate(_results(qdrant="down"))
        evaluator.evaluate(_results(qdrant="down"))

        assert mock_notifier.notify.call_count == 1

    def test_streak_resets_on_recovery(self):
        """When a service recovers, its streak resets to 0."""
        rules = [AlertRule(service="mongodb", condition="down", consecutive_failures=3)]
        evaluator = AlertEvaluator(rules=rules)

        evaluator.evaluate(_results(mongodb="down"))
        evaluator.evaluate(_results(mongodb="down"))
        evaluator.evaluate(_results(mongodb="ok"))

        assert evaluator.streaks["mongodb:down"] == 0

    def test_alert_can_refire_after_recovery(self):
        """After recovery + new failures, alert fires again."""
        mock_notifier = MagicMock()
        rules = [AlertRule(service="mongodb", condition="down", consecutive_failures=2)]
        evaluator = AlertEvaluator(rules=rules, notifiers={"log": mock_notifier})

        evaluator.evaluate(_results(mongodb="down"))
        evaluator.evaluate(_results(mongodb="down"))
        assert mock_notifier.notify.call_count == 1

        evaluator.evaluate(_results(mongodb="ok"))

        evaluator.evaluate(_results(mongodb="down"))
        evaluator.evaluate(_results(mongodb="down"))
        assert mock_notifier.notify.call_count == 2


class TestAlertEvaluatorMultipleRules:
    """Tests for evaluator with multiple rules."""

    def test_independent_tracking_per_service(self):
        """Each service has its own streak counter."""
        rules = [
            AlertRule(service="mongodb", condition="down", consecutive_failures=2),
            AlertRule(service="qdrant", condition="down", consecutive_failures=2),
        ]
        evaluator = AlertEvaluator(rules=rules)

        evaluator.evaluate(_results(mongodb="down", qdrant="ok"))
        evaluator.evaluate(_results(mongodb="down", qdrant="down"))

        assert evaluator.streaks["mongodb:down"] == 2
        assert evaluator.streaks["qdrant:down"] == 1

    def test_degraded_condition_tracked_separately(self):
        """A rule for 'degraded' does not interfere with 'down' tracking."""
        rules = [
            AlertRule(service="ollama", condition="degraded", consecutive_failures=2),
        ]
        evaluator = AlertEvaluator(rules=rules)

        evaluator.evaluate(_results(ollama="down"))
        assert evaluator.streaks.get("ollama:degraded", 0) == 0

        evaluator.evaluate(_results(ollama="degraded"))
        assert evaluator.streaks["ollama:degraded"] == 1

    def test_missing_service_in_results_is_ignored(self):
        """If a service has a rule but is not in results, nothing happens."""
        rules = [
            AlertRule(service="nonexistent", condition="down", consecutive_failures=1)
        ]
        evaluator = AlertEvaluator(rules=rules)

        fired = evaluator.evaluate(_results())
        assert fired == []


class TestAlertEvaluatorFromConfig:
    """Tests for AlertEvaluator.from_config factory."""

    def test_creates_rules_from_config_dicts(self):
        """from_config parses settings-style dicts into AlertRule objects."""
        config = [
            {
                "service": "mongodb",
                "condition": "down",
                "consecutive_failures": 5,
                "channel": "log",
            },
            {"service": "qdrant", "condition": "degraded", "consecutive_failures": 3},
        ]
        evaluator = AlertEvaluator.from_config(config)

        assert len(evaluator.rules) == 2
        assert evaluator.rules[0].service == "mongodb"
        assert evaluator.rules[0].consecutive_failures == 5
        assert evaluator.rules[1].condition == "degraded"
        assert evaluator.rules[1].channel == "log"

    def test_skips_entries_without_service(self):
        """Entries missing 'service' key are filtered out."""
        config = [
            {"condition": "down"},
            {"service": "mongodb", "condition": "down"},
        ]
        evaluator = AlertEvaluator.from_config(config)
        assert len(evaluator.rules) == 1

    def test_empty_config_creates_no_rules(self):
        """Empty config list creates evaluator with no rules."""
        evaluator = AlertEvaluator.from_config([])
        assert evaluator.rules == []


class TestLogNotifier:
    """Tests for LogNotifier behavior."""

    def test_notify_does_not_raise(self):
        """LogNotifier.notify completes without error."""
        notifier = LogNotifier()
        rule = AlertRule(service="mongodb", condition="down", consecutive_failures=3)
        notifier.notify(rule, "mongodb", 3)
