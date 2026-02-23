"""Nexus gateway router.

Exposes the Unified Message Bus over HTTP so the WebChat widget (and future
channel adapters) can send/receive messages through the Arcturus agent core.

Endpoints
---------
POST /api/nexus/webchat/inbound
    Receive an inbound WebChat message, route it through the bus (agent
    processing + outbound delivery to the session outbox).

GET  /api/nexus/webchat/messages/{session_id}
    Poll for queued outbound messages for a WebChat session. Each call drains
    and returns all pending messages (fire-and-forget delivery model).
"""

import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from gateway.envelope import MessageEnvelope

router = APIRouter(prefix="/nexus", tags=["Nexus"])

# Lazy reference to the shared MessageBus singleton.
# We defer import so that this module can be imported safely at startup
# before gateway components are fully initialized.
_bus = None


def _get_bus():
    global _bus
    if _bus is None:
        from shared.state import get_message_bus
        _bus = get_message_bus()
    return _bus


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class WebChatInboundRequest(BaseModel):
    """Inbound WebChat message from the widget."""

    session_id: str
    sender_id: str
    sender_name: str
    text: str
    message_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/webchat/inbound")
async def webchat_inbound(req: WebChatInboundRequest):
    """Receive a message from the WebChat widget.

    Builds a ``MessageEnvelope``, runs it through the bus (agent processing +
    formatted reply enqueued in the session outbox), and returns the bus result.

    The widget should follow up with GET ``/api/nexus/webchat/messages/{session_id}``
    to fetch the agent's reply.
    """
    envelope = MessageEnvelope.from_webchat(
        session_id=req.session_id,
        sender_id=req.sender_id,
        sender_name=req.sender_name,
        text=req.text,
        message_id=req.message_id or str(uuid.uuid4()),
    )
    result = await _get_bus().roundtrip(envelope)
    return result.to_dict()


@router.get("/webchat/messages/{session_id}")
async def webchat_poll(session_id: str):
    """Poll for pending outbound messages for a WebChat session.

    Drains the session outbox — each message is returned exactly once.
    Returns an empty list if no messages are queued.
    """
    bus = _get_bus()
    adapter = bus.adapters.get("webchat")
    messages = adapter.drain_outbox(session_id) if adapter else []
    return {
        "session_id": session_id,
        "messages": messages,
        "count": len(messages),
    }
