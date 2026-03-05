"""Mobile app channel adapter for Arcturus gateway.

Provides send/receive functionality for the native mobile app.
This is a built-in channel served directly from the Arcturus gateway.

Outbox model (Week 1):
  - Each mobile session gets a bounded per-session deque (maxlen=200).
  - send_message() appends to the session's outbox.
  - drain_outbox() returns all pending messages and clears the queue.
  - The /api/nexus/mobile/messages/{session_id} endpoint calls drain_outbox()
    so the app can poll for replies.
"""

import uuid
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional
from core.utils import log_step


from channels.base import ChannelAdapter


class MobileAdapter(ChannelAdapter):
    """Mobile app channel adapter.

    Handles messages from the native mobile app (React Native / Expo).
    Outbound messages are queued per-session and drained by the polling endpoint.
    """

    # Class-level outbox: session_id -> bounded deque of message dicts.
    _outboxes: Dict[str, deque] = {}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Mobile adapter."""
        super().__init__("mobile", config)

    def get_outbox(self, session_id: str) -> deque:
        """Return the outbox deque for *session_id*, creating it if needed."""
        if session_id not in MobileAdapter._outboxes:
            MobileAdapter._outboxes[session_id] = deque(maxlen=200)
        return MobileAdapter._outboxes[session_id]

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> Dict[str, Any]:
        """Enqueue an outbound message to a mobile session."""
        msg: Dict[str, Any] = {
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "channel": "mobile",
            "recipient_id": recipient_id,
            "content": content,
            "metadata": kwargs.get("metadata", {}),
        }
        self.get_outbox(recipient_id).append(msg)
        return {"message_id": msg["message_id"], "success": True}

    def drain_outbox(self, session_id: str) -> List[Dict[str, Any]]:
        """Return all pending outbound messages for *session_id* and clear the queue."""
        outbox = self.get_outbox(session_id)
        messages = list(outbox)
        outbox.clear()
        return messages

    def acknowledge_messages(self, session_id: str, message_ids: List[str]):
        """Acknowledge receipt of messages (placeholder for robust delivery)."""
        log_step(f"ACK received for {len(message_ids)} messages in session {session_id}")

    def nack_messages(self, session_id: str, messages: List[Dict[str, Any]]):
        """Re-enqueue messages that failed to sync on the mobile device."""
        outbox = self.get_outbox(session_id)
        # Re-enqueue at the front of the outbox (FIFO priority)
        for msg in reversed(messages):
            outbox.appendleft(msg)
        log_step(f"NACK received: re-enqueued {len(messages)} messages for session {session_id}")

    async def initialize(self) -> None:
        """Initialize the Mobile adapter."""
        pass

    async def shutdown(self) -> None:
        """Gracefully shutdown the Mobile adapter."""
        MobileAdapter._outboxes.clear()
