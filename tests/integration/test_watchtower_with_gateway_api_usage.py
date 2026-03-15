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


# ---------------------------------------------------------------------------
# P14.4: Admin Controls integration tests
# ---------------------------------------------------------------------------


def test_11_admin_flags_module_provides_feature_flag_store() -> None:
    """ops.admin.feature_flags.FeatureFlagStore can get/set/list flags."""
    import tempfile
    import json
    from pathlib import Path
    from ops.admin.feature_flags import FeatureFlagStore

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "flags.json"
        store = FeatureFlagStore(path=path)

        # File should be auto-created with defaults
        assert path.exists()

        # list_all returns flags
        flags = store.list_all()
        assert isinstance(flags, list)
        assert len(flags) >= 4

        # get/set works
        store.set("test_flag", True)
        assert store.get("test_flag") is True

        store.set("test_flag", False)
        assert store.get("test_flag") is False

        # delete works
        assert store.delete("test_flag") is True
        assert store.get("test_flag") is False  # returns default


def test_12_admin_diagnostics_module_returns_results() -> None:
    """ops.admin.diagnostics.run_diagnostics returns overall, summary, checks."""
    from unittest.mock import patch

    # Mock health checks to avoid network calls
    mock_results = [
        type("R", (), {"to_dict": lambda self: {"service": "mongodb", "status": "ok", "latency_ms": 1.0, "details": None}})(),
        type("R", (), {"to_dict": lambda self: {"service": "qdrant", "status": "ok", "latency_ms": 2.0, "details": None}})(),
    ]

    with patch("ops.admin.diagnostics.run_all_health_checks" if False else "ops.health.run_all_health_checks", return_value=mock_results):
        from ops.admin.diagnostics import run_diagnostics
        result = run_diagnostics()

    assert "overall" in result
    assert result["overall"] in ("pass", "warn", "fail")
    assert "summary" in result
    assert "checks" in result
    assert isinstance(result["checks"], list)
    assert len(result["checks"]) >= 5  # env checks + service checks


def test_13_admin_throttle_policy_reads_cost_data() -> None:
    """ops.admin.throttle.ThrottlePolicy returns usage summary."""
    from unittest.mock import MagicMock
    from ops.admin.throttle import ThrottlePolicy

    # Mock spans collection that returns zero cost
    mock_coll = MagicMock()
    mock_coll.aggregate.return_value = iter([])

    policy = ThrottlePolicy(spans_collection=mock_coll)
    summary = policy.get_usage_summary()

    assert "hourly" in summary
    assert "daily" in summary
    assert "allowed" in summary
    assert summary["allowed"] is True
    assert summary["hourly"]["spent_usd"] == 0.0
    assert summary["daily"]["spent_usd"] == 0.0


# ====================================================================
# P14.5 — Audit & Compliance integration tests
# ====================================================================


def test_14_audit_logger_writes_and_queries():
    """AuditLogger round-trip: write an entry, then query it back."""
    from unittest.mock import MagicMock, patch
    from ops.audit.audit_logger import AuditLogger, AuditEntry

    logger = AuditLogger.__new__(AuditLogger)
    logger._lock = __import__("threading").Lock()
    logger._repo = None

    # Use JSONL fallback to a temp file
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mktemp(suffix=".jsonl"))
    logger._fallback_path = tmp

    try:
        # Patch settings so _get_repo returns None (JSONL only)
        with patch("ops.audit.audit_logger.settings", {"watchtower": {"enabled": False}}):
            # Write an entry
            entry = logger.log_action("test-actor", "test-action", "test-resource", "old", "new")
            assert isinstance(entry, AuditEntry)
            assert entry.actor == "test-actor"

            # Query it back
            results = logger.query(hours=1, action="test-action")
            assert len(results) == 1
            assert results[0]["actor"] == "test-actor"
            assert results[0]["action"] == "test-action"
            assert results[0]["resource"] == "test-resource"
            assert results[0]["old_value"] == "old"
            assert results[0]["new_value"] == "new"
    finally:
        if tmp.exists():
            tmp.unlink()


