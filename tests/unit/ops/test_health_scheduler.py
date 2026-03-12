"""Unit tests for ops.health.scheduler.HealthScheduler."""

import asyncio

import mongomock
import pytest

from ops.health.models import HealthResult, ResourceSnapshot
from ops.health.repository import HealthRepository
from ops.health.scheduler import HealthScheduler
from unittest.mock import patch, MagicMock


@pytest.fixture()
def collection():
    """Fresh mongomock collection for each test."""
    client = mongomock.MongoClient()
    return client["watchtower"]["health_checks"]


@pytest.fixture()
def repo(collection):
    """HealthRepository backed by mongomock."""
    return HealthRepository(collection)


def _mock_health_results():
    return [
        HealthResult(service="mongodb", status="ok", latency_ms=5.0),
        HealthResult(service="qdrant", status="ok", latency_ms=3.0),
    ]


def _mock_resources():
    return ResourceSnapshot(cpu_pct=25.0, mem_pct=60.0, disk_pct=40.0)


class TestHealthSchedulerLifecycle:
    """Tests for start/stop lifecycle behavior."""

    @pytest.mark.asyncio
    async def test_starts_and_sets_running_flag(self, repo):
        """After start(), is_running is True."""
        scheduler = HealthScheduler(repository=repo, interval_seconds=300)
        with (
            patch(
                "ops.health.scheduler.run_all_health_checks",
                return_value=_mock_health_results(),
            ),
            patch(
                "ops.health.scheduler.collect_resources", return_value=_mock_resources()
            ),
        ):
            await scheduler.start()
            assert scheduler.is_running is True
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self, repo):
        """After stop(), is_running is False."""
        scheduler = HealthScheduler(repository=repo, interval_seconds=300)
        with (
            patch(
                "ops.health.scheduler.run_all_health_checks",
                return_value=_mock_health_results(),
            ),
            patch(
                "ops.health.scheduler.collect_resources", return_value=_mock_resources()
            ),
        ):
            await scheduler.start()
            await scheduler.stop()
            assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_double_start_is_idempotent(self, repo):
        """Calling start() twice does not create a second task."""
        scheduler = HealthScheduler(repository=repo, interval_seconds=300)
        with (
            patch(
                "ops.health.scheduler.run_all_health_checks",
                return_value=_mock_health_results(),
            ),
            patch(
                "ops.health.scheduler.collect_resources", return_value=_mock_resources()
            ),
        ):
            await scheduler.start()
            task1 = scheduler._task
            await scheduler.start()
            task2 = scheduler._task
            assert task1 is task2
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self, repo):
        """Calling stop() without start() does not raise."""
        scheduler = HealthScheduler(repository=repo, interval_seconds=300)
        await scheduler.stop()
        assert scheduler.is_running is False


class TestHealthSchedulerTick:
    """Tests for tick behavior (health check execution and persistence)."""

    @pytest.mark.asyncio
    async def test_tick_persists_health_results(self, repo, collection):
        """A single tick saves health snapshots to MongoDB."""
        scheduler = HealthScheduler(repository=repo, interval_seconds=300)
        with (
            patch(
                "ops.health.scheduler.run_all_health_checks",
                return_value=_mock_health_results(),
            ),
            patch(
                "ops.health.scheduler.collect_resources", return_value=_mock_resources()
            ),
        ):
            await scheduler._tick()

        assert collection.count_documents({}) == 2
        doc = collection.find_one({"service": "mongodb"})
        assert doc["status"] == "ok"
        assert "resources" in doc
        assert doc["resources"]["cpu_pct"] == 25.0

    @pytest.mark.asyncio
    async def test_tick_includes_resource_snapshot(self, repo, collection):
        """Each persisted document includes the resource snapshot."""
        scheduler = HealthScheduler(repository=repo, interval_seconds=300)
        with (
            patch(
                "ops.health.scheduler.run_all_health_checks",
                return_value=_mock_health_results(),
            ),
            patch(
                "ops.health.scheduler.collect_resources", return_value=_mock_resources()
            ),
        ):
            await scheduler._tick()

        for doc in collection.find():
            assert "resources" in doc
            assert doc["resources"]["mem_pct"] == 60.0

    @pytest.mark.asyncio
    async def test_tick_handles_exception_gracefully(self, repo, collection):
        """If health checks raise, tick logs error but does not crash."""
        scheduler = HealthScheduler(repository=repo, interval_seconds=300)
        with patch(
            "ops.health.scheduler.run_all_health_checks",
            side_effect=RuntimeError("network timeout"),
        ):
            await scheduler._tick()

        assert collection.count_documents({}) == 0

    @pytest.mark.asyncio
    async def test_scheduler_runs_tick_on_start(self, repo, collection):
        """After start(), at least one tick executes before we stop."""
        scheduler = HealthScheduler(repository=repo, interval_seconds=300)
        with (
            patch(
                "ops.health.scheduler.run_all_health_checks",
                return_value=_mock_health_results(),
            ),
            patch(
                "ops.health.scheduler.collect_resources", return_value=_mock_resources()
            ),
        ):
            await scheduler.start()
            await asyncio.sleep(0.2)
            await scheduler.stop()

        assert collection.count_documents({}) >= 2


class TestHealthSchedulerConfig:
    """Tests for configuration behavior."""

    def test_uses_provided_interval(self, repo):
        """When interval_seconds is passed, scheduler uses it."""
        scheduler = HealthScheduler(repository=repo, interval_seconds=120)
        assert scheduler.interval_seconds == 120

    def test_reads_interval_from_settings(self, repo):
        """When no interval_seconds, reads from watchtower config."""
        with patch.dict(
            "config.settings_loader.settings",
            {"watchtower": {"health_check_interval_seconds": 45}},
        ):
            scheduler = HealthScheduler(repository=repo)
            assert scheduler.interval_seconds == 45

    def test_defaults_to_60_seconds(self, repo):
        """When no config at all, defaults to 60 seconds."""
        with patch.dict(
            "config.settings_loader.settings",
            {"watchtower": {}},
        ):
            scheduler = HealthScheduler(repository=repo)
            assert scheduler.interval_seconds == 60
