"""
P05 Chronicle: Async event capture engine.

Low-overhead, async event streaming to immutable event log.
Subscribes to event_bus and writes events to session event log.
Hardened for concurrent edits: per-session sequence, lock-protected appends.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from session.schema import EventLogEntry, EventType

# Default storage under project
DEFAULT_EVENT_LOG_DIR = Path(__file__).parent.parent / "memory" / "chronicle_events"

# Per-session write locks for concurrent-edit safety
_session_locks: dict[str, asyncio.Lock] = {}


def _get_session_lock(session_id: str) -> asyncio.Lock:
    """Get or create lock for a session (concurrent sessions = different files, same session = serialized)."""
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]


class SessionCapture:
    """
    Async event capture: appends events to an immutable event log per session.
    Non-blocking: uses queue + background writer to avoid impacting agent latency.
    Hardened: per-session sequence, lock-protected file appends for concurrent edits.
    """

    def __init__(self, event_log_dir: Optional[Path] = None):
        self.event_log_dir = event_log_dir or DEFAULT_EVENT_LOG_DIR
        self._queue: asyncio.Queue[EventLogEntry] = asyncio.Queue()
        self._writer_task: Optional[asyncio.Task] = None
        self._session_id: Optional[str] = None
        self._sequence_lock = asyncio.Lock()
        self._session_sequences: dict[str, int] = {}

    def _session_log_path(self, session_id: str) -> Path:
        """Path to session event log file."""
        self.event_log_dir.mkdir(parents=True, exist_ok=True)
        return self.event_log_dir / f"events_{session_id}.ndjson"

    def start_session(self, session_id: str) -> None:
        """Start capturing for a session."""
        self._session_id = session_id
        if session_id not in self._session_sequences:
            self._session_sequences[session_id] = 0

    async def _next_sequence(self, session_id: str) -> int:
        """Thread-safe per-session sequence increment."""
        async with self._sequence_lock:
            self._session_sequences[session_id] = self._session_sequences.get(session_id, 0) + 1
            return self._session_sequences[session_id]

    def get_last_sequence(self, session_id: str) -> int:
        """Return current sequence for session (for checkpoint last_sequence)."""
        return self._session_sequences.get(session_id, 0)

    async def emit(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        session_id: Optional[str] = None,
    ) -> None:
        """
        Emit an event (non-blocking). Queued for async write.
        """
        sid = session_id or self._session_id or "unknown"
        seq = await self._next_sequence(sid)
        entry = EventLogEntry(
            type=event_type,
            timestamp=datetime.utcnow().isoformat() + "Z",
            sequence=seq,
            session_id=sid,
            payload=payload,
        )
        await self._queue.put(entry)

    def emit_sync(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        session_id: Optional[str] = None,
    ) -> None:
        """
        Synchronous emit for use from sync contexts.
        Schedules async emit on event loop.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_thread_safe(
                lambda: asyncio.create_task(
                    self.emit(event_type, payload, session_id)
                )
            )
        except RuntimeError:
            # No running loop - skip (e.g. in tests)
            pass

    async def _writer_loop(self) -> None:
        """Background task: drain queue and append to log file."""
        while True:
            try:
                entry = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if entry is None:
                break  # Shutdown signal
            sid = entry.session_id
            path = self._session_log_path(sid)
            line = entry.to_canonical_json() + "\n"
            lock = _get_session_lock(sid)
            try:
                async with lock:
                    with open(path, "a", encoding="utf-8") as f:
                        f.write(line)
            except Exception as e:
                print(f"⚠️ Chronicle capture write failed: {e}")

    def start_writer(self) -> None:
        """Start background writer task."""
        if self._writer_task is None or self._writer_task.done():
            self._writer_task = asyncio.create_task(self._writer_loop())

    async def stop_writer(self) -> None:
        """Stop background writer (flush queue)."""
        await self._queue.put(None)
        if self._writer_task and not self._writer_task.done():
            await self._writer_task

    def get_events_path(self, session_id: str) -> Path:
        """Return path to event log for a session."""
        return self._session_log_path(session_id)


# Global capture instance (lazy init)
_capture: Optional[SessionCapture] = None


def get_capture() -> SessionCapture:
    """Get or create global SessionCapture instance."""
    global _capture
    if _capture is None:
        _capture = SessionCapture()
        _capture.start_writer()
    return _capture
