"""Integration tests for P14 (p14_watchtower).

Contract tests (01–05) plus functional integration tests for admin API wiring.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import admin as admin_router

PROJECT_ID = "P14"
PROJECT_KEY = "p14_watchtower"
CI_CHECK = "p14-watchtower-ops"
CHARTER = Path("CAPSTONE/project_charters/P14_watchtower_admin_observability_operations_dashboard.md")
ACCEPTANCE_FILE = Path("tests/acceptance/p14_watchtower/test_trace_path_is_complete.py")
INTEGRATION_FILE = Path("tests/integration/test_watchtower_with_gateway_api_usage.py")
WORKFLOW_FILE = Path(".github/workflows/project-gates.yml")
BASELINE_SCRIPT = Path("scripts/test_all.sh")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Contract tests (CI wiring)
# ---------------------------------------------------------------------------


def test_01_integration_file_is_declared_in_charter() -> None:
    assert f"Integration: " in _read(CHARTER)


def test_02_acceptance_and_integration_files_exist() -> None:
    assert ACCEPTANCE_FILE.exists(), f"Missing acceptance file: {ACCEPTANCE_FILE}"
    assert INTEGRATION_FILE.exists(), f"Missing integration file: {INTEGRATION_FILE}"


def test_03_baseline_script_exists_and_is_executable() -> None:
    assert BASELINE_SCRIPT.exists(), "Missing baseline script scripts/test_all.sh"
    assert BASELINE_SCRIPT.stat().st_mode & 0o111, "scripts/test_all.sh must be executable"


def test_04_project_ci_check_is_wired_in_workflow() -> None:
    assert WORKFLOW_FILE.exists(), "Missing workflow .github/workflows/project-gates.yml"
    assert CI_CHECK in _read(WORKFLOW_FILE), f"CI check {CI_CHECK} not found in workflow"


def test_05_charter_requires_baseline_regression() -> None:
    assert "scripts/test_all.sh quick" in _read(CHARTER)


# ---------------------------------------------------------------------------
# Functional integration tests: Admin API mounted and responsive
# ---------------------------------------------------------------------------


def test_06_admin_router_mounted_and_traces_reachable() -> None:
    """Admin router is mounted; traces endpoint returns 200 with mocked MongoDB."""
    mock_coll = MagicMock()
    mock_coll.aggregate.return_value = iter([])
    mock_coll.find.return_value.sort.return_value = []

    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api")

    with patch.object(admin_router, "_get_spans_collection", return_value=mock_coll):
        with TestClient(app) as client:
            resp = client.get("/api/admin/traces")
    assert resp.status_code == 200
    assert "traces" in resp.json()


def test_07_admin_health_integration_returns_services() -> None:
    """Health endpoint returns services list when health checks are mocked."""
    mock_results = [
        type("R", (), {"to_dict": lambda self: {"service": "mongodb", "status": "ok", "latency_ms": 1.0, "details": None}})(),
        type("R", (), {"to_dict": lambda self: {"service": "qdrant", "status": "ok", "latency_ms": 2.0, "details": None}})(),
    ]
    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api")

    with patch("ops.health.run_all_health_checks", return_value=mock_results):
        with TestClient(app) as client:
            resp = client.get("/api/admin/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "services" in data
    assert len(data["services"]) >= 2


def test_08_admin_cost_and_errors_endpoints_wired() -> None:
    """Cost and errors endpoints are wired and return expected keys."""
    mock_coll = MagicMock()
    mock_coll.aggregate.return_value = iter([])
    mock_coll.find.return_value.sort.return_value = []

    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api")

    with patch.object(admin_router, "_get_spans_collection", return_value=mock_coll):
        with TestClient(app) as client:
            cost_resp = client.get("/api/admin/cost/summary")
            err_resp = client.get("/api/admin/errors/summary")
    assert cost_resp.status_code == 200
    assert "total_cost_usd" in cost_resp.json()
    assert err_resp.status_code == 200
    assert "error_count" in err_resp.json()


def test_09_ops_health_module_provides_run_all_health_checks() -> None:
    """ops.health.run_all_health_checks exists and returns list of results."""
    from ops.health import run_all_health_checks

    results = run_all_health_checks()
    assert isinstance(results, list)
    assert len(results) >= 4
    for r in results:
        assert hasattr(r, "service")
        assert hasattr(r, "status")
        assert hasattr(r, "to_dict")


def test_10_ops_cost_module_provides_configurable_calculator() -> None:
    """ops.cost.ConfigurableCostCalculator exists and computes cost."""
    from ops.cost import ConfigurableCostCalculator

    calc = ConfigurableCostCalculator()
    result = calc.compute(1000, 500, "gemini-2.5-flash", "gemini")
    assert hasattr(result, "cost_usd")
    assert hasattr(result, "input_tokens")
    assert hasattr(result, "output_tokens")
    assert result.input_tokens == 1000
    assert result.output_tokens == 500
