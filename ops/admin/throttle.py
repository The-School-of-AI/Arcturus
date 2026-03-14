"""
Global cost throttle policy.

Extends the per-run cost limits already enforced in core/loop.py (lines 608-807)
with **daily/hourly global budgets**. The admin can view and update these via the
``/admin/throttle`` endpoints.

Budget config lives in ``settings.json`` under ``watchtower.throttle``::

    "watchtower": {
        "throttle": {
            "daily_budget_usd": 5.0,
            "hourly_budget_usd": 1.0
        }
    }

If the key is missing the policy defaults to generous limits (no throttle).
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from config.settings_loader import settings

logger = logging.getLogger("watchtower.throttle")


@dataclass
class UsageSummary:
    """Snapshot of cost usage vs budget for a time window."""

    window: str  # "hourly" | "daily"
    hours: int
    spent_usd: float
    budget_usd: float
    remaining_usd: float
    usage_pct: float
    throttled: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window": self.window,
            "hours": self.hours,
            "spent_usd": round(self.spent_usd, 6),
            "budget_usd": round(self.budget_usd, 6),
            "remaining_usd": round(max(self.remaining_usd, 0), 6),
            "usage_pct": round(self.usage_pct, 2),
            "throttled": self.throttled,
        }


class ThrottlePolicy:
    """Global cost budget enforcement using spans data."""

    def __init__(self, spans_collection: Optional[Any] = None):
        self._coll = spans_collection

    # ------------------------------------------------------------------
    # Budget config helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_throttle_config() -> Dict[str, float]:
        """Read throttle config from settings."""
        wt = settings.get("watchtower", {})
        return wt.get("throttle", {})

    @staticmethod
    def get_daily_budget() -> float:
        cfg = ThrottlePolicy._get_throttle_config()
        return cfg.get("daily_budget_usd", 10.0)

    @staticmethod
    def get_hourly_budget() -> float:
        cfg = ThrottlePolicy._get_throttle_config()
        return cfg.get("hourly_budget_usd", 2.0)

    # ------------------------------------------------------------------
    # Cost aggregation from spans
    # ------------------------------------------------------------------

    def _aggregate_cost(self, hours: int) -> float:
        """Sum cost_usd from llm.generate spans in the given window."""
        if self._coll is None:
            return 0.0

        from datetime import datetime, timedelta

        since = datetime.utcnow() - timedelta(hours=hours)
        pipeline = [
            {
                "$match": {
                    "start_time": {"$gte": since},
                    "name": "llm.generate",
                    "attributes.cost_usd": {"$exists": True},
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": {"$toDouble": "$attributes.cost_usd"}},
                }
            },
        ]
        row = next(self._coll.aggregate(pipeline), None)
        return float(row["total"]) if row else 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_budget(self) -> tuple[bool, str]:
        """
        Check if the current usage is within budget.

        Returns ``(allowed, reason)``.
        """
        hourly_spent = self._aggregate_cost(1)
        hourly_budget = self.get_hourly_budget()
        if hourly_spent >= hourly_budget:
            msg = f"Hourly budget exceeded: ${hourly_spent:.4f} >= ${hourly_budget:.2f}"
            logger.warning(msg)
            return False, msg

        daily_spent = self._aggregate_cost(24)
        daily_budget = self.get_daily_budget()
        if daily_spent >= daily_budget:
            msg = f"Daily budget exceeded: ${daily_spent:.4f} >= ${daily_budget:.2f}"
            logger.warning(msg)
            return False, msg

        return True, "Within budget"

    def get_usage_summary(self) -> Dict[str, Any]:
        """Return hourly and daily usage summaries."""
        hourly_spent = self._aggregate_cost(1)
        hourly_budget = self.get_hourly_budget()
        daily_spent = self._aggregate_cost(24)
        daily_budget = self.get_daily_budget()

        hourly = UsageSummary(
            window="hourly",
            hours=1,
            spent_usd=hourly_spent,
            budget_usd=hourly_budget,
            remaining_usd=hourly_budget - hourly_spent,
            usage_pct=(hourly_spent / hourly_budget * 100) if hourly_budget > 0 else 0,
            throttled=hourly_spent >= hourly_budget,
        )
        daily = UsageSummary(
            window="daily",
            hours=24,
            spent_usd=daily_spent,
            budget_usd=daily_budget,
            remaining_usd=daily_budget - daily_spent,
            usage_pct=(daily_spent / daily_budget * 100) if daily_budget > 0 else 0,
            throttled=daily_spent >= daily_budget,
        )
        allowed, reason = self.check_budget()
        return {
            "hourly": hourly.to_dict(),
            "daily": daily.to_dict(),
            "allowed": allowed,
            "reason": reason,
        }
