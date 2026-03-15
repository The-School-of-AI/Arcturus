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


# === Git/checkpoint alignment and cross-module trace linking ===


def test_11_checkpoint_includes_git_commit_when_in_repo() -> None:
    """Checkpoint includes git_commit_sha when created from a git repo."""
    from session.checkpoint import create_checkpoint
    from session.alignment import get_git_head_info

    # Use project root (this repo is a git repo)
    repo = Path(__file__).resolve().parent.parent.parent
    if not (repo / ".git").exists():
        return  # Skip if not in git repo (e.g. extracted tarball)
    git_info = get_git_head_info(repo)
    if not git_info.get("git_commit_sha"):
        return  # Skip if git not available

    graph_snap = {
        "directed": True,
        "multigraph": False,
        "graph": {"session_id": "integ-git", "status": "completed", "created_at": "2025-01-15T12:00:00Z"},
        "nodes": [{"id": "ROOT", "agent": "System", "status": "completed"}],
        "edges": [],
    }
    with tempfile.TemporaryDirectory() as tmp:
        cp_dir = Path(tmp) / "cp"
        ev_dir = Path(tmp) / "ev"
        ev_dir.mkdir()
        snap = create_checkpoint(
            "integ-git",
            "manual",
            graph_snap,
            event_log_path=ev_dir / "events_integ-git.ndjson",
            checkpoint_dir=cp_dir,
            repo_path=repo,
        )
        assert snap.git_commit_sha != ""
        assert len(snap.git_commit_sha) >= 7


def test_12_checkpoint_includes_trace_id_when_under_span() -> None:
    """Checkpoint includes trace_id when created under run_span (Watchtower cross-module linking)."""
    import pytest

    from session.checkpoint import create_checkpoint
    from ops.tracing.spans import run_span

    graph_snap = {
        "directed": True,
        "multigraph": False,
        "graph": {"session_id": "integ-trace", "status": "completed", "created_at": "2025-01-15T12:00:00Z"},
        "nodes": [{"id": "ROOT", "agent": "System", "status": "completed"}],
        "edges": [],
    }
    with tempfile.TemporaryDirectory() as tmp:
        cp_dir = Path(tmp) / "cp"
        ev_dir = Path(tmp) / "ev"
        ev_dir.mkdir()
        with run_span("integ-trace-run", "test trace linking"):
            snap = create_checkpoint(
                "integ-trace",
                "manual",
                graph_snap,
                event_log_path=ev_dir / "events_integ-trace.ndjson",
                checkpoint_dir=cp_dir,
            )
        if not snap.trace_id:
            pytest.skip("Tracing not initialized (init_tracing not called)")
        assert len(snap.trace_id) == 32


# === Phase 7: Concurrent edit hardening ===


def test_13_concurrent_checkpoint_creation_same_session() -> None:
    """Multiple checkpoints for same session complete without corruption (lock-protected)."""
    import concurrent.futures

    from session.checkpoint import create_checkpoint, load_checkpoint

    graph_snap = {
        "directed": True,
        "multigraph": False,
        "graph": {"session_id": "integ-concurrent", "status": "completed", "created_at": "2025-01-15T12:00:00Z"},
        "nodes": [{"id": "ROOT", "agent": "System", "status": "completed"}],
        "edges": [],
    }
    with tempfile.TemporaryDirectory() as tmp:
        cp_dir = Path(tmp) / "cp"
        ev_dir = Path(tmp) / "ev"
        ev_dir.mkdir()

        def create_one(i: int):
            g = {**graph_snap, "graph": {**graph_snap["graph"], "seq": i}}
            return create_checkpoint(
                "integ-concurrent",
                "manual",
                g,
                event_log_path=ev_dir / "events_integ-concurrent.ndjson",
                checkpoint_dir=cp_dir,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(create_one, i) for i in range(8)]
            snaps = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(snaps) == 8
        ids = {s.checkpoint_id for s in snaps}
        assert len(ids) == 8
        for s in snaps:
            loaded = load_checkpoint("integ-concurrent", s.checkpoint_id, checkpoint_dir=cp_dir)
            assert loaded is not None


def test_14_capture_per_session_sequence() -> None:
    """SessionCapture emits events with correct per-session sequence under concurrent sessions."""
    import asyncio

    from session.capture import SessionCapture
    from session.schema import EventType

    async def run():
        with tempfile.TemporaryDirectory() as tmp:
            ev_dir = Path(tmp) / "ev"
            ev_dir.mkdir()
            cap = SessionCapture(event_log_dir=ev_dir)
            cap.start_writer()

            async def emit_session(sid: str, count: int):
                cap.start_session(sid)
                for _ in range(count):
                    await cap.emit(EventType.STEP_START, {"step": "x"}, session_id=sid)

            await asyncio.gather(
                emit_session("s1", 3),
                emit_session("s2", 2),
            )
            await cap.stop_writer()

            def read_sequences(path: Path):
                seqs = []
                if path.exists():
                    for line in path.read_text().strip().split("\n"):
                        if line:
                            obj = __import__("json").loads(line)
                            seqs.append(obj.get("sequence", 0))
                return seqs

            s1_seqs = sorted(read_sequences(ev_dir / "events_s1.ndjson"))
            s2_seqs = sorted(read_sequences(ev_dir / "events_s2.ndjson"))
            assert s1_seqs == [1, 2, 3]
            assert s2_seqs == [1, 2]

    asyncio.run(run())
