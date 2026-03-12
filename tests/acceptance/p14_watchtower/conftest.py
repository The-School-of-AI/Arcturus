"""P14 Watchtower acceptance test fixtures.

Provides TestClient with mocked MongoDB and health checks so tests run without
external services (MongoDB, Qdrant, Ollama).
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import admin as admin_router


def _make_mock_spans_collection():
    """Create a mock MongoDB spans collection for admin API tests."""

    def _aggregate(pipeline):
        # Infer endpoint from pipeline structure (check most specific first)
        pipeline_str = str(pipeline)
        has_cost_group = "total_cost_usd" in pipeline_str
        has_metrics_group = "total_traces" in pipeline_str
        has_error_group = "$ifNull" in pipeline_str and "trace_ids" in pipeline_str
        has_trace_group = "$trace_id" in pipeline_str and "trace_id" in pipeline_str

        if has_cost_group:
            # get_cost_summary
            return iter(
                [
                    {
                        "total_cost_usd": 0.05,
                        "trace_ids": ["t1", "t2"],
                        "by_agent": [{"agent": "ThinkerAgent", "cost": "0.03"}],
                        "by_model": [{"model": "gemini-2.5-flash", "cost": "0.03"}],
                    }
                ]
            )
        if has_metrics_group:
            # get_metrics_summary
            return iter(
                [
                    {
                        "total_traces": 10,
                        "avg_duration_ms": 200.5,
                        "error_count": 1,
                    }
                ]
            )
        if has_error_group:
            # get_errors_summary
            return iter(
                [
                    {"_id": "llm.generate", "count": 2, "trace_ids": ["t1", "t2"]},
                ]
            )
        if has_trace_group:
            # get_traces
            return iter(
                [
                    {
                        "_id": "abc123def456",
                        "trace_id": "abc123def456",
                        "start_time": datetime.now(timezone.utc),
                        "duration_ms": 150.5,
                        "has_error": False,
                        "span_count": 5,
                        "session_id": "sess-1",
                        "cost_usd": 0.001234,
                        "input_tokens": 100,
                        "output_tokens": 50,
                    }
                ]
            )
        return iter([])

    def _find_spans(trace_id="abc123"):
        return [
            {
                "trace_id": trace_id,
                "span_id": "span1",
                "name": "run.execute",
                "start_time": datetime.now(timezone.utc),
                "end_time": datetime.now(timezone.utc),
                "duration_ms": 100,
                "status": "ok",
            }
        ]

    mock_coll = MagicMock()
    mock_coll.aggregate.side_effect = _aggregate
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = _find_spans()
    mock_coll.find.return_value = mock_cursor
    return mock_coll


def _make_mock_health_repo():
    """Create a mock HealthRepository for health history/uptime endpoints."""
    mock_repo = MagicMock()
    mock_repo.get_history.return_value = [
        {"timestamp": "2025-03-11T10:00:00", "service": "mongodb", "status": "ok", "latency_ms": 5.0, "details": None},
        {"timestamp": "2025-03-11T10:00:00", "service": "qdrant", "status": "ok", "latency_ms": 3.0, "details": None},
    ]
    mock_repo.compute_all_uptimes.return_value = [
        {"service": "mongodb", "hours": 24, "uptime_pct": 99.5, "total_checks": 100, "ok_checks": 99, "degraded_checks": 1, "down_checks": 0, "avg_latency_ms": 5.0},
        {"service": "qdrant", "hours": 24, "uptime_pct": 100.0, "total_checks": 100, "ok_checks": 100, "degraded_checks": 0, "down_checks": 0, "avg_latency_ms": 3.0},
    ]
    return mock_repo


def _make_mock_resource_snapshot():
    """Create a mock ResourceSnapshot for /health/resources endpoint."""
    mock_snap = MagicMock()
    mock_snap.to_dict.return_value = {
        "cpu_pct": 25.0, "mem_pct": 60.0, "disk_pct": 45.0,
        "mem_used_mb": 8192.0, "mem_total_mb": 16384.0,
        "disk_used_gb": 100.0, "disk_total_gb": 500.0,
    }
    return mock_snap


@pytest.fixture
def admin_client():
    """TestClient for admin API with mocked MongoDB and health."""
    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api")

    mock_coll = _make_mock_spans_collection()
    mock_health_repo = _make_mock_health_repo()
    mock_resources = _make_mock_resource_snapshot()

    with (
        patch.object(admin_router, "_get_spans_collection", return_value=mock_coll),
        patch.object(admin_router, "_get_health_repo", return_value=mock_health_repo),
        patch(
            "ops.health.run_all_health_checks",
            return_value=[
                type("R", (), {"to_dict": lambda self: {"service": "mongodb", "status": "ok", "latency_ms": 1.0, "details": None}})(),
                type("R", (), {"to_dict": lambda self: {"service": "qdrant", "status": "ok", "latency_ms": 2.0, "details": None}})(),
                type("R", (), {"to_dict": lambda self: {"service": "ollama", "status": "ok", "latency_ms": 3.0, "details": None}})(),
                type("R", (), {"to_dict": lambda self: {"service": "mcp_gateway", "status": "ok", "latency_ms": None, "details": "1 server(s)"}})(),
            ],
        ),
        patch("ops.health.collect_resources", return_value=mock_resources),
    ):
        with TestClient(app) as client:
            yield client
