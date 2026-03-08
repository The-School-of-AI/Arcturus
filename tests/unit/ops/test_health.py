"""Unit tests for ops.health module."""
import pytest
from unittest.mock import patch, MagicMock

from ops.health import (
    HealthResult,
    check_mongodb,
    check_qdrant,
    check_ollama,
    check_mcp,
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
        """When Qdrant /health returns 200, returns status ok."""
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


class TestRunAllHealthChecks:
    """Tests for run_all_health_checks behavior."""

    def test_returns_four_services(self):
        """run_all_health_checks returns exactly four service results."""
        with (
            patch("ops.health.check_mongodb", return_value=HealthResult("mongodb", "ok")),
            patch("ops.health.check_qdrant", return_value=HealthResult("qdrant", "ok")),
            patch("ops.health.check_ollama", return_value=HealthResult("ollama", "ok")),
            patch("ops.health.check_mcp", return_value=HealthResult("mcp_gateway", "ok")),
        ):
            results = run_all_health_checks()
        services = [r.service for r in results]
        assert "mongodb" in services
        assert "qdrant" in services
        assert "ollama" in services
        assert "mcp_gateway" in services
        assert len(results) == 4
