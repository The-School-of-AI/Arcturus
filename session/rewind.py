"""
P05 Chronicle: Rewind engine and state restoration invariants.

Restores an ExecutionContextManager to the exact graph state captured
in a CheckpointSnapshot, then verifies restoration invariants.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from session.checkpoint import (
    DEFAULT_CHECKPOINT_DIR,
    list_checkpoints,
    load_checkpoint,
)
from session.schema import CheckpointSnapshot

# Re-export so callers only need to import from session.rewind
__all__ = [
    "RewindError",
    "RewindResult",
    "restore_from_checkpoint",
    "rewind_to_latest",
    "list_available_checkpoints",
    "verify_restoration_invariants",
]


class RewindError(Exception):
    """Raised when state restoration fails an invariant."""


class RewindResult:
    """Result of a rewind operation."""

    def __init__(
        self,
        checkpoint: CheckpointSnapshot,
        restored_node_ids: list[str],
        reset_node_ids: list[str],
        invariants_passed: bool,
        violations: list[str],
    ) -> None:
        self.checkpoint = checkpoint
        self.restored_node_ids = restored_node_ids
        self.reset_node_ids = reset_node_ids
        self.invariants_passed = invariants_passed
        self.violations = violations

    def __repr__(self) -> str:
        return (
            f"RewindResult(checkpoint={self.checkpoint.checkpoint_id!r}, "
            f"nodes={len(self.restored_node_ids)}, "
            f"reset={len(self.reset_node_ids)}, "
            f"ok={self.invariants_passed})"
        )


def verify_restoration_invariants(
    graph_snapshot: dict,
    context_graph: "nx.DiGraph",  # type: ignore[name-defined]
) -> list[str]:
    """
    Verify that the restored graph satisfies state restoration invariants.

    Invariants:
    1. Node count matches snapshot.
    2. All node IDs from snapshot are present in the restored graph.
    3. No node has status='running' after restoration (running is reset to pending).
    4. Completed nodes have end_time set.
    5. Failed nodes have error set.

    Returns a list of violation strings (empty = all passed).
    """
    violations: list[str] = []
    snap_nodes = {n["id"]: n for n in graph_snapshot.get("nodes", [])}
    graph_node_ids = set(context_graph.nodes)

    # Invariant 1: Node count matches
    if len(snap_nodes) != len(graph_node_ids):
        violations.append(
            f"Node count mismatch: snapshot has {len(snap_nodes)}, "
            f"restored graph has {len(graph_node_ids)}"
        )

    # Invariant 2: All snapshot nodes present
    for nid in snap_nodes:
        if nid not in graph_node_ids:
            violations.append(f"Node '{nid}' from snapshot is missing in restored graph")

    # Invariant 3: No running nodes
    for nid in graph_node_ids:
        status = context_graph.nodes[nid].get("status", "")
        if status == "running":
            violations.append(f"Node '{nid}' has status='running' after restoration (must be pending or completed)")

    # Invariant 4: Completed nodes have end_time
    for nid in graph_node_ids:
        node_data = context_graph.nodes[nid]
        if node_data.get("status") == "completed" and not node_data.get("end_time"):
            violations.append(f"Completed node '{nid}' is missing 'end_time'")

    # Invariant 5: Failed nodes have error
    for nid in graph_node_ids:
        node_data = context_graph.nodes[nid]
        if node_data.get("status") == "failed" and not node_data.get("error"):
            violations.append(f"Failed node '{nid}' is missing 'error' field")

    return violations


def restore_from_checkpoint(
    checkpoint: CheckpointSnapshot,
    raise_on_violation: bool = True,
) -> "tuple[ExecutionContextManager, RewindResult]":  # type: ignore[name-defined]
    """
    Restore an ExecutionContextManager to the state captured in a CheckpointSnapshot.

    Steps:
    1. Reconstruct NetworkX graph from graph_snapshot (node_link_graph).
    2. Reset any 'running' or 'stopped' nodes to 'pending' (safe restart).
    3. Verify state restoration invariants.
    4. Return (context, RewindResult).

    Args:
        checkpoint: The CheckpointSnapshot to restore to.
        raise_on_violation: If True, raise RewindError on invariant violation.

    Returns:
        Tuple of (restored ExecutionContextManager, RewindResult).
    """
    import networkx as nx
    from memory.context import ExecutionContextManager

    graph_data = checkpoint.graph_snapshot
    if not graph_data or not graph_data.get("nodes"):
        raise RewindError(
            f"Checkpoint '{checkpoint.checkpoint_id}' has no graph snapshot data"
        )

    # Normalize edge key: older NetworkX used "links", newer uses "edges"
    if "links" in graph_data and "edges" not in graph_data:
        graph_data = {**graph_data, "edges": graph_data["links"]}

    # Reconstruct graph
    plan_graph = nx.node_link_graph(graph_data)

    # Track which nodes are reset vs restored
    restored_node_ids = list(plan_graph.nodes)
    reset_node_ids: list[str] = []

    # Reset running/stopped/waiting_input nodes to pending (invariant 3)
    for node_id in plan_graph.nodes:
        node_data = plan_graph.nodes[node_id]
        status = node_data.get("status", "")
        if status in ("running", "stopped", "waiting_input"):
            node_data["status"] = "pending"
            reset_node_ids.append(node_id)

    # Build ExecutionContextManager from restored graph (bypass __init__)
    context = ExecutionContextManager.__new__(ExecutionContextManager)
    context.plan_graph = plan_graph
    context.debug_mode = False
    context.stop_requested = False
    context.api_mode = True
    import asyncio
    context.user_input_event = asyncio.Event()
    context.user_input_value = None
    context._live_display = None
    context.multi_mcp = None  # Caller must inject

    # Verify invariants
    violations = verify_restoration_invariants(graph_data, plan_graph)
    invariants_passed = len(violations) == 0

    result = RewindResult(
        checkpoint=checkpoint,
        restored_node_ids=restored_node_ids,
        reset_node_ids=reset_node_ids,
        invariants_passed=invariants_passed,
        violations=violations,
    )

    if not invariants_passed and raise_on_violation:
        raise RewindError(
            f"Restoration invariant violations for checkpoint "
            f"'{checkpoint.checkpoint_id}':\n" + "\n".join(violations)
        )

    return context, result


def rewind_to_latest(
    session_id: str,
    checkpoint_dir: Optional[Path] = None,
    raise_on_violation: bool = True,
) -> "tuple[ExecutionContextManager, RewindResult]":  # type: ignore[name-defined]
    """
    Rewind to the most recent checkpoint for a session.

    Convenience wrapper around restore_from_checkpoint that selects
    the latest checkpoint automatically.
    """
    checkpoints = list_checkpoints(session_id, checkpoint_dir=checkpoint_dir)
    if not checkpoints:
        raise RewindError(f"No checkpoints found for session '{session_id}'")

    latest = checkpoints[0]  # list_checkpoints returns newest-first
    checkpoint = load_checkpoint(
        session_id,
        latest["checkpoint_id"],
        checkpoint_dir=checkpoint_dir,
    )
    if checkpoint is None:
        raise RewindError(
            f"Could not load checkpoint '{latest['checkpoint_id']}' "
            f"for session '{session_id}'"
        )

    return restore_from_checkpoint(checkpoint, raise_on_violation=raise_on_violation)


def list_available_checkpoints(
    session_id: str,
    checkpoint_dir: Optional[Path] = None,
) -> list[dict]:
    """
    Return list of available checkpoints for a session, newest first.
    Each entry: {checkpoint_id, trigger, created_at, event_count}
    """
    return list_checkpoints(session_id, checkpoint_dir=checkpoint_dir)
