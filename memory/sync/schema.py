"""
P11 Phase 4 Sync Engine — Pydantic models for sync protocol.

Push: client sends batch of changes (memory, space).
Pull: client requests changes since cursor; server returns changes + new cursor.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


# --- Per-entity deltas ---


class MemoryDelta(BaseModel):
    """Syncable memory change. Text + payload from Qdrant."""

    memory_id: str
    text: str
    payload: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    device_id: str = ""
    updated_at: str = ""  # ISO8601
    deleted: bool = False


class SpaceDelta(BaseModel):
    """Syncable space metadata change. From Neo4j Space node."""

    space_id: str
    name: str = ""
    description: str = ""
    sync_policy: str = "sync"  # sync | local_only
    version: int = 1
    device_id: str = ""
    updated_at: str = ""  # ISO8601
    deleted: bool = False


class EpisodicDelta(BaseModel):
    """Phase B: Syncable episodic change. From Qdrant arcturus_episodic."""

    episodic_id: str  # session_id (point id)
    session_id: str
    user_id: str
    space_id: str
    skeleton_json: str
    original_query: str = ""
    outcome: str = "completed"
    version: int = 1
    device_id: str = ""
    updated_at: str = ""  # ISO8601
    deleted: bool = False


# --- Sync change (union type) ---

SyncChangeType = Literal["memory", "space", "episodic"]


class SyncChange(BaseModel):
    """Single change in push/pull stream."""

    type: SyncChangeType
    payload: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    updated_at: str = ""
    deleted: bool = False

    @classmethod
    def from_memory(cls, m: MemoryDelta) -> "SyncChange":
        return cls(
            type="memory",
            payload={
                "memory_id": m.memory_id,
                "text": m.text,
                "payload": m.payload,
                "device_id": m.device_id,
            },
            version=m.version,
            updated_at=m.updated_at,
            deleted=m.deleted,
        )

    @classmethod
    def from_space(cls, s: SpaceDelta) -> "SyncChange":
        return cls(
            type="space",
            payload={
                "space_id": s.space_id,
                "name": s.name,
                "description": s.description,
                "sync_policy": s.sync_policy,
                "device_id": s.device_id,
            },
            version=s.version,
            updated_at=s.updated_at,
            deleted=s.deleted,
        )

    @classmethod
    def from_episodic(cls, e: EpisodicDelta) -> "SyncChange":
        return cls(
            type="episodic",
            payload={
                "episodic_id": e.episodic_id,
                "session_id": e.session_id,
                "user_id": e.user_id,
                "space_id": e.space_id,
                "skeleton_json": e.skeleton_json,
                "original_query": e.original_query,
                "outcome": e.outcome,
                "device_id": e.device_id,
            },
            version=e.version,
            updated_at=e.updated_at,
            deleted=e.deleted,
        )


# --- Push request/response ---


class PushRequest(BaseModel):
    """POST /sync/push body."""

    user_id: str
    device_id: str
    changes: list[SyncChange] = Field(default_factory=list)


class PushResponse(BaseModel):
    """POST /sync/push response."""

    accepted: bool = True
    cursor: str = ""
    errors: list[str] = Field(default_factory=list)


# --- Pull request/response ---


class PullRequest(BaseModel):
    """POST /sync/pull body."""

    user_id: str
    device_id: str
    since_cursor: str = ""


class PullResponse(BaseModel):
    """POST /sync/pull response."""

    changes: list[SyncChange] = Field(default_factory=list)
    cursor: str = ""
