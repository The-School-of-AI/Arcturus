"""Unit tests for ops.health module."""

import os
import sys

import pytest
from unittest.mock import patch, MagicMock

from ops.health import (
    HealthResult,
    ResourceSnapshot,
    check_mongodb,
    check_qdrant,
    check_ollama,
    check_mcp,
    check_neo4j,
    check_agent_core,
    collect_resources,
    run_all_health_checks,
)


class TestHealthResult:
    """Tests for HealthResult dataclass."""

    def test_to_dict_includes_all_fields(self):
        """HealthResult.to_dict() returns service, status, latency_ms, details."""
        r = HealthResult(service="test", status="ok", latency_ms=12.5, details="ok")
        d = r.to_dict()
        assert d["service"] == "test"
        assert d["status"] == "ok"
        assert d["latency_ms"] == 12.5
        assert d["details"] == "ok"


class TestCheckMongodb:
    """Tests for check_mongodb behavior."""

    def test_returns_ok_when_ping_succeeds(self):
        """When MongoDB ping succeeds, returns status ok."""
        mock_client = MagicMock()
        with patch("pymongo.MongoClient", return_value=mock_client):
            result = check_mongodb()
        assert result.service == "mongodb"
        assert result.status == "ok"
        assert result.latency_ms is not None

    def test_returns_down_when_connection_fails(self):
        """When MongoDB connection fails, returns status down."""
        with patch("pymongo.MongoClient", side_effect=Exception("Connection refused")):
            result = check_mongodb()
        assert result.service == "mongodb"
        assert result.status == "down"
        assert result.details == "Connection refused"


class TestCheckQdrant:
    """Tests for check_qdrant behavior."""

    def test_returns_ok_when_health_endpoint_returns_200(self):
        """When Qdrant /healthz returns 200, returns status ok."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_client)
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("httpx.Client", return_value=mock_cm):
            result = check_qdrant()
        assert result.service == "qdrant"
        assert result.status == "ok"

    def test_returns_down_when_request_fails(self):
        """When HTTP request fails, returns status down."""
        with patch("httpx.Client", side_effect=Exception("Connection refused")):
            result = check_qdrant()
        assert result.service == "qdrant"
        assert result.status == "down"


class TestCheckOllama:
    """Tests for check_ollama behavior."""

    def test_returns_ok_when_api_tags_returns_200(self):
        """When Ollama /api/tags returns 200, returns status ok."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_client)
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("httpx.Client", return_value=mock_cm):
            result = check_ollama()
        assert result.service == "ollama"
        assert result.status == "ok"

    def test_returns_down_when_request_fails(self):
        """When HTTP request fails, returns status down."""
        with patch("httpx.Client", side_effect=Exception("Connection refused")):
            result = check_ollama()
        assert result.service == "ollama"
        assert result.status == "down"


class TestCheckMcp:
    """Tests for check_mcp behavior."""

    def test_returns_ok_when_sessions_exist(self):
        """When MultiMCP has connected sessions, returns status ok."""
        mock_mcp = MagicMock()
        mock_mcp.sessions = {"server_a": MagicMock(), "server_b": MagicMock()}
        mock_mcp.server_configs = {}
        with patch("shared.state.get_multi_mcp", return_value=mock_mcp):
            result = check_mcp()
        assert result.service == "mcp_gateway"
        assert result.status == "ok"
        assert "2 server(s)" in (result.details or "")

    def test_returns_ok_when_no_servers_configured(self):
        """When no MCP servers configured, returns status ok."""
        mock_mcp = MagicMock()
        mock_mcp.sessions = {}
        mock_mcp.server_configs = {}
        with patch("shared.state.get_multi_mcp", return_value=mock_mcp):
            result = check_mcp()
        assert result.service == "mcp_gateway"
        assert result.status == "ok"


class TestCheckNeo4j:
    """Tests for check_neo4j behavior."""

    def test_returns_ok_disabled_when_env_not_set(self):
        """When NEO4J_ENABLED is not set, returns ok with 'Disabled' details."""
        with patch.dict("os.environ", {}, clear=False):
            env = dict(os.environ)
            env.pop("NEO4J_ENABLED", None)
            with patch.dict("os.environ", env, clear=True):
                result = check_neo4j()
        assert result.service == "neo4j"
        assert result.status == "ok"
        assert "Disabled" in (result.details or "")

    def test_returns_down_when_password_not_set(self):
        """When NEO4J_ENABLED but no password, returns down."""
        with patch.dict("os.environ", {"NEO4J_ENABLED": "true", "NEO4J_PASSWORD": ""}):
            result = check_neo4j()
        assert result.service == "neo4j"
        assert result.status == "down"
        assert "PASSWORD" in (result.details or "")

    def test_returns_ok_when_connectivity_succeeds(self):
        """When Neo4j verify_connectivity succeeds, returns ok with latency."""
        mock_driver = MagicMock()
        with (
            patch.dict(
                "os.environ",
                {
                    "NEO4J_ENABLED": "true",
                    "NEO4J_URI": "bolt://localhost:7687",
                    "NEO4J_USER": "neo4j",
                    "NEO4J_PASSWORD": "testpass",
                },
            ),
            patch("neo4j.GraphDatabase.driver", return_value=mock_driver),
        ):
            result = check_neo4j()
        assert result.service == "neo4j"
        assert result.status == "ok"
        assert result.latency_ms is not None
        mock_driver.verify_connectivity.assert_called_once()
        mock_driver.close.assert_called_once()

    def test_returns_down_when_connection_fails(self):
        """When Neo4j connection fails, returns down with error details."""
        with (
            patch.dict(
                "os.environ",
                {
                    "NEO4J_ENABLED": "true",
                    "NEO4J_PASSWORD": "testpass",
                },
            ),
            patch(
                "neo4j.GraphDatabase.driver",
                side_effect=Exception("Connection refused"),
            ),
        ):
            result = check_neo4j()
        assert result.service == "neo4j"
        assert result.status == "down"
        assert "Connection refused" in (result.details or "")


