"""P14 Watchtower acceptance test fixtures.

Provides TestClient with mocked MongoDB and health checks so tests run without
external services (MongoDB, Qdrant, Ollama).

P14.4: Also mocks feature flags, diagnostics, throttle, cache, and config.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import json
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import admin as admin_router


def _make_mock_spans_collection():
    """Create a mock MongoDB spans collection for admin API tests."""

    def _aggregate(pipeline):
        # Infer endpoint from pipeline structure.
        # Order matters: check most specific patterns first.
        pipeline_str = str(pipeline)
        has_trace_group = "'_id': '$trace_id'" in pipeline_str
        has_session_group = "attributes.session_id" in pipeline_str
        has_metrics_group = "total_traces" in pipeline_str
        has_cost_group = "total_cost_usd" in pipeline_str
        has_error_group = "$ifNull" in pipeline_str and "trace_ids" in pipeline_str

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
        if has_session_group:
            # list_sessions
            return iter(
                [
                    {
                        "_id": "sess-001",
                        "start_time": datetime.now(timezone.utc),
                        "end_time": datetime.now(timezone.utc),
                        "span_count": 10,
                        "total_cost_usd": 0.05,
                        "agents": ["ThinkerAgent", "CoderAgent"],
                    }
                ]
            )
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
def admin_client(tmp_path):
    """TestClient for admin API with mocked MongoDB, health, and P14.4 admin controls."""
    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api")

    mock_coll = _make_mock_spans_collection()
    mock_health_repo = _make_mock_health_repo()
    mock_resources = _make_mock_resource_snapshot()

    # P14.4: Create temp feature flags file for isolation
    flags_path = tmp_path / "feature_flags.json"
    flags_path.write_text(json.dumps({
        "deep_research": True,
        "voice_wake": True,
        "multi_agent": False,
        "cost_tracking": True,
        "semantic_cache": True,
        "health_scheduler": True,
    }))

    # P14.4: Create temp settings defaults for config/diff
    defaults_path = tmp_path / "settings.defaults.json"
    defaults_path.write_text(json.dumps({
        "models": {"default": "gemini-2.5-flash"},
        "agent": {"max_cost_per_run": 0.50},
    }))

    # P14.4: Mock diagnostics
    mock_diagnostics = {
        "overall": "pass",
        "summary": {"pass": 5, "warn": 1, "fail": 0},
        "checks": [
            {"check": "python_version", "status": "pass", "message": "Python 3.11.5"},
            {"check": "config_file", "status": "pass", "message": "settings.json is valid"},
        ],
    }

    # P14.4: Mock throttle
    mock_throttle = {
        "hourly": {"window": "hourly", "hours": 1, "spent_usd": 0.1, "budget_usd": 2.0, "remaining_usd": 1.9, "usage_pct": 5.0, "throttled": False},
        "daily": {"window": "daily", "hours": 24, "spent_usd": 0.5, "budget_usd": 10.0, "remaining_usd": 9.5, "usage_pct": 5.0, "throttled": False},
        "allowed": True,
        "reason": "Within budget",
    }

    # Import and create a FeatureFlagStore pointing at temp file
    from ops.admin.feature_flags import FeatureFlagStore
    temp_flag_store = FeatureFlagStore(path=flags_path)

    # P14.5: Mock audit logger
    mock_audit_logger = MagicMock()
    mock_audit_logger.query.return_value = [
        {
            "timestamp": "2026-03-14T10:00:00",
            "actor": "admin",
            "action": "feature_toggle",
            "resource": "flag:voice_wake",
            "old_value": True,
            "new_value": False,
            "context": {},
        },
        {
            "timestamp": "2026-03-14T09:30:00",
            "actor": "admin",
            "action": "cache_flush",
            "resource": "cache:settings",
            "old_value": None,
            "new_value": "flushed",
            "context": {},
        },
    ]

    # P14.5: Mock data manager
    mock_data_manager = MagicMock()
    mock_data_manager.export.return_value = {
        "session_id": "test-session",
        "exported_at": "2026-03-14T10:00:00",
        "stores": {
            "session_files": {"count": 1, "data": [{"path": "test.json", "content": {}}]},
            "mongodb_spans": {"count": 5, "data": []},
            "qdrant_vectors": {"count": 0, "data": []},
            "neo4j_graph": {"count": 0, "data": None},
            "chronicle_checkpoints": {"count": 0, "data": {"checkpoints": [], "events": []}},
            "audit_log": {"count": 0, "data": []},
        },
    }
    mock_data_manager.delete.side_effect = lambda sid: {
        "session_id": sid,
        "deleted_at": "2026-03-14T10:00:00",
        "stores": {
            "session_files": {"deleted": 1},
            "mongodb_spans": {"deleted": 5},
            "qdrant_vectors": {"deleted": 0},
            "neo4j_graph": {"deleted": 0},
            "chronicle_checkpoints": {"deleted": 0},
            "audit_log": {"deleted": 0},
        },
    }

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
        # P14.4 mocks
        patch("routers.admin.flag_store" if False else "ops.admin.feature_flags.flag_store", temp_flag_store),
        patch("ops.admin.diagnostics.run_diagnostics", return_value=mock_diagnostics),
        # P14.5 mocks
        patch("ops.audit.audit_logger", mock_audit_logger),
        patch.object(admin_router, "_get_data_manager", return_value=mock_data_manager),
    ):
        with TestClient(app) as client:
            yield client


@pytest.fixture
def admin_client_with_auth(tmp_path):
    """TestClient with admin API key configured for auth testing."""
    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api")

    mock_coll = _make_mock_spans_collection()

    # Configure admin_api_key in settings
    test_settings = {
        "watchtower": {
            "enabled": False,
            "admin_api_key": "test-secret-key-123",
        }
    }

    with (
        patch.object(admin_router, "_get_spans_collection", return_value=mock_coll),
        patch("config.settings_loader.settings", test_settings),
        patch("routers.admin.settings", test_settings),
    ):
        with TestClient(app) as client:
            yield client
