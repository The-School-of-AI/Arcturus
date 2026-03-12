"""Unit tests for ops.health.repository.HealthRepository."""

from datetime import datetime, timedelta

import mongomock
import pytest

from ops.health import HealthResult, ResourceSnapshot
from ops.health.repository import HealthRepository


@pytest.fixture()
def collection():
    """Fresh mongomock collection for each test."""
    client = mongomock.MongoClient()
    return client["watchtower"]["health_checks"]


@pytest.fixture()
def repo(collection):
    """HealthRepository backed by mongomock."""
    return HealthRepository(collection)


class TestSaveSnapshot:
    """Tests for HealthRepository.save_snapshot behavior."""

    def test_inserts_one_doc_per_service(self, repo, collection):
        """Each HealthResult becomes one MongoDB document."""
        results = [
            HealthResult(service="mongodb", status="ok", latency_ms=5.0),
            HealthResult(service="qdrant", status="down", details="timeout"),
        ]
        count = repo.save_snapshot(results)
        assert count == 2
        assert collection.count_documents({}) == 2

    def test_document_has_expected_fields(self, repo, collection):
        """Saved document contains timestamp, service, status, latency, details."""
        results = [
            HealthResult(
                service="ollama",
                status="degraded",
                latency_ms=100.0,
                details="HTTP 503",
            )
        ]
        repo.save_snapshot(results)

        doc = collection.find_one({"service": "ollama"})
        assert doc is not None
        assert isinstance(doc["timestamp"], datetime)
        assert doc["status"] == "degraded"
        assert doc["latency_ms"] == 100.0
        assert doc["details"] == "HTTP 503"

    def test_includes_resources_when_provided(self, repo, collection):
        """When ResourceSnapshot is given, each doc gets a resources sub-document."""
        results = [HealthResult(service="mongodb", status="ok")]
        resources = ResourceSnapshot(cpu_pct=30.0, mem_pct=60.0, disk_pct=45.0)
        repo.save_snapshot(results, resources=resources)

        doc = collection.find_one({"service": "mongodb"})
        assert "resources" in doc
        assert doc["resources"]["cpu_pct"] == 30.0
        assert doc["resources"]["mem_pct"] == 60.0
        assert doc["resources"]["disk_pct"] == 45.0

    def test_omits_resources_when_not_provided(self, repo, collection):
        """When no ResourceSnapshot, documents have no resources key."""
        results = [HealthResult(service="mongodb", status="ok")]
        repo.save_snapshot(results)

        doc = collection.find_one({"service": "mongodb"})
        assert "resources" not in doc

    def test_returns_zero_for_empty_results(self, repo, collection):
        """Passing an empty list inserts nothing and returns 0."""
        count = repo.save_snapshot([])
        assert count == 0
        assert collection.count_documents({}) == 0


class TestGetHistory:
    """Tests for HealthRepository.get_history behavior."""

    def test_returns_recent_snapshots(self, repo, collection):
        """get_history returns documents within the time window."""
        now = datetime.utcnow()
        collection.insert_many(
            [
                {
                    "timestamp": now - timedelta(hours=1),
                    "service": "mongodb",
                    "status": "ok",
                    "latency_ms": 5.0,
                    "details": None,
                },
                {
                    "timestamp": now - timedelta(hours=2),
                    "service": "mongodb",
                    "status": "down",
                    "latency_ms": None,
                    "details": "err",
                },
                {
                    "timestamp": now - timedelta(hours=48),
                    "service": "mongodb",
                    "status": "ok",
                    "latency_ms": 3.0,
                    "details": None,
                },
            ]
        )

        history = repo.get_history(hours=24, service="mongodb")
        assert len(history) == 2
        assert history[0]["status"] == "ok"
        assert history[1]["status"] == "down"

    def test_filters_by_service(self, repo, collection):
        """get_history only returns snapshots for the requested service."""
        now = datetime.utcnow()
        collection.insert_many(
            [
                {
                    "timestamp": now,
                    "service": "mongodb",
                    "status": "ok",
                    "latency_ms": None,
                    "details": None,
                },
                {
                    "timestamp": now,
                    "service": "qdrant",
                    "status": "ok",
                    "latency_ms": None,
                    "details": None,
                },
            ]
        )

        history = repo.get_history(hours=24, service="qdrant")
        assert len(history) == 1
        assert history[0]["service"] == "qdrant"

    def test_returns_all_services_when_no_filter(self, repo, collection):
        """Without service filter, returns all services."""
        now = datetime.utcnow()
        collection.insert_many(
            [
                {
                    "timestamp": now,
                    "service": "mongodb",
                    "status": "ok",
                    "latency_ms": None,
                    "details": None,
                },
                {
                    "timestamp": now,
                    "service": "qdrant",
                    "status": "ok",
                    "latency_ms": None,
                    "details": None,
                },
            ]
        )

        history = repo.get_history(hours=24)
        assert len(history) == 2

    def test_respects_limit(self, repo, collection):
        """get_history caps results at the limit parameter."""
        now = datetime.utcnow()
        docs = [
            {
                "timestamp": now - timedelta(minutes=i),
                "service": "mongodb",
                "status": "ok",
                "latency_ms": None,
                "details": None,
            }
            for i in range(10)
        ]
        collection.insert_many(docs)

        history = repo.get_history(hours=24, service="mongodb", limit=3)
        assert len(history) == 3

    def test_timestamps_are_iso_strings(self, repo, collection):
        """Returned timestamps are ISO-formatted strings, not datetime objects."""
        now = datetime.utcnow()
        collection.insert_one(
            {
                "timestamp": now,
                "service": "mongodb",
                "status": "ok",
                "latency_ms": None,
                "details": None,
            }
        )

        history = repo.get_history(hours=24)
        assert len(history) == 1
        assert isinstance(history[0]["timestamp"], str)


