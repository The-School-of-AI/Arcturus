"""WebChat channel adapter for Arcturus gateway.

Provides send/receive functionality for the embedded WebChat widget.
This is a built-in channel served directly from the Arcturus gateway.

Outbox model (Week 1):
  - Each browser session gets a bounded per-session deque (maxlen=200).
  - send_message() appends to the session's outbox.
  - drain_outbox() returns all pending messages and clears the queue.
  - The /api/nexus/webchat/messages/{session_id} endpoint calls drain_outbox()
    so the widget can poll for replies.
"""

import uuid
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

from channels.base import ChannelAdapter


class WebChatAdapter(ChannelAdapter):
    """WebChat channel adapter.

    Handles messages from the embeddable WebChat widget.
    Outbound messages are queued per-session and drained by the polling endpoint.
    """

    # Class-level outbox: session_id → bounded deque of message dicts.
    # Using a class-level dict ensures all references to any WebChatAdapter
    # instance share the same outbox store (singleton-like within a process).
    _outboxes: Dict[str, deque] = {}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize WebChat adapter."""
        super().__init__("webchat", config)

    def get_outbox(self, session_id: str) -> deque:
        """Return the outbox deque for *session_id*, creating it if needed.

        Args:
            session_id: WebChat session identifier.

        Returns:
            Bounded deque (maxlen=200) for this session.
        """
        if session_id not in WebChatAdapter._outboxes:
            WebChatAdapter._outboxes[session_id] = deque(maxlen=200)
        return WebChatAdapter._outboxes[session_id]

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> Dict[str, Any]:
        """Enqueue an outbound message to a WebChat session.

        In production this would push via WebSocket. For now, messages are
        stored in the per-session outbox and retrieved by the polling endpoint.

        Args:
            recipient_id: WebChat session_id (browser tab / user instance).
            content: Formatted message text (HTML from WebChatFormatter).
            **kwargs: Reserved for future options (priority, tags, etc.).

        Returns:
            Dict with message_id and success flag.
        """
        msg: Dict[str, Any] = {
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "channel": "webchat",
            "recipient_id": recipient_id,
            "content": content,
        }
        self.get_outbox(recipient_id).append(msg)
        return {"message_id": msg["message_id"], "success": True}

    def drain_outbox(self, session_id: str) -> List[Dict[str, Any]]:
        """Return all pending outbound messages for *session_id* and clear the queue.

        Called by the polling endpoint so the widget can consume replies.

        Args:
            session_id: WebChat session identifier.

        Returns:
            List of message dicts (may be empty).
        """
        outbox = self.get_outbox(session_id)
        messages = list(outbox)
        outbox.clear()
        return messages

    async def initialize(self) -> None:
        """Initialize the WebChat adapter.

        In production: sets up WebSocket handlers and session management.
        """
        pass

    async def shutdown(self) -> None:
        """Gracefully shutdown the WebChat adapter."""
        WebChatAdapter._outboxes.clear()
