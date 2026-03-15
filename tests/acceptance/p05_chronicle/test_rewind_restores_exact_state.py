"""Acceptance scaffold for P05 (p05_chronicle).

Replace these contract tests with feature-level assertions as implementation matures.
Week 1: Event log schema + deterministic checkpoint flow tests.
"""

import tempfile
from pathlib import Path

PROJECT_ID = "P05"
PROJECT_KEY = "p05_chronicle"
CI_CHECK = "p05-chronicle-replay"
CHARTER = Path("CAPSTONE/project_charters/P05_chronicle_ai_session_tracking_reproducibility.md")
DELIVERY_README = Path("CAPSTONE/project_charters/P05_DELIVERY_README.md")
DEMO_SCRIPT = Path("scripts/demos/p05_chronicle.sh")
THIS_FILE = Path("tests/acceptance/p05_chronicle/test_rewind_restores_exact_state.py")


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


# === Week 1: Event log schema + checkpoint flow ===


def test_09_event_log_entry_canonical_json_determinism() -> None:
    """Same entry produces identical canonical JSON when given same timestamp."""
    from session.schema import EventLogEntry, EventType

    ts = "2025-01-15T12:00:00.000000Z"
    e1 = EventLogEntry(
        type=EventType.STEP_START,
        timestamp=ts,
        sequence=1,
        session_id="s1",
        payload={"step_id": "Step1", "agent": "CoderAgent"},
    )
    e2 = EventLogEntry(
        type=EventType.STEP_START,
        timestamp=ts,
        sequence=1,
        session_id="s1",
        payload={"step_id": "Step1", "agent": "CoderAgent"},
    )
    assert e1.to_canonical_json() == e2.to_canonical_json()


def test_10_event_log_entry_content_hash_determinism() -> None:
    """Same entry produces identical content hash when given same timestamp."""
    from session.schema import EventLogEntry, EventType

    ts = "2025-01-15T12:00:00.000000Z"
    e1 = EventLogEntry(
        type=EventType.TOOL_INVOCATION,
        timestamp=ts,
        sequence=2,
        session_id="s1",
        payload={"step_id": "S1", "tool_name": "read_file"},
    )
    e2 = EventLogEntry(
        type=EventType.TOOL_INVOCATION,
        timestamp=ts,
        sequence=2,
        session_id="s1",
        payload={"step_id": "S1", "tool_name": "read_file"},
    )
    assert e1.content_hash() == e2.content_hash()
    assert len(e1.content_hash()) == 16


def test_11_create_checkpoint_deterministic_hash() -> None:
    """Same inputs produce same checkpoint content hash."""
    from session.checkpoint import create_checkpoint

    with tempfile.TemporaryDirectory() as tmp:
        cp_dir = Path(tmp) / "checkpoints"
        ev_dir = Path(tmp) / "events"
        ev_dir.mkdir()
        graph = {"nodes": [{"id": "A"}], "links": []}
        fixed_created_at = "2025-01-15T12:00:00.000000Z"
        c1 = create_checkpoint(
            session_id="s1",
            trigger="step_complete",
            graph=graph,
            event_log_path=ev_dir / "events_s1.ndjson",
            last_sequence=0,
            checkpoint_dir=cp_dir,
            created_at=fixed_created_at,
        )
        c2 = create_checkpoint(
            session_id="s1",
            trigger="step_complete",
            graph=graph,
            event_log_path=ev_dir / "events_s1.ndjson",
            last_sequence=0,
            checkpoint_dir=cp_dir,
            created_at=fixed_created_at,
        )
        assert c1.content_hash == c2.content_hash
        assert c1.checkpoint_id == c2.checkpoint_id


def test_12_create_checkpoint_persists_and_loads() -> None:
    """Checkpoint is written to disk and load_checkpoint retrieves it."""
    from session.checkpoint import create_checkpoint, load_checkpoint

    with tempfile.TemporaryDirectory() as tmp:
        cp_dir = Path(tmp) / "checkpoints"
        ev_dir = Path(tmp) / "events"
        ev_dir.mkdir()
        graph = {
            "nodes": [{"id": "X"}, {"id": "Y"}],
            "links": [{"source": "X", "target": "Y"}],
        }
        snap = create_checkpoint(
            session_id="sess1",
            trigger="manual",
            graph=graph,
            event_log_path=ev_dir / "events_sess1.ndjson",
            checkpoint_dir=cp_dir,
        )
        loaded = load_checkpoint("sess1", snap.checkpoint_id, checkpoint_dir=cp_dir)
        assert loaded is not None
        assert loaded.session_id == "sess1"
        assert loaded.trigger == "manual"
        assert len(loaded.graph_snapshot.get("nodes", [])) == 2


# === Week 2: Rewind engine and state restoration invariants ===


