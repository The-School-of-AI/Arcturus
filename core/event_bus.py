import asyncio
import logging
from typing import Dict, List, Any, Callable, Awaitable
from datetime import datetime
import json
from collections import deque

logger = logging.getLogger("event_bus")

class EventBus:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._subscribers: List[asyncio.Queue] = []
            cls._instance._history = deque(maxlen=100) # Keep last 100 events
        return cls._instance

    async def publish(self, event_type: str, source: str, data: Dict[str, Any]):
        """Publish an event to all subscribers."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "source": source,
            "data": data
        }
        
        # Add to history
        self._history.append(event)
        
        # Log to console
        logger.debug(f"Event: {event_type} from {source}")

        # Broadcast to all active queues
        # Use list copy to avoid modification during iteration issues if sub disconnects
        for q in list(self._instance._subscribers):
            try:
                await q.put(event)
            except Exception as e:
                logger.error(f"Failed to push to subscriber: {e}")

    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to the event stream."""
        q = asyncio.Queue()
        self._subscribers.append(q)
        
        # Replay history? Configurable.
        # For now, let's replay the last 5 events to give context
        for event in list(self._history)[-5:]:
            await q.put(event)
            
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

# Global Instance
event_bus = EventBus()
