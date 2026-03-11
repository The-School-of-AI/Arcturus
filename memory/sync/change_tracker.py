"""
P11 Phase 4 Sync Engine — build push payload from local store.

Scans Qdrant memories and Neo4j spaces with sync metadata; filters by sync_policy.
"""

from datetime import datetime
from typing import Any, Callable

from memory.space_constants import SPACE_ID_GLOBAL
from memory.sync.policy import should_sync_space
from memory.sync.schema import MemoryDelta, SpaceDelta, SyncChange


def build_memory_deltas(
    memories: list[dict[str, Any]],
    *,
    device_id: str,
    get_policy: Callable[[str], str] | None = None,
) -> list[MemoryDelta]:
    """
    Build MemoryDelta list from memory records. Only include those in syncable spaces.
    """
    deltas: list[MemoryDelta] = []
    for m in memories:
        space_id = m.get("space_id") or SPACE_ID_GLOBAL
        if not should_sync_space(space_id, get_policy):
            continue
        payload = {k: v for k, v in m.items() if k != "text"}
        deltas.append(
            MemoryDelta(
                memory_id=str(m.get("id", "")),
                text=m.get("text", ""),
                payload=payload,
                version=int(m.get("version", 1)),
                device_id=m.get("device_id", device_id),
                updated_at=m.get("updated_at", datetime.now().isoformat()),
                deleted=bool(m.get("deleted", False)),
            )
        )
    return deltas


def build_space_deltas(
    spaces: list[dict[str, Any]],
    *,
    device_id: str,
) -> list[SpaceDelta]:
    """
    Build SpaceDelta list from space records. Space metadata always syncs
    (so all devices see the list and sync_policy). Content filtering is separate.
    """
    deltas: list[SpaceDelta] = []
    for s in spaces:
        deltas.append(
            SpaceDelta(
                space_id=str(s.get("space_id", "")),
                name=s.get("name", ""),
                description=s.get("description", ""),
                sync_policy=s.get("sync_policy", "sync"),
                version=int(s.get("version", 1)),
                device_id=s.get("device_id", device_id),
                updated_at=s.get("updated_at", datetime.now().isoformat()),
                deleted=bool(s.get("deleted", False)),
            )
        )
    return deltas


def build_push_changes(
    memory_deltas: list[MemoryDelta],
    space_deltas: list[SpaceDelta],
) -> list[SyncChange]:
    """Convert deltas to SyncChange list for push request."""
    out: list[SyncChange] = []
    for m in memory_deltas:
        out.append(SyncChange.from_memory(m))
    for s in space_deltas:
        out.append(SyncChange.from_space(s))
    return out
