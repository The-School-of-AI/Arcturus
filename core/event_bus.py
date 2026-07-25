import asyncio
import json
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("event_bus")

# Persist events to disk
_EVENTS_FILE = Path(__file__).parent.parent / "data" / "system" / "event_log.jsonl"

_REPLAY_COUNT = 50  # Events replayed to new subscribers
_MAX_HISTORY = 200  # In-memory ring buffer size
_HEARTBEAT_INTERVAL = 30  # seconds


def _load_events_from_disk(limit: int = _REPLAY_COUNT) -> list[dict]:
    """Load the last `limit` events from the persistent log."""
    if not _EVENTS_FILE.exists():
        return []
    try:
        lines = _EVENTS_FILE.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []

    events: list[dict] = []
    for raw in lines[-limit:]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            events.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return events


def _append_event_to_disk(event: dict) -> None:
    """Append a single event to the persistent JSONL log."""
    try:
        if not _EVENTS_FILE.parent.exists():
            _EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _EVENTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        logger.warning("Failed to persist event to disk")


class EventBus:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            inst = super(EventBus, cls).__new__(cls)
            inst._subscribers: List[asyncio.Queue] = []
            inst._history: deque = deque(maxlen=_MAX_HISTORY)
            inst._heartbeat_task = None
            inst._initialized = False
            cls._instance = inst
        return cls._instance

    def initialize(self):
        """Load persisted history and start heartbeat. Call once at app startup."""
        if self._initialized:
            return
        # Restore history from disk
        for ev in _load_events_from_disk(_MAX_HISTORY):
            self._history.append(ev)
        logger.info(f"EventBus: restored {len(self._history)} events from disk")
        self._initialized = True

    def start_heartbeat(self):
        """Start the periodic heartbeat task. Must be called inside a running event loop."""
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """Publish a heartbeat event every _HEARTBEAT_INTERVAL seconds."""
        try:
            while True:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                await self.publish(
                    "heartbeat",
                    "system",
                    {"status": "alive", "subscribers": len(self._subscribers)},
                    persist=False,  # Don't clutter disk with heartbeats
                )
        except asyncio.CancelledError:
            pass

    async def publish(
        self, event_type: str, source: str, data: Dict[str, Any], *, persist: bool = True
    ):
        """Publish an event to all subscribers."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "source": source,
            "data": data,
        }

        # Add to in-memory history
        self._history.append(event)

        # Persist to disk (skip heartbeats and other ephemeral events)
        if persist:
            _append_event_to_disk(event)
        logger.debug(f"Event: {event_type} from {source}")

        # Broadcast to all active queues
        for q in list(self._subscribers):
            try:
                await q.put(event)
            except Exception as e:
                logger.error(f"Failed to push to subscriber: {e}")

    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to the event stream. Replays last _REPLAY_COUNT events."""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)

        # Replay recent history so the console isn't empty on connect
        for event in list(self._history)[-_REPLAY_COUNT:]:
            await q.put(event)

        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)


# Global Instance
event_bus = EventBus()