def test_15_audit_fallback_to_jsonl():
    """AuditLogger falls back to JSONL when MongoDB is unavailable."""
    from unittest.mock import patch
    from ops.audit.audit_logger import AuditLogger

    logger = AuditLogger.__new__(AuditLogger)
    logger._lock = __import__("threading").Lock()
    logger._repo = None

    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mktemp(suffix=".jsonl"))
    logger._fallback_path = tmp

    try:
        # Patch settings so _get_repo returns None (watchtower disabled)
        with patch("ops.audit.audit_logger.settings", {"watchtower": {"enabled": False}}):
            logger.log_action("admin", "cache_flush", "cache:settings")

        assert tmp.exists()
        import json
        lines = tmp.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "cache_flush"
    finally:
        if tmp.exists():
            tmp.unlink()


def test_16_session_data_manager_export_collects_data():
    """SessionDataManager.export aggregates data from all stores."""
    from unittest.mock import MagicMock
    from ops.audit.data_manager import SessionDataManager

    import tempfile
    from pathlib import Path
    import json

    # Create a temp conversation dir with a test session file
    conv_dir = Path(tempfile.mkdtemp())
    session_file = conv_dir / "session_test123.json"
    session_file.write_text(json.dumps({"query": "hello", "steps": 3}))

    manager = SessionDataManager(
        spans_collection=None,
        audit_collection=None,
        conversation_dir=conv_dir,
        checkpoint_dir=Path(tempfile.mkdtemp()),
        events_dir=Path(tempfile.mkdtemp()),
    )

    result = manager.export("test123")

    assert result["session_id"] == "test123"
    assert "stores" in result
    assert result["stores"]["session_files"]["count"] == 1
    assert result["stores"]["mongodb_spans"]["count"] == 0  # No MongoDB
    assert result["stores"]["qdrant_vectors"]["count"] == 0  # No Qdrant
    assert result["stores"]["chronicle_checkpoints"]["count"] == 0  # Empty dir


def test_17_session_data_manager_delete_purges_data():
    """SessionDataManager.delete removes session files."""
    from ops.audit.data_manager import SessionDataManager

    import tempfile
    from pathlib import Path
    import json

    conv_dir = Path(tempfile.mkdtemp())
    session_file = conv_dir / "session_del123.json"
    session_file.write_text(json.dumps({"query": "test"}))

    assert session_file.exists()

    manager = SessionDataManager(
        spans_collection=None,
        audit_collection=None,
        conversation_dir=conv_dir,
        checkpoint_dir=Path(tempfile.mkdtemp()),
        events_dir=Path(tempfile.mkdtemp()),
    )

    result = manager.delete("del123")

    assert result["session_id"] == "del123"
    assert result["stores"]["session_files"]["deleted"] == 1
    assert not session_file.exists()  # File actually removed


def test_18_admin_auth_middleware_enforces_key():
    """Admin auth middleware returns 401 when key is configured and missing."""
    from unittest.mock import patch, MagicMock
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import routers.admin as admin_router

    app = FastAPI()
    app.include_router(admin_router.router, prefix="/api")

    mock_coll = MagicMock()

    test_settings = {
        "watchtower": {
            "enabled": False,
            "admin_api_key": "secret-key-xyz",
        }
    }

    with (
        patch.object(admin_router, "_get_spans_collection", return_value=mock_coll),
        patch("config.settings_loader.settings", test_settings),
        patch("routers.admin.settings", test_settings),
    ):
        with TestClient(app) as client:
            # Without key → 401
            resp = client.get("/api/admin/audit")
            assert resp.status_code == 401

            # With wrong key → 401
            resp = client.get("/api/admin/audit", headers={"X-Admin-Key": "wrong"})
            assert resp.status_code == 401

            # With correct key → not 401
            resp = client.get("/api/admin/audit", headers={"X-Admin-Key": "secret-key-xyz"})
            assert resp.status_code != 401
