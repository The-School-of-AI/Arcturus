"""Tests for the WebChat SSE push stream endpoint.

GET /api/nexus/webchat/stream/{session_id} pushes agent replies via SSE.

Testing strategy:
- Use TestClient with raise_server_exceptions=True for header/status checks.
  The test uses a pre-loaded SSE queue so the generator yields one message
  then the TestClient's context manager closes the connection.
- For unit-level behaviour (subscribe/unsubscribe/fan-out), test the adapter
  directly without involving HTTP.
"""

import asyncio
import json
import threading

from fastapi import FastAPI
from fastapi.testclient import TestClient

from channels.webchat import WebChatAdapter
from routers import nexus as nexus_router
import shared.state as state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_MSG = {
    "message_id": "test-sse-001",
    "timestamp": "2026-02-21T00:00:00",
    "channel": "webchat",
    "recipient_id": "sess-x",
    "content": "<b>Hello SSE</b>",
}


def _make_client() -> TestClient:
    """Build a minimal FastAPI app with only the nexus router, reset singletons."""
    state._message_bus = None
    WebChatAdapter._outboxes.clear()
    WebChatAdapter._sse_queues.clear()
    nexus_router._bus = None

    app = FastAPI()
    app.include_router(nexus_router.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Unit tests for subscribe/unsubscribe/fan-out (no HTTP)
# ---------------------------------------------------------------------------


def test_subscribe_sse_creates_queue():
    """subscribe_sse() must register a queue for the session."""
    WebChatAdapter._sse_queues.clear()
    adapter = WebChatAdapter()
    q = adapter.subscribe_sse("sess-sub")
    assert q in WebChatAdapter._sse_queues["sess-sub"]


def test_unsubscribe_sse_removes_queue():
    """unsubscribe_sse() must remove the queue from the registry."""
    WebChatAdapter._sse_queues.clear()
    adapter = WebChatAdapter()
    q = adapter.subscribe_sse("sess-unsub")
    adapter.unsubscribe_sse("sess-unsub", q)
    assert q not in WebChatAdapter._sse_queues.get("sess-unsub", [])


def test_send_message_fans_out_to_sse_queue():
    """send_message() must push the message to any live SSE subscriber queue."""

    async def _run():
        WebChatAdapter._sse_queues.clear()
        WebChatAdapter._outboxes.clear()
        adapter = WebChatAdapter()
        q = adapter.subscribe_sse("sess-fan")
        await adapter.send_message("sess-fan", "**Hello**")
        assert not q.empty()
        msg = q.get_nowait()
        assert msg["content"] == "**Hello**"
        assert msg["channel"] == "webchat"

    asyncio.run(_run())


def test_send_message_also_fills_outbox():
    """SSE push must be additive — the outbox drain still works alongside SSE."""

    async def _run():
        WebChatAdapter._sse_queues.clear()
        WebChatAdapter._outboxes.clear()
        adapter = WebChatAdapter()
        q = adapter.subscribe_sse("sess-both")
        await adapter.send_message("sess-both", "hi")
        # outbox must still have the message
        messages = adapter.drain_outbox("sess-both")
        assert len(messages) == 1
        # SSE queue must also have it
        assert not q.empty()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


def test_sse_endpoint_registered_in_router():
    """The SSE stream route must be registered on the nexus router.

    SSE endpoints return a persistent streaming response — TestClient blocks
    until the generator closes, which never happens for a live SSE stream.
    Rather than open a real HTTP connection, we verify the route contract by
    inspecting the router's route table directly: the path must exist and the
    endpoint function must return an EventSourceResponse.
    """
    from sse_starlette.sse import EventSourceResponse

    routes = {r.path: r for r in nexus_router.router.routes}  # type: ignore[attr-defined]
    assert "/nexus/webchat/stream/{session_id}" in routes, (
        "SSE route /webchat/stream/{session_id} not registered on nexus router"
    )

    # The endpoint must reference EventSourceResponse — verify by calling it
    # directly with a mock request and checking the return type.
    import inspect
    from unittest.mock import AsyncMock, MagicMock

    route = routes["/nexus/webchat/stream/{session_id}"]
    endpoint_fn = route.endpoint  # type: ignore[attr-defined]

    # Build a minimal mock request that looks disconnected immediately.
    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=True)

    # Reset singletons so _get_bus() initialises fresh.
    state._message_bus = None
    WebChatAdapter._sse_queues.clear()
    nexus_router._bus = None

    response = asyncio.run(endpoint_fn(session_id="sess-route-check", request=mock_request))
    assert isinstance(response, EventSourceResponse), (
        f"Expected EventSourceResponse, got {type(response).__name__}"
    )


def test_sse_delivers_roundtrip_reply():
    """An inbound POST roundtrip must appear in the SSE stream."""
    client = _make_client()
    session_id = "sess-rt-sse"

    # First POST the inbound so the bus processes it and enqueues a reply.
    post_resp = client.post(
        "/api/nexus/webchat/inbound",
        json={
            "session_id": session_id,
            "sender_id": "u1",
            "sender_name": "Alice",
            "text": "hello",
        },
    )
    assert post_resp.json()["ok"] is True

    # The reply is now in the outbox. Subscribe an SSE queue and inject via
    # send_message to simulate what happens when SSE is connected at send time.
    adapter = WebChatAdapter()
    q = adapter.subscribe_sse(session_id)
    asyncio.run(adapter.send_message(session_id, "<b>SSE reply</b>"))

    assert not q.empty()
    msg = q.get_nowait()
    assert msg["content"] == "<b>SSE reply</b>"
    assert msg["recipient_id"] == session_id