def _make_graph_snapshot(nodes: list[dict], edges: list[dict] | None = None) -> dict:
    """Build a minimal node_link_data style graph dict for tests."""
    return {
        "directed": True,
        "multigraph": False,
        "graph": {
            "session_id": "test-session",
            "original_query": "test",
            "status": "completed",
            "created_at": "2025-01-15T12:00:00Z",
            "file_manifest": [],
            "globals_schema": {},
        },
        "nodes": nodes,
        "edges": edges or [],
    }


def test_13_restore_from_checkpoint_returns_correct_node_count() -> None:
    """Restored context has same number of nodes as the checkpoint snapshot."""
    from session.checkpoint import create_checkpoint, load_checkpoint
    from session.rewind import restore_from_checkpoint

    with tempfile.TemporaryDirectory() as tmp:
        cp_dir = Path(tmp) / "cp"
        ev_dir = Path(tmp) / "ev"
        ev_dir.mkdir()
        graph_snap = _make_graph_snapshot([
            {"id": "ROOT", "agent": "System", "status": "completed", "output": None, "error": None, "cost": 0.0, "start_time": None, "end_time": "2025-01-15T12:00:01Z"},
            {"id": "Step1", "agent": "CoderAgent", "status": "completed", "output": {}, "error": None, "cost": 0.01, "start_time": "2025-01-15T12:00:01Z", "end_time": "2025-01-15T12:00:05Z"},
            {"id": "Step2", "agent": "FormatterAgent", "status": "pending", "output": None, "error": None, "cost": 0.0, "start_time": None, "end_time": None},
        ])
        snap = create_checkpoint(
            session_id="s-restore",
            trigger="step_complete",
            graph=graph_snap,
            event_log_path=ev_dir / "events_s-restore.ndjson",
            checkpoint_dir=cp_dir,
        )
        loaded = load_checkpoint("s-restore", snap.checkpoint_id, checkpoint_dir=cp_dir)
        context, result = restore_from_checkpoint(loaded, raise_on_violation=False)
        assert len(list(context.plan_graph.nodes)) == 3


def test_14_restore_resets_running_nodes_to_pending() -> None:
    """Nodes with status 'running' are reset to 'pending' after restoration."""
    from session.checkpoint import create_checkpoint, load_checkpoint
    from session.rewind import restore_from_checkpoint

    with tempfile.TemporaryDirectory() as tmp:
        cp_dir = Path(tmp) / "cp"
        ev_dir = Path(tmp) / "ev"
        ev_dir.mkdir()
        graph_snap = _make_graph_snapshot([
            {"id": "ROOT", "agent": "System", "status": "completed", "output": None, "error": None, "cost": 0.0, "start_time": None, "end_time": "2025-01-15T12:00:01Z"},
            {"id": "StepA", "agent": "CoderAgent", "status": "running", "output": None, "error": None, "cost": 0.0, "start_time": "2025-01-15T12:00:05Z", "end_time": None},
        ])
        snap = create_checkpoint(
            session_id="s-reset",
            trigger="step_complete",
            graph=graph_snap,
            event_log_path=ev_dir / "events_s-reset.ndjson",
            checkpoint_dir=cp_dir,
        )
        loaded = load_checkpoint("s-reset", snap.checkpoint_id, checkpoint_dir=cp_dir)
        context, result = restore_from_checkpoint(loaded, raise_on_violation=False)
        assert context.plan_graph.nodes["StepA"]["status"] == "pending"
        assert "StepA" in result.reset_node_ids


def test_15_verify_restoration_invariants_no_running_nodes() -> None:
    """verify_restoration_invariants catches running nodes as a violation."""
    import networkx as nx
    from session.rewind import verify_restoration_invariants

    graph_snap = _make_graph_snapshot([
        {"id": "ROOT", "agent": "System", "status": "completed"},
        {"id": "StepX", "agent": "CoderAgent", "status": "running"},
    ])
    g = nx.DiGraph()
    g.add_node("ROOT", agent="System", status="completed")
    g.add_node("StepX", agent="CoderAgent", status="running")

    violations = verify_restoration_invariants(graph_snap, g)
    assert any("running" in v for v in violations)


def test_16_list_available_checkpoints_returns_nonempty_after_create() -> None:
    """list_available_checkpoints returns entries after a checkpoint is created."""
    from session.checkpoint import create_checkpoint
    from session.rewind import list_available_checkpoints

    with tempfile.TemporaryDirectory() as tmp:
        cp_dir = Path(tmp) / "cp"
        ev_dir = Path(tmp) / "ev"
        ev_dir.mkdir()
        graph_snap = _make_graph_snapshot([{"id": "ROOT", "agent": "System", "status": "completed"}])
        create_checkpoint(
            session_id="s-list",
            trigger="manual",
            graph=graph_snap,
            event_log_path=ev_dir / "events_s-list.ndjson",
            checkpoint_dir=cp_dir,
        )
        checkpoints = list_available_checkpoints("s-list", checkpoint_dir=cp_dir)
        assert len(checkpoints) >= 1
        assert "checkpoint_id" in checkpoints[0]
        assert "trigger" in checkpoints[0]