class TestComputeUptime:
    """Tests for HealthRepository.compute_uptime behavior."""

    def test_computes_100_percent_when_all_ok(self, repo, collection):
        """If all checks are ok, uptime is 100%."""
        now = datetime.utcnow()
        docs = [
            {
                "timestamp": now - timedelta(minutes=i),
                "service": "mongodb",
                "status": "ok",
                "latency_ms": 5.0,
            }
            for i in range(10)
        ]
        collection.insert_many(docs)

        result = repo.compute_uptime("mongodb", hours=24)
        assert result["uptime_pct"] == 100.0
        assert result["total_checks"] == 10
        assert result["ok_checks"] == 10
        assert result["down_checks"] == 0

    def test_computes_partial_uptime(self, repo, collection):
        """Mixed statuses produce correct uptime percentage."""
        now = datetime.utcnow()
        statuses = ["ok"] * 9 + ["down"]
        docs = [
            {
                "timestamp": now - timedelta(minutes=i),
                "service": "qdrant",
                "status": s,
                "latency_ms": None,
            }
            for i, s in enumerate(statuses)
        ]
        collection.insert_many(docs)

        result = repo.compute_uptime("qdrant", hours=24)
        assert result["uptime_pct"] == 90.0
        assert result["total_checks"] == 10
        assert result["ok_checks"] == 9
        assert result["down_checks"] == 1

    def test_counts_degraded_separately(self, repo, collection):
        """Degraded checks are counted separately and do not count as ok."""
        now = datetime.utcnow()
        docs = [
            {"timestamp": now, "service": "ollama", "status": "ok", "latency_ms": None},
            {
                "timestamp": now,
                "service": "ollama",
                "status": "degraded",
                "latency_ms": None,
            },
            {
                "timestamp": now,
                "service": "ollama",
                "status": "down",
                "latency_ms": None,
            },
        ]
        collection.insert_many(docs)

        result = repo.compute_uptime("ollama", hours=24)
        assert result["total_checks"] == 3
        assert result["ok_checks"] == 1
        assert result["degraded_checks"] == 1
        assert result["down_checks"] == 1
        assert result["uptime_pct"] == pytest.approx(33.33, rel=0.01)

    def test_returns_defaults_when_no_data(self, repo):
        """With no snapshots, returns 100% uptime and zero counts."""
        result = repo.compute_uptime("nonexistent", hours=24)
        assert result["uptime_pct"] == 100.0
        assert result["total_checks"] == 0
        assert result["ok_checks"] == 0

    def test_excludes_snapshots_outside_time_window(self, repo, collection):
        """Only snapshots within the hours window are counted."""
        now = datetime.utcnow()
        collection.insert_many(
            [
                {
                    "timestamp": now - timedelta(hours=1),
                    "service": "mongodb",
                    "status": "ok",
                    "latency_ms": None,
                },
                {
                    "timestamp": now - timedelta(hours=48),
                    "service": "mongodb",
                    "status": "down",
                    "latency_ms": None,
                },
            ]
        )

        result = repo.compute_uptime("mongodb", hours=24)
        assert result["total_checks"] == 1
        assert result["ok_checks"] == 1
        assert result["uptime_pct"] == 100.0

    def test_includes_average_latency(self, repo, collection):
        """Uptime result includes average latency across all checks."""
        now = datetime.utcnow()
        collection.insert_many(
            [
                {
                    "timestamp": now,
                    "service": "mongodb",
                    "status": "ok",
                    "latency_ms": 10.0,
                },
                {
                    "timestamp": now,
                    "service": "mongodb",
                    "status": "ok",
                    "latency_ms": 20.0,
                },
            ]
        )

        result = repo.compute_uptime("mongodb", hours=24)
        assert result["avg_latency_ms"] == 15.0


class TestComputeAllUptimes:
    """Tests for HealthRepository.compute_all_uptimes behavior."""

    def test_returns_uptime_for_each_service(self, repo, collection):
        """compute_all_uptimes returns one entry per distinct service."""
        now = datetime.utcnow()
        collection.insert_many(
            [
                {
                    "timestamp": now,
                    "service": "mongodb",
                    "status": "ok",
                    "latency_ms": None,
                },
                {
                    "timestamp": now,
                    "service": "qdrant",
                    "status": "ok",
                    "latency_ms": None,
                },
                {
                    "timestamp": now,
                    "service": "ollama",
                    "status": "down",
                    "latency_ms": None,
                },
            ]
        )

        uptimes = repo.compute_all_uptimes(hours=24)
        services = [u["service"] for u in uptimes]
        assert "mongodb" in services
        assert "qdrant" in services
        assert "ollama" in services
        assert len(uptimes) == 3

    def test_returns_empty_list_when_no_data(self, repo):
        """With no snapshots, returns empty list."""
        uptimes = repo.compute_all_uptimes(hours=24)
        assert uptimes == []
