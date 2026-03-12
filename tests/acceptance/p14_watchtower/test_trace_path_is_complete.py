"""Acceptance tests for P14 (p14_watchtower).

Contract tests (01–08) plus functional tests for admin API: traces, cost, errors, health.
Uses conftest.admin_client with mocked MongoDB and health checks.
"""

from pathlib import Path

PROJECT_ID = "P14"
PROJECT_KEY = "p14_watchtower"
CI_CHECK = "p14-watchtower-ops"
CHARTER = Path("CAPSTONE/project_charters/P14_watchtower_admin_observability_operations_dashboard.md")
DELIVERY_README = Path("CAPSTONE/project_charters/P14_DELIVERY_README.md")
DEMO_SCRIPT = Path("scripts/demos/p14_watchtower.sh")
THIS_FILE = Path("tests/acceptance/p14_watchtower/test_trace_path_is_complete.py")


def _charter_text() -> str:
    return CHARTER.read_text(encoding="utf-8")


def test_01_charter_exists() -> None:
    assert CHARTER.exists(), f"Missing charter: {CHARTER}"


def test_02_expanded_gate_contract_present() -> None:
    assert "Expanded Mandatory Test Gate Contract (10 Hard Conditions)" in _charter_text()


def test_03_acceptance_path_declared_in_charter() -> None:
    assert f"Acceptance: " in _charter_text()


def test_04_demo_script_exists() -> None:
    assert DEMO_SCRIPT.exists(), f"Missing demo script: {DEMO_SCRIPT}"


def test_05_demo_script_is_executable() -> None:
    assert DEMO_SCRIPT.stat().st_mode & 0o111, f"Demo script not executable: {DEMO_SCRIPT}"


def test_06_delivery_readme_exists() -> None:
    assert DELIVERY_README.exists(), f"Missing delivery README: {DELIVERY_README}"


def test_07_delivery_readme_has_required_sections() -> None:
    required = [
        "## 1. Scope Delivered",
        "## 2. Architecture Changes",
        "## 3. API And UI Changes",
        "## 4. Mandatory Test Gate Definition",
        "## 5. Test Evidence",
        "## 8. Known Gaps",
        "## 10. Demo Steps",
    ]
    text = DELIVERY_README.read_text(encoding="utf-8")
    for section in required:
        assert section in text, f"Missing section {section} in {DELIVERY_README}"


def test_08_ci_check_declared_in_charter() -> None:
    assert f"CI required check: " in _charter_text()


# ---------------------------------------------------------------------------
# Functional tests: Admin API behaviour (traces, cost, errors, health)
# ---------------------------------------------------------------------------


def test_09_admin_traces_returns_expected_structure(admin_client) -> None:
    """Traces endpoint returns traces list with trace_id, duration_ms, span_count."""
    resp = admin_client.get("/api/admin/traces", params={"limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert "traces" in data
    assert isinstance(data["traces"], list)
    if data["traces"]:
        t = data["traces"][0]
        assert "trace_id" in t
        assert "duration_ms" in t
        assert "span_count" in t
        assert "start_time" in t


def test_10_admin_cost_summary_returns_expected_structure(admin_client) -> None:
    """Cost summary endpoint returns total_cost_usd, by_agent, by_model."""
    resp = admin_client.get("/api/admin/cost/summary", params={"hours": 24})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_cost_usd" in data
    assert "by_agent" in data
    assert "by_model" in data
    assert "trace_count" in data
    assert "hours" in data
    assert isinstance(data["by_agent"], dict)
    assert isinstance(data["by_model"], dict)


def test_11_admin_errors_summary_returns_expected_structure(admin_client) -> None:
    """Errors summary endpoint returns error_count and by_agent."""
    resp = admin_client.get("/api/admin/errors/summary", params={"hours": 24})
    assert resp.status_code == 200
    data = resp.json()
    assert "error_count" in data
    assert "by_agent" in data
    assert "hours" in data
    assert isinstance(data["by_agent"], dict)


def test_12_admin_health_returns_expected_structure(admin_client) -> None:
    """Health endpoint returns services list with status and latency."""
    resp = admin_client.get("/api/admin/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "services" in data
    assert isinstance(data["services"], list)
    assert len(data["services"]) >= 4
    for svc in data["services"]:
        assert "service" in svc
        assert "status" in svc
        assert svc["status"] in ("ok", "degraded", "down")


def test_13_admin_metrics_summary_returns_expected_structure(admin_client) -> None:
    """Metrics summary endpoint returns total_traces, avg_duration_ms, error_count."""
    resp = admin_client.get("/api/admin/metrics/summary", params={"hours": 24})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_traces" in data
    assert "avg_duration_ms" in data
    assert "error_count" in data
    assert "hours" in data


def test_14_admin_trace_detail_returns_spans(admin_client) -> None:
    """Trace detail endpoint returns trace_id and spans list."""
    resp = admin_client.get("/api/admin/traces/abc123def456")
    assert resp.status_code == 200
    data = resp.json()
    assert "trace_id" in data
    assert "spans" in data
    assert isinstance(data["spans"], list)


def test_15_admin_invalid_params_return_controlled_errors(admin_client) -> None:
    """Invalid query params return 422 (validation error), not 500."""
    resp = admin_client.get("/api/admin/traces", params={"limit": -1})
    assert resp.status_code == 422
    resp = admin_client.get("/api/admin/cost/summary", params={"hours": 0})
    assert resp.status_code == 422


def test_16_admin_traces_view_returns_html(admin_client) -> None:
    """Traces view fallback returns HTML page."""
    resp = admin_client.get("/api/admin/traces/view")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Watchtower" in resp.text or "traces" in resp.text.lower()


# ---------------------------------------------------------------------------
# Phase 4: Health history, uptime, resources endpoints (P14.3)
# ---------------------------------------------------------------------------


def test_17_health_history_returns_snapshots(admin_client) -> None:
    """Health history endpoint returns snapshots list with count."""
    resp = admin_client.get("/api/admin/health/history", params={"hours": 24})
    assert resp.status_code == 200
    data = resp.json()
    assert "snapshots" in data
    assert isinstance(data["snapshots"], list)
    assert "count" in data
    assert "hours" in data
    if data["snapshots"]:
        snap = data["snapshots"][0]
        assert "service" in snap
        assert "status" in snap
        assert "timestamp" in snap


def test_18_health_uptime_returns_percentages(admin_client) -> None:
    """Health uptime endpoint returns per-service uptime data."""
    resp = admin_client.get("/api/admin/health/uptime", params={"hours": 24})
    assert resp.status_code == 200
    data = resp.json()
    assert "uptimes" in data
    assert isinstance(data["uptimes"], list)
    assert "hours" in data
    if data["uptimes"]:
        entry = data["uptimes"][0]
        assert "service" in entry
        assert "uptime_pct" in entry
        assert "total_checks" in entry
        assert "ok_checks" in entry


def test_19_health_resources_returns_cpu_mem_disk(admin_client) -> None:
    """Health resources endpoint returns CPU, memory, and disk metrics."""
    resp = admin_client.get("/api/admin/health/resources")
    assert resp.status_code == 200
    data = resp.json()
    assert "resources" in data
    res = data["resources"]
    assert "cpu_pct" in res
    assert "mem_pct" in res
    assert "disk_pct" in res
    assert isinstance(res["cpu_pct"], (int, float))
    assert isinstance(res["mem_pct"], (int, float))
    assert isinstance(res["disk_pct"], (int, float))
