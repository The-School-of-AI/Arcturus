"""
Periodic health check scheduler.

Runs health checks on a configurable interval, persists results
to MongoDB via HealthRepository, evaluates alert rules, and logs
a summary each tick.
"""

import asyncio
import logging
from typing import Optional

from config.settings_loader import settings
from ops.health.alerts import AlertEvaluator
from ops.health.checks import collect_resources, run_all_health_checks
from ops.health.repository import HealthRepository

logger = logging.getLogger("watchtower.health")


class HealthScheduler:
    """
    Asyncio background task that periodically runs all health checks,
    persists snapshots to MongoDB, evaluates alerts, and logs results.
    """

    def __init__(
        self,
        repository: HealthRepository,
        alert_evaluator: Optional[AlertEvaluator] = None,
        interval_seconds: Optional[int] = None,
    ):
        self._repository = repository
        self._alert_evaluator = alert_evaluator
        watchtower_cfg = settings.get("watchtower", {})
        self._interval = interval_seconds or watchtower_cfg.get(
            "health_check_interval_seconds", 60
        )
        self._task: Optional[asyncio.Task[None]] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def interval_seconds(self) -> int:
        return self._interval

    async def start(self) -> None:
        """Spawn the background tick loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("HealthScheduler started (interval=%ds)", self._interval)

    async def stop(self) -> None:
        """Cancel the background task and wait for clean exit."""
        if not self._running:
            return
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("HealthScheduler stopped")

    async def _loop(self) -> None:
        """Run health checks every interval_seconds until cancelled."""
        try:
            while self._running:
                await self._tick()
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            return

    async def _tick(self) -> None:
        """Execute one round of health checks, persist, and log."""
        try:
            results = await asyncio.to_thread(run_all_health_checks)
            resources = await asyncio.to_thread(collect_resources)

            try:
                self._repository.save_snapshot(results, resources=resources)
                self._persist_failures = 0
            except Exception:
                self._persist_failures = getattr(self, "_persist_failures", 0) + 1
                if self._persist_failures <= 1:
                    logger.warning(
                        "Health tick: MongoDB unavailable, snapshots will not be persisted"
                    )

            if self._alert_evaluator is not None:
                self._alert_evaluator.evaluate(results)

            ok = sum(1 for r in results if r.status == "ok")
            total = len(results)
            degraded = sum(1 for r in results if r.status == "degraded")
            down = sum(1 for r in results if r.status == "down")

            if down > 0:
                logger.warning(
                    "Health tick: %d/%d ok, %d degraded, %d DOWN | CPU=%.1f%% MEM=%.1f%%",
                    ok,
                    total,
                    degraded,
                    down,
                    resources.cpu_pct,
                    resources.mem_pct,
                )
            else:
                logger.info(
                    "Health tick: %d/%d ok, %d degraded | CPU=%.1f%% MEM=%.1f%%",
                    ok,
                    total,
                    degraded,
                    resources.cpu_pct,
                    resources.mem_pct,
                )
        except Exception as exc:
            logger.error("Health tick failed: %s", exc, exc_info=True)