class TestCheckAgentCore:
    """Tests for check_agent_core behavior."""

    def test_returns_ok_idle_when_no_active_loops(self):
        """When active_loops is empty, returns ok with 'Idle'."""
        with patch("shared.state.active_loops", {}):
            result = check_agent_core()
        assert result.service == "agent_core"
        assert result.status == "ok"
        assert "Idle" in (result.details or "")

    def test_returns_ok_with_count_when_loops_active(self):
        """When active_loops has entries, returns ok with loop count."""
        with patch(
            "shared.state.active_loops", {"run_1": MagicMock(), "run_2": MagicMock()}
        ):
            result = check_agent_core()
        assert result.service == "agent_core"
        assert result.status == "ok"
        assert "2 active loop(s)" in (result.details or "")

    def test_returns_down_when_import_fails(self):
        """When shared.state import fails, returns down."""
        with patch("ops.health.check_agent_core", wraps=check_agent_core):
            with patch.dict("sys.modules", {"shared.state": None}):
                result = check_agent_core()
        assert result.service == "agent_core"
        assert result.status == "down"


class TestResourceSnapshot:
    """Tests for ResourceSnapshot dataclass."""

    def test_to_dict_includes_all_fields(self):
        """ResourceSnapshot.to_dict() returns all resource fields."""
        snap = ResourceSnapshot(
            cpu_pct=25.0,
            mem_pct=60.0,
            disk_pct=45.0,
            mem_used_mb=8192.0,
            mem_total_mb=16384.0,
            disk_used_gb=100.0,
            disk_total_gb=500.0,
        )
        d = snap.to_dict()
        assert d["cpu_pct"] == 25.0
        assert d["mem_pct"] == 60.0
        assert d["disk_pct"] == 45.0
        assert d["mem_used_mb"] == 8192.0
        assert d["mem_total_mb"] == 16384.0
        assert d["disk_used_gb"] == 100.0
        assert d["disk_total_gb"] == 500.0


class TestCollectResources:
    """Tests for collect_resources behavior."""

    def test_returns_resource_snapshot_with_valid_values(self):
        """collect_resources returns a ResourceSnapshot with realistic percentages."""
        mock_mem = MagicMock()
        mock_mem.percent = 62.5
        mock_mem.used = 8 * 1024 * 1024 * 1024
        mock_mem.total = 16 * 1024 * 1024 * 1024

        mock_disk = MagicMock()
        mock_disk.percent = 45.0
        mock_disk.used = 100 * 1024**3
        mock_disk.total = 500 * 1024**3

        with (
            patch("psutil.cpu_percent", return_value=30.0),
            patch("psutil.virtual_memory", return_value=mock_mem),
            patch("psutil.disk_usage", return_value=mock_disk),
        ):
            snap = collect_resources()

        assert isinstance(snap, ResourceSnapshot)
        assert snap.cpu_pct == 30.0
        assert snap.mem_pct == 62.5
        assert snap.disk_pct == 45.0
        assert snap.mem_used_mb == round(8 * 1024, 1)
        assert snap.mem_total_mb == round(16 * 1024, 1)
        assert snap.disk_used_gb == 100.0
        assert snap.disk_total_gb == 500.0

    def test_returns_snapshot_even_with_zero_values(self):
        """collect_resources handles zero values gracefully."""
        mock_mem = MagicMock()
        mock_mem.percent = 0.0
        mock_mem.used = 0
        mock_mem.total = 0

        mock_disk = MagicMock()
        mock_disk.percent = 0.0
        mock_disk.used = 0
        mock_disk.total = 0

        with (
            patch("psutil.cpu_percent", return_value=0.0),
            patch("psutil.virtual_memory", return_value=mock_mem),
            patch("psutil.disk_usage", return_value=mock_disk),
        ):
            snap = collect_resources()

        assert snap.cpu_pct == 0.0
        assert snap.mem_pct == 0.0
        assert snap.disk_pct == 0.0


class TestRunAllHealthChecks:
    """Tests for run_all_health_checks behavior."""

    def test_returns_seven_services(self):
        """run_all_health_checks returns exactly seven service results."""
        with (
            patch(
                "ops.health.check_mongodb", return_value=HealthResult("mongodb", "ok")
            ),
            patch("ops.health.check_qdrant", return_value=HealthResult("qdrant", "ok")),
            patch("ops.health.check_ollama", return_value=HealthResult("ollama", "ok")),
            patch(
                "ops.health.check_mcp", return_value=HealthResult("mcp_gateway", "ok")
            ),
            patch("ops.health.check_neo4j", return_value=HealthResult("neo4j", "ok")),
            patch(
                "ops.health.checks.get_voice_status",
                return_value=(True, None),
            ),
            patch(
                "ops.health.check_agent_core",
                return_value=HealthResult("agent_core", "ok"),
            ),
        ):
            results = run_all_health_checks()
        services = [r.service for r in results]
        assert "mongodb" in services
        assert "qdrant" in services
        assert "ollama" in services
        assert "mcp_gateway" in services
        assert "neo4j" in services
        assert "voice_pipeline" in services
        assert "agent_core" in services
        assert len(results) == 7
