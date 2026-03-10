"""Integration scaffold for P05 (p05_chronicle).

These tests enforce contract-level integration gates across repo structure and CI wiring.
"""

from pathlib import Path

PROJECT_ID = "P05"
PROJECT_KEY = "p05_chronicle"
CI_CHECK = "p05-chronicle-replay"
CHARTER = Path("CAPSTONE/project_charters/P05_chronicle_ai_session_tracking_reproducibility.md")
ACCEPTANCE_FILE = Path("tests/acceptance/p05_chronicle/test_rewind_restores_exact_state.py")
INTEGRATION_FILE = Path("tests/integration/test_chronicle_git_checkpoint_alignment.py")
WORKFLOW_FILE = Path(".github/workflows/project-gates.yml")
BASELINE_SCRIPT = Path("scripts/test_all.sh")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


# === Week 2: Integration scenarios for rewind engine ===

import tempfile


def test_06_rewind_module_importable() -> None:
    """session.rewind module imports without error."""
    from session.rewind import (  # noqa: F401
        RewindError,
        RewindResult,
        restore_from_checkpoint,
        rewind_to_latest,
        list_available_checkpoints,
        verify_restoration_invariants,
    )


def test_07_checkpoint_and_rewind_roundtrip() -> None:
    """Create a checkpoint from a graph dict, rewind, and verify node count matches."""
    from session.checkpoint import create_checkpoint, load_checkpoint
    from session.rewind import restore_from_checkpoint

    graph_snap = {
        "directed": True,
        "multigraph": False,
        "graph": {
            "session_id": "integ-s1",
            "original_query": "test roundtrip",
            "status": "completed",
            "created_at": "2025-01-15T12:00:00Z",
            "file_manifest": [],
            "globals_schema": {},
        },
            "nodes": [
                {"id": "ROOT", "agent": "System", "status": "completed", "output": None, "error": None, "cost": 0.0, "start_time": None, "end_time": "2025-01-15T12:00:01Z"},
                {"id": "PlannerAgent", "agent": "PlannerAgent", "status": "completed", "output": {}, "error": None, "cost": 0.01, "start_time": "2025-01-15T12:00:01Z", "end_time": "2025-01-15T12:00:03Z"},
                {"id": "CoderAgent", "agent": "CoderAgent", "status": "completed", "output": {}, "error": None, "cost": 0.02, "start_time": "2025-01-15T12:00:03Z", "end_time": "2025-01-15T12:00:10Z"},
            ],
            "edges": [
                {"source": "ROOT", "target": "PlannerAgent"},
                {"source": "PlannerAgent", "target": "CoderAgent"},
            ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        cp_dir = Path(tmp) / "cp"
        ev_dir = Path(tmp) / "ev"
        ev_dir.mkdir()
        snap = create_checkpoint(
            session_id="integ-s1",
            trigger="step_complete",
            graph=graph_snap,
            event_log_path=ev_dir / "events_integ-s1.ndjson",
            checkpoint_dir=cp_dir,
        )
        loaded = load_checkpoint("integ-s1", snap.checkpoint_id, checkpoint_dir=cp_dir)
        context, result = restore_from_checkpoint(loaded, raise_on_violation=False)
        assert len(list(context.plan_graph.nodes)) == 3
        assert result.invariants_passed


def test_08_rewind_to_latest_selects_newest_checkpoint() -> None:
    """rewind_to_latest picks the most recent checkpoint when multiple exist."""
    from session.checkpoint import create_checkpoint
    from session.rewind import rewind_to_latest

    graph_snap = {
        "directed": True, "multigraph": False,
        "graph": {"session_id": "integ-s2", "original_query": "q", "status": "completed", "created_at": "2025-01-15T12:00:00Z", "file_manifest": [], "globals_schema": {}},
        "nodes": [{"id": "ROOT", "agent": "System", "status": "completed", "output": None, "error": None, "cost": 0.0, "start_time": None, "end_time": "2025-01-15T12:00:01Z"}],
            "edges": [],
    }
    with tempfile.TemporaryDirectory() as tmp:
        cp_dir = Path(tmp) / "cp"
        ev_dir = Path(tmp) / "ev"
        ev_dir.mkdir()
        create_checkpoint("integ-s2", "step_complete", graph_snap,
                          event_log_path=ev_dir / "events_integ-s2.ndjson",
                          created_at="2025-01-15T12:00:00Z", checkpoint_dir=cp_dir)
        create_checkpoint("integ-s2", "manual", graph_snap,
                          event_log_path=ev_dir / "events_integ-s2.ndjson",
                          created_at="2025-01-15T13:00:00Z", checkpoint_dir=cp_dir)
        context, result = rewind_to_latest("integ-s2", checkpoint_dir=cp_dir, raise_on_violation=False)
        assert result.checkpoint.trigger == "manual"


def test_09_restoration_invariants_pass_for_clean_graph() -> None:
    """verify_restoration_invariants reports no violations for a valid completed graph."""
    import networkx as nx
    from session.rewind import verify_restoration_invariants

    graph_snap = {
        "nodes": [
            {"id": "ROOT"},
            {"id": "StepA"},
        ]
    }
    g = nx.DiGraph()
    g.add_node("ROOT", agent="System", status="completed", end_time="2025-01-15T12:00:01Z", error=None)
    g.add_node("StepA", agent="CoderAgent", status="completed", end_time="2025-01-15T12:00:05Z", error=None)
    violations = verify_restoration_invariants(graph_snap, g)
    assert violations == []


def test_10_restoration_invariants_detect_missing_end_time() -> None:
    """verify_restoration_invariants flags completed nodes missing end_time."""
    import networkx as nx
    from session.rewind import verify_restoration_invariants

    graph_snap = {"nodes": [{"id": "StepB"}]}
    g = nx.DiGraph()
    g.add_node("StepB", agent="CoderAgent", status="completed", end_time=None, error=None)
    violations = verify_restoration_invariants(graph_snap, g)
    assert any("end_time" in v for v in violations)
