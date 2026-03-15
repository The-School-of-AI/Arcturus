"""Unit tests for ops.health.checks – voice pipeline health check."""

import pytest
from unittest.mock import patch

from ops.health.checks import check_voice, run_all_health_checks
from ops.health.models import HealthResult


class TestCheckVoice:
    """Tests for the check_voice health check."""

    def test_returns_ok_when_pipeline_is_ready(self):
        with patch(
            "ops.health.checks.get_voice_status", return_value=(True, None)
        ):
            result = check_voice()

        assert result.service == "voice_pipeline"
        assert result.status == "ok"
        assert result.details is None

    def test_returns_down_with_error_when_startup_failed(self):
        error_msg = "wake engine failed: PICOVOICE_ACCESS_KEY not found"
        with patch(
            "ops.health.checks.get_voice_status",
            return_value=(False, error_msg),
        ):
            result = check_voice()

        assert result.service == "voice_pipeline"
        assert result.status == "down"
        assert "PICOVOICE_ACCESS_KEY" in result.details

    def test_returns_down_not_initialized_when_never_started(self):
        with patch(
            "ops.health.checks.get_voice_status", return_value=(False, None)
        ):
            result = check_voice()

        assert result.service == "voice_pipeline"
        assert result.status == "down"
        assert result.details == "Not initialized"

    def test_handles_import_error_gracefully(self):
        with patch(
            "ops.health.checks.get_voice_status",
            side_effect=ImportError("shared.state not available"),
        ):
            result = check_voice()

        assert result.service == "voice_pipeline"
        assert result.status == "down"


class TestRunAllHealthChecksIncludesVoice:
    """Verify voice_pipeline is included in the aggregated health check list."""

    def test_voice_pipeline_present_in_results(self):
        mock_result = HealthResult(service="mock", status="ok")
        with (
            patch("ops.health.checks.check_mongodb", return_value=mock_result),
            patch("ops.health.checks.check_qdrant", return_value=mock_result),
            patch("ops.health.checks.check_ollama", return_value=mock_result),
            patch("ops.health.checks.check_mcp", return_value=mock_result),
            patch("ops.health.checks.check_neo4j", return_value=mock_result),
            patch("ops.health.checks.check_agent_core", return_value=mock_result),
            patch(
                "ops.health.checks.get_voice_status",
                return_value=(False, "missing key"),
            ),
        ):
            results = run_all_health_checks()

        services = [r.service for r in results]
        assert "voice_pipeline" in services

        voice = next(r for r in results if r.service == "voice_pipeline")
        assert voice.status == "down"
        assert "missing key" in voice.details
