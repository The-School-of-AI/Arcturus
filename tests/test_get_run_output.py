"""Tests for GET /api/runs/{run_id}/output endpoint.

Tests cover:
- run_id that is currently active (running) → status=running, output=None
- run_id with a completed session JSON on disk → status=completed, output=str
- run_id that is unknown → status=not_found, output=None

All tests use TestClient; no real AgentLoop4 is started.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import runs as runs_router


def _make_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(runs_router.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Test 1: run_id is actively running
# ---------------------------------------------------------------------------


def test_output_running():
    """A run_id present in active_loops must return status=running, output=None."""
    client = _make_test_client()
    fake_loop = object()  # Any truthy value stands in for an active loop
    with patch.dict(runs_router.active_loops, {"run-live-001": fake_loop}):
        resp = client.get("/api/runs/run-live-001/output")

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "run-live-001"
    assert body["status"] == "running"
    assert body["output"] is None


# ---------------------------------------------------------------------------
# Test 2: completed run on disk
# ---------------------------------------------------------------------------


def test_output_completed():
    """A session JSON on disk must return status=completed and the extracted output."""
    run_id = "1700000001"
    # Minimal session node-link JSON with a FormatterAgent node that has output
    session_data = {
        "directed": True,
        "multigraph": False,
        "graph": {"status": "completed"},
        "nodes": [
            {"id": "ROOT", "status": "completed", "agent": "PlannerAgent", "output": {}},
            {
                "id": "node_1",
                "status": "completed",
                "agent": "FormatterAgent",
                "output": {"markdown_report": "# Result\n\nThe answer is 42."},
            },
        ],
        "edges": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        # Build the expected directory structure
        session_dir = Path(tmpdir) / "2026" / "02" / "23"
        session_dir.mkdir(parents=True)
        session_file = session_dir / f"session_{run_id}.json"
        session_file.write_text(json.dumps(session_data))

        fake_summaries_dir = Path(tmpdir)

        with patch.object(runs_router, "PROJECT_ROOT", Path(tmpdir).parent):
            # Patch the rglob search to use our tmp dir
            original_rglob = Path.rglob

            def _patched_rglob(self, pattern):
                if "session_summaries_index" in str(self):
                    return fake_summaries_dir.rglob(pattern)
                return original_rglob(self, pattern)

            with patch.object(Path, "rglob", _patched_rglob):
                # Also patch the summaries_dir construction inside the endpoint
                with patch("routers.runs.PROJECT_ROOT", Path(tmpdir).parent):
                    # Directly patch the rglob on the specific path object
                    # Simpler: patch active_loops to be empty and patch the glob
                    with patch.dict(runs_router.active_loops, {}):
                        client = _make_test_client()

                        # Inject the session file by patching the rglob call
                        def mock_rglob(pattern):
                            if f"session_{run_id}" in pattern:
                                return iter([session_file])
                            return iter([])

                        import routers.runs as rmod
                        orig_project_root = rmod.PROJECT_ROOT
                        try:
                            rmod.PROJECT_ROOT = Path(tmpdir).parent

                            # Patch Path.rglob on the summaries_dir
                            with patch.object(
                                Path,
                                "rglob",
                                lambda self, pat: iter([session_file]) if run_id in pat else iter([]),
                            ):
                                resp = client.get(f"/api/runs/{run_id}/output")
                        finally:
                            rmod.PROJECT_ROOT = orig_project_root

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run_id
    assert body["status"] == "completed"
    assert body["output"] is not None
    assert "42" in body["output"]


# ---------------------------------------------------------------------------
# Test 3: unknown run_id → not_found
# ---------------------------------------------------------------------------


def test_output_not_found():
    """An unknown run_id must return status=not_found, output=None (no 404)."""
    client = _make_test_client()

    with patch.dict(runs_router.active_loops, {}):
        # Patch Path.rglob to return empty iterator (no session file on disk)
        with patch.object(Path, "rglob", return_value=iter([])):
            resp = client.get("/api/runs/does-not-exist-999/output")

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "does-not-exist-999"
    assert body["status"] == "not_found"
    assert body["output"] is None
