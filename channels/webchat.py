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

import asyncio
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

    # Class-level SSE subscriber registry: session_id → list of asyncio.Queue.
    # send_message() pushes to these queues so live SSE connections receive
    # replies immediately without polling.
    _sse_queues: Dict[str, List[asyncio.Queue]] = {}

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

    async def send_typing_indicator(self, recipient_id: str, **kwargs) -> None:
        """Push a typing event to all SSE subscribers for this session."""
        for q in list(WebChatAdapter._sse_queues.get(recipient_id, [])):
            try:
                q.put_nowait({"type": "typing", "session_id": recipient_id})
            except asyncio.QueueFull:
                pass

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
        media_attachments = kwargs.get("attachments", [])
        msg: Dict[str, Any] = {
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "channel": "webchat",
            "recipient_id": recipient_id,
            "content": content,
        }
        if media_attachments:
            msg["attachments"] = [
                {"media_type": a.media_type, "url": a.url,
                 "filename": a.filename, "mime_type": a.mime_type}
                for a in media_attachments
            ]
        self.get_outbox(recipient_id).append(msg)
        # Push to any live SSE subscriber queues for this session.
        for q in list(WebChatAdapter._sse_queues.get(recipient_id, [])):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass
        return {"message_id": msg["message_id"], "success": True}

    def subscribe_sse(self, session_id: str) -> asyncio.Queue:
        """Register a new SSE subscriber queue for *session_id*.

        The returned queue receives a copy of every message delivered to the
        session via send_message().  The caller is responsible for calling
        unsubscribe_sse() when the SSE connection closes.

        Args:
            session_id: WebChat session identifier.

        Returns:
            asyncio.Queue that will receive outbound message dicts.
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        if session_id not in WebChatAdapter._sse_queues:
            WebChatAdapter._sse_queues[session_id] = []
        WebChatAdapter._sse_queues[session_id].append(q)
        return q

    def unsubscribe_sse(self, session_id: str, q: asyncio.Queue) -> None:
        """Remove a previously registered SSE subscriber queue.

        Args:
            session_id: WebChat session identifier.
            q: The queue returned by subscribe_sse().
        """
        queues = WebChatAdapter._sse_queues.get(session_id, [])
        if q in queues:
            queues.remove(q)

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
        WebChatAdapter._sse_queues.clear()
