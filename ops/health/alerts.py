"""
Health alert rules engine.

Evaluates health check results against configurable rules and fires
notifications when consecutive failure thresholds are breached.

Uses Strategy pattern for notification channels (currently: log-based).
Extensible to Slack, email, PagerDuty by implementing AlertNotifier.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from ops.health.models import HealthResult

logger = logging.getLogger("watchtower.alerts")


@dataclass
class AlertRule:
    """A single alert rule definition."""

    service: str
    condition: str  # "down" or "degraded"
    consecutive_failures: int = 3
    channel: str = "log"


class AlertNotifier(ABC):
    """Interface for alert notification channels."""

    @abstractmethod
    def notify(self, rule: AlertRule, service: str, current_streak: int) -> None:
        """Send an alert notification."""
        pass


class LogNotifier(AlertNotifier):
    """Writes alerts to the application log."""

    def notify(self, rule: AlertRule, service: str, current_streak: int) -> None:
        logger.warning(
            "ALERT: service '%s' has been '%s' for %d consecutive checks (threshold: %d)",
            service,
            rule.condition,
            current_streak,
            rule.consecutive_failures,
        )


NOTIFIER_REGISTRY: Dict[str, AlertNotifier] = {
    "log": LogNotifier(),
}


class AlertEvaluator:
    """
    Evaluates health results against alert rules.

    Tracks consecutive failure counts per service and fires the
    appropriate notifier when the threshold is met.
    """

    def __init__(
        self,
        rules: List[AlertRule],
        notifiers: Optional[Dict[str, AlertNotifier]] = None,
    ):
        self._rules = rules
        self._notifiers = notifiers or NOTIFIER_REGISTRY
        self._streaks: Dict[str, int] = {}
        self._fired: Dict[str, bool] = {}

    @property
    def rules(self) -> List[AlertRule]:
        return list(self._rules)

    @property
    def streaks(self) -> Dict[str, int]:
        return dict(self._streaks)

    def evaluate(self, results: List[HealthResult]) -> List[AlertRule]:
        """
        Evaluate results against all rules. Returns list of rules that fired.

        On each call:
        - If a service matches a rule's condition, increment its streak.
        - If streak >= consecutive_failures and alert hasn't fired yet, fire it.
        - If a service recovers (status != condition), reset its streak.
        """
        status_by_service = {r.service: r.status for r in results}
        fired_rules: List[AlertRule] = []

        for rule in self._rules:
            key = f"{rule.service}:{rule.condition}"
            current_status = status_by_service.get(rule.service)

            if current_status is None:
                continue

            if current_status == rule.condition:
                self._streaks[key] = self._streaks.get(key, 0) + 1

                if self._streaks[
                    key
                ] >= rule.consecutive_failures and not self._fired.get(key, False):
                    notifier = self._notifiers.get(rule.channel)
                    if notifier:
                        notifier.notify(rule, rule.service, self._streaks[key])
                    self._fired[key] = True
                    fired_rules.append(rule)
            else:
                if self._fired.get(key, False):
                    logger.info(
                        "RECOVERED: service '%s' is now '%s' (was '%s' for %d checks)",
                        rule.service,
                        current_status,
                        rule.condition,
                        self._streaks.get(key, 0),
                    )
                self._streaks[key] = 0
                self._fired[key] = False

        return fired_rules

    @classmethod
    def from_config(cls, config_rules: List[Dict[str, Any]]) -> "AlertEvaluator":
        """Create an AlertEvaluator from settings.json alert_rules config."""
        rules = [
            AlertRule(
                service=r.get("service", ""),
                condition=r.get("condition", "down"),
                consecutive_failures=r.get("consecutive_failures", 3),
                channel=r.get("channel", "log"),
            )
            for r in config_rules
            if r.get("service")
        ]
        return cls(rules=rules)
