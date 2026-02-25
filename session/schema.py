"""
P05 Chronicle: Event log schema and checkpoint snapshot types.

Defines the canonical event types and structures for session capture.
Deterministic serialization ensures identical content produces identical hashes.
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# === Event Type Enum (canonical) ===
class EventType(str, Enum):
    """Canonical event types for the event log."""

    SESSION_START = "session_start"
    SESSION_END = "session_end"
    USER_PROMPT = "user_prompt"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    STEP_FAILED = "step_failed"
    AGENT_REASONING = "agent_reasoning"
    TOOL_INVOCATION = "tool_invocation"
    FILE_CHANGE = "file_change"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    CHECKPOINT_CREATED = "checkpoint_created"


# === Base Event (all events extend this) ===
class BaseEvent(BaseModel):
    """Base event with timestamp and sequence for ordering."""

    type: EventType
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    sequence: int = 0
    session_id: str = ""

    model_config = {"frozen": True, "extra": "forbid"}

    def to_canonical_json(self) -> str:
        """Produce deterministic JSON for content-addressable hashing."""
        return self.model_dump_json(sort_keys=True, exclude_none=True)


# === Concrete Event Payloads ===
class UserPromptPayload(BaseModel):
    """User prompt event: text, optional file refs, optional image refs."""

    text: str
    file_refs: list[str] = Field(default_factory=list)
    image_refs: list[str] = Field(default_factory=list)


class StepStartPayload(BaseModel):
    """Step start: step_id, agent type, description."""

    step_id: str
    agent: str
    description: str = ""


class StepCompletePayload(BaseModel):
    """Step complete: metrics and status."""

    step_id: str
    agent: str
    cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    execution_time_sec: float = 0.0
    status: str = "completed"


class StepFailedPayload(BaseModel):
    """Step failed: error message."""

    step_id: str
    agent: str
    error: str


class AgentReasoningPayload(BaseModel):
    """Agent reasoning trace (chain-of-thought, tool selection rationale)."""

    step_id: str
    agent: str
    thought: str
    turn: int = 1


class ToolInvocationPayload(BaseModel):
    """Tool invocation: name, args, result summary, duration."""

    step_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_preview: str = ""  # Truncated for storage
    duration_ms: float = 0.0
    success: bool = True


class FileChangePayload(BaseModel):
    """File change: path, operation, diff or content preview."""

    path: str
    operation: str  # "created" | "modified" | "deleted"
    diff: Optional[str] = None
    content_preview: Optional[str] = None  # First N chars for large files


class MemoryAccessPayload(BaseModel):
    """Memory read or write."""

    step_id: str = ""
    operation: str  # "read" | "write"
    key_or_query: str = ""
    summary: str = ""


class SessionMetadata(BaseModel):
    """Session metadata for session_start."""

    session_id: str
    original_query: str = ""
    user: str = ""
    agent_config: dict[str, Any] = Field(default_factory=dict)
    model_versions: dict[str, str] = Field(default_factory=dict)
    skill_set: list[str] = Field(default_factory=list)
    start_time: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class SessionEndPayload(BaseModel):
    """Session end: final status and duration."""

    session_id: str
    status: str  # "completed" | "failed" | "stopped" | "cost_exceeded"
    duration_sec: float = 0.0
    total_cost: float = 0.0
    total_tokens: int = 0


class CheckpointCreatedPayload(BaseModel):
    """Checkpoint created: id, trigger, event_count."""

    checkpoint_id: str
    trigger: str  # "step_complete" | "manual" | "commit"
    event_count: int = 0
    snapshot_hash: str = ""


# === Event Log Entry (wraps payload) ===
class EventLogEntry(BaseModel):
    """
    Full event log entry: type + payload + metadata.
    Deterministic JSON serialization for content-addressable storage.
    """

    type: EventType
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    sequence: int = 0
    session_id: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": False}  # Allow mutation for sequence assignment

    def to_canonical_json(self) -> str:
        """Produce deterministic JSON."""
        return json.dumps(
            {
                "type": self.type.value,
                "timestamp": self.timestamp,
                "sequence": self.sequence,
                "session_id": self.session_id,
                "payload": self.payload,
            },
            sort_keys=True,
            ensure_ascii=False,
        )

    def content_hash(self) -> str:
        """SHA-256 hash of canonical JSON for content-addressable IDs."""
        return hashlib.sha256(self.to_canonical_json().encode()).hexdigest()[:16]


# === Checkpoint Snapshot Schema ===
class CheckpointSnapshot(BaseModel):
    """
    Deterministic checkpoint snapshot.
    Contains full session transcript + agent state at a point in time.
    """

    checkpoint_id: str
    session_id: str
    trigger: str  # "step_complete" | "manual" | "commit"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    event_count: int = 0
    last_sequence: int = 0
    # Serialized graph (node_link_data) for restore
    graph_snapshot: dict[str, Any] = Field(default_factory=dict)
    # Event log entries up to this checkpoint (or refs)
    event_entries: list[dict[str, Any]] = Field(default_factory=list)
    # Content hash for determinism
    content_hash: str = ""

    def to_canonical_json(self) -> str:
        """Deterministic JSON for hashing."""
        return json.dumps(
            self.model_dump(),
            sort_keys=True,
            ensure_ascii=False,
        )

    def compute_content_hash(self) -> str:
        """Compute and set content_hash; return it. Hash excludes content_hash and created_at for determinism."""
        d = self.model_dump(exclude={"content_hash", "created_at"})
        canonical = json.dumps(d, sort_keys=True, ensure_ascii=False)
        self.content_hash = hashlib.sha256(canonical.encode()).hexdigest()[:24]
        return self.content_hash
