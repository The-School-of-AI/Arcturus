"""
P05 Chronicle: Deterministic checkpoint snapshot flow.

Creates content-addressable checkpoints from session state.
Flow: capture events -> snapshot graph -> compute hash -> persist.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from session.schema import CheckpointSnapshot

# Checkpoint storage
DEFAULT_CHECKPOINT_DIR = Path(__file__).parent.parent / "memory" / "chronicle_checkpoints"
DEFAULT_EVENT_LOG_DIR = Path(__file__).parent.parent / "memory" / "chronicle_events"


def _load_events_until_sequence(log_path: Path, last_sequence: int) -> list[dict]:
    """Load event entries from ndjson up to last_sequence inclusive."""
    if not log_path.exists():
        return []
    entries = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("sequence", 0) <= last_sequence:
                    entries.append(obj)
            except json.JSONDecodeError:
                continue
    return entries


def _graph_to_serializable(graph: Any) -> dict:
    """Convert NetworkX graph to JSON-serializable dict (node_link_data format)."""
    try:
        import networkx as nx

        if hasattr(graph, "nodes"):
            return nx.node_link_data(graph)
    except ImportError:
        pass
    if isinstance(graph, dict):
        return graph
    return {}


def create_checkpoint(
    session_id: str,
    trigger: str,
    graph: Any,
    event_log_path: Optional[Path] = None,
    last_sequence: Optional[int] = None,
    checkpoint_dir: Optional[Path] = None,
    created_at: Optional[str] = None,
) -> CheckpointSnapshot:
    """
    Create a deterministic checkpoint snapshot.

    Flow:
    1. Serialize graph to node_link_data
    2. Load event entries up to last_sequence
    3. Build CheckpointSnapshot
    4. Compute content hash
    5. Persist to checkpoint dir

    Returns the snapshot (also written to disk).
    """
    cp_dir = checkpoint_dir or DEFAULT_CHECKPOINT_DIR
    events_file = event_log_path or (DEFAULT_EVENT_LOG_DIR / f"events_{session_id}.ndjson")

    graph_snap = _graph_to_serializable(graph)
    events = _load_events_until_sequence(events_file, last_sequence or 0)
    event_count = len(events)

    snapshot = CheckpointSnapshot(
        checkpoint_id="",  # Set after hash
        session_id=session_id,
        trigger=trigger,
        created_at=created_at or (datetime.utcnow().isoformat() + "Z"),
        event_count=event_count,
        last_sequence=last_sequence or 0,
        graph_snapshot=graph_snap,
        event_entries=events,
        content_hash="",
    )
    cid = snapshot.compute_content_hash()
    snapshot.checkpoint_id = cid

    # Persist
    cp_dir.mkdir(parents=True, exist_ok=True)
    session_cp_dir = cp_dir / session_id
    session_cp_dir.mkdir(parents=True, exist_ok=True)
    cp_file = session_cp_dir / f"checkpoint_{cid}.json"
    with open(cp_file, "w", encoding="utf-8") as f:
        f.write(snapshot.to_canonical_json())

    return snapshot


def list_checkpoints(
    session_id: str,
    checkpoint_dir: Optional[Path] = None,
) -> list[dict]:
    """List checkpoints for a session, sorted by created_at."""
    cp_dir = checkpoint_dir or DEFAULT_CHECKPOINT_DIR
    session_cp_dir = cp_dir / session_id
    if not session_cp_dir.exists():
        return []
    results = []
    for p in session_cp_dir.glob("checkpoint_*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            results.append(
                {
                    "checkpoint_id": data.get("checkpoint_id", ""),
                    "trigger": data.get("trigger", ""),
                    "created_at": data.get("created_at", ""),
                    "event_count": data.get("event_count", 0),
                }
            )
        except (json.JSONDecodeError, OSError):
            continue
    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return results


def load_checkpoint(
    session_id: str,
    checkpoint_id: str,
    checkpoint_dir: Optional[Path] = None,
) -> Optional[CheckpointSnapshot]:
    """Load a checkpoint by id."""
    cp_dir = checkpoint_dir or DEFAULT_CHECKPOINT_DIR
    cp_file = cp_dir / session_id / f"checkpoint_{checkpoint_id}.json"
    if not cp_file.exists():
        return None
    try:
        data = json.loads(cp_file.read_text(encoding="utf-8"))
        return CheckpointSnapshot.model_validate(data)
    except (json.JSONDecodeError, Exception):
        return None
