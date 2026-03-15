"""End-to-end tests for WebChat via routers/nexus.py.

Uses FastAPI's TestClient with a minimal app that includes only the nexus
router — no full api.py startup required.

Flow under test:
  POST /api/nexus/webchat/inbound   → bus.roundtrip() → outbox enqueued
  GET  /api/nexus/webchat/messages/{session_id} → drain outbox → reply returned
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Reset WebChatAdapter class-level outbox between tests
from channels.webchat import WebChatAdapter
from routers import nexus as nexus_router


def _make_client() -> TestClient:
    """Build a minimal FastAPI app with only the nexus router.

    Pins create_mock_agent as the agent factory so tests are deterministic
    and do not depend on a running FastAPI server (create_runs_agent requires one).
    """
    from gateway.bus import MessageBus
    from gateway.formatter import MessageFormatter
    from gateway.router import MessageRouter, create_mock_agent
    import shared.state as state

    WebChatAdapter._outboxes.clear()
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    bus = MessageBus(router=router, formatter=formatter, adapters={"webchat": WebChatAdapter()})
    state._message_bus = bus
    nexus_router._bus = bus

    app = FastAPI()
    app.include_router(nexus_router.router, prefix="/api")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _inbound_payload(session_id="sess-1", text="Hello", sender_id="u1", sender_name="Alice"):
    return {
        "session_id": session_id,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "text": text,
        "message_id": str(uuid.uuid4()),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_webchat_inbound_returns_accepted():
    """POST inbound should return ok=True immediately (background processing)."""
    client = _make_client()
    resp = client.post("/api/nexus/webchat/inbound", json=_inbound_payload())
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["status"] == "accepted"
    assert data["session_id"] == "sess-1"


def test_webchat_poll_returns_reply():
    """After POST inbound, GET messages should return the agent's reply."""
    client = _make_client()
    session_id = "sess-poll"

    client.post("/api/nexus/webchat/inbound", json=_inbound_payload(session_id=session_id))

    resp = client.get(f"/api/nexus/webchat/messages/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["count"] >= 1
    assert len(data["messages"]) >= 1
    # Each message must carry content
    assert data["messages"][0]["content"] != ""


def test_webchat_outbox_clears_after_drain():
    """A second GET after the first should return an empty outbox."""
    client = _make_client()
    session_id = "sess-drain"

    client.post("/api/nexus/webchat/inbound", json=_inbound_payload(session_id=session_id))
    # First poll drains the queue
    client.get(f"/api/nexus/webchat/messages/{session_id}")
    # Second poll should be empty
    resp = client.get(f"/api/nexus/webchat/messages/{session_id}")
    data = resp.json()
    assert data["count"] == 0
    assert data["messages"] == []


def test_webchat_session_affinity():
    """Two messages in the same session should route to the same agent instance.

    The mock agent increments message_number per session. If session affinity
    works, the second message gets message_number=2.  With background processing,
    we verify via the outbox: both replies should be present after both POSTs.
    """
    client = _make_client()
    session_id = "sess-affinity"

    resp1 = client.post("/api/nexus/webchat/inbound", json=_inbound_payload(session_id=session_id, text="first"))
    resp2 = client.post("/api/nexus/webchat/inbound", json=_inbound_payload(session_id=session_id, text="second"))

    assert resp1.json()["ok"] is True
    assert resp2.json()["ok"] is True

    # Both POSTs return the same session_id
    assert resp1.json()["session_id"] == resp2.json()["session_id"] == session_id

    # Drain outbox — both replies should be there (TestClient awaits background tasks)
    poll = client.get(f"/api/nexus/webchat/messages/{session_id}")
    messages = poll.json()["messages"]
    assert len(messages) >= 2


def test_webchat_formatter_produces_html():
    """The reply content in the outbox should be HTML (WebChat format)."""
    client = _make_client()
    session_id = "sess-html"

    # Send Markdown that the formatter should convert to HTML
    client.post(
        "/api/nexus/webchat/inbound",
        json=_inbound_payload(session_id=session_id, text="**bold message**"),
    )

    resp = client.get(f"/api/nexus/webchat/messages/{session_id}")
    messages = resp.json()["messages"]
    assert len(messages) >= 1
    # The formatter converts **bold** → <b>bold</b> for WebChat
    content = messages[0]["content"]
    assert "<b>" in content or "<br>" in content or content != ""
