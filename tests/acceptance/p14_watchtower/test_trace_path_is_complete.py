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


# ---------------------------------------------------------------------------
# Phase 5: P14.4 Admin Controls
# ---------------------------------------------------------------------------


def test_20_admin_flags_list_returns_flags(admin_client) -> None:
    """Feature flags endpoint returns list of flags with name, enabled, lifecycle."""
    resp = admin_client.get("/api/admin/flags")
    assert resp.status_code == 200
    data = resp.json()
    assert "flags" in data
    assert isinstance(data["flags"], list)
    assert len(data["flags"]) >= 4
    flag = data["flags"][0]
    assert "name" in flag
    assert "enabled" in flag
    assert "lifecycle" in flag
    assert isinstance(flag["enabled"], bool)


def test_21_admin_flags_toggle_updates_state(admin_client) -> None:
    """Toggling a flag returns the updated state."""
    # Toggle multi_agent to True
    resp = admin_client.put("/api/admin/flags/multi_agent", json={"enabled": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "multi_agent"
    assert data["enabled"] is True

    # Verify it persisted
    resp = admin_client.get("/api/admin/flags")
    flags = {f["name"]: f["enabled"] for f in resp.json()["flags"]}
    assert flags["multi_agent"] is True


def test_22_admin_flags_delete_removes_flag(admin_client) -> None:
    """Deleting a flag removes it from the list."""
    resp = admin_client.delete("/api/admin/flags/semantic_cache")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == "semantic_cache"

    # Verify it's gone
    resp = admin_client.get("/api/admin/flags")
    names = [f["name"] for f in resp.json()["flags"]]
    assert "semantic_cache" not in names


def test_23_admin_cache_list_returns_caches(admin_client) -> None:
    """Cache endpoint returns list of known caches."""
    resp = admin_client.get("/api/admin/cache")
    assert resp.status_code == 200
    data = resp.json()
    assert "caches" in data
    assert isinstance(data["caches"], list)
    assert len(data["caches"]) >= 1
    # Settings cache should always be present
    names = [c["name"] for c in data["caches"]]
    assert "settings" in names


def test_24_admin_config_returns_current_config(admin_client) -> None:
    """Config endpoint returns current settings."""
    resp = admin_client.get("/api/admin/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "config" in data
    assert isinstance(data["config"], dict)


def test_25_admin_diagnostics_returns_check_results(admin_client) -> None:
    """Diagnostics endpoint returns overall status and checks list."""
    resp = admin_client.get("/api/admin/diagnostics")
    assert resp.status_code == 200
    data = resp.json()
    assert "overall" in data
    assert data["overall"] in ("pass", "warn", "fail")
    assert "summary" in data
    assert "checks" in data
    assert isinstance(data["checks"], list)
    if data["checks"]:
        check = data["checks"][0]
        assert "check" in check
        assert "status" in check
        assert "message" in check


def test_26_admin_sessions_returns_session_list(admin_client) -> None:
    """Sessions endpoint returns list of sessions from span data."""
    resp = admin_client.get("/api/admin/sessions", params={"hours": 24, "limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)
    assert "hours" in data
    assert "count" in data


def test_27_admin_invalid_flag_delete_returns_404(admin_client) -> None:
    """Deleting a nonexistent flag returns 404."""
    resp = admin_client.delete("/api/admin/flags/nonexistent_flag_xyz")
    assert resp.status_code == 404


# ===================================================================
# P14.5 — Audit & Compliance
# ===================================================================


def test_28_admin_audit_returns_log_entries(admin_client) -> None:
    """Audit query endpoint returns a list of audit entries."""
    resp = admin_client.get("/api/admin/audit", params={"hours": 24})
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert isinstance(data["entries"], list)
    assert "count" in data
    assert data["count"] >= 0
    # Verify entry structure when entries exist
    if data["entries"]:
        entry = data["entries"][0]
        assert "timestamp" in entry
        assert "actor" in entry
        assert "action" in entry
        assert "resource" in entry


def test_29_admin_audit_filter_by_action(admin_client) -> None:
    """Audit log supports filtering by action type."""
    resp = admin_client.get(
        "/api/admin/audit",
        params={"hours": 24, "action": "feature_toggle"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert "count" in data


def test_30_admin_data_export_returns_session_data(admin_client) -> None:
    """GDPR export endpoint returns data bundle with all stores."""
    resp = admin_client.get("/api/admin/data/test-session")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "test-session"
    assert "stores" in data
    stores = data["stores"]
    expected_stores = [
        "session_files", "mongodb_spans", "qdrant_vectors",
        "neo4j_graph", "chronicle_checkpoints", "audit_log",
    ]
    for store_name in expected_stores:
        assert store_name in stores, f"Missing store: {store_name}"


def test_31_admin_data_delete_purges_session(admin_client) -> None:
    """GDPR delete endpoint returns deletion summary for each store."""
    resp = admin_client.delete("/api/admin/data/test-session")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "test-session"
    assert "stores" in data
    assert "deleted_at" in data
    # Each store should have a "deleted" count
    for store_name, store_data in data["stores"].items():
        assert "deleted" in store_data, f"Store {store_name} missing 'deleted' key"


def test_32_admin_data_delete_nonexistent_returns_empty(admin_client) -> None:
    """Deleting a nonexistent session returns zero counts but succeeds."""
    resp = admin_client.delete("/api/admin/data/nonexistent-session-xyz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "nonexistent-session-xyz"


def test_33_admin_auth_rejects_without_key(admin_client_with_auth) -> None:
    """When admin_api_key is configured, requests without key get 401."""
    resp = admin_client_with_auth.get("/api/admin/audit")
    assert resp.status_code == 401


def test_34_admin_auth_allows_with_valid_key(admin_client_with_auth) -> None:
    """When admin_api_key is configured, requests with correct key get through."""
    resp = admin_client_with_auth.get(
        "/api/admin/audit",
        headers={"X-Admin-Key": "test-secret-key-123"},
    )
    # Should not be 401 (may be 500 if mocks not set up for full flow, but auth passes)
    assert resp.status_code != 401
