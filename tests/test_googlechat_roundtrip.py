"""Unit and integration tests for the Google Chat channel adapter and webhook endpoint.

Tests cover:
1. GoogleChatAdapter.send_message() happy path via webhook URL (mocked httpx)
2. GoogleChatAdapter.send_message() API error (non-2xx response)
3. GoogleChatAdapter.send_message() network/transport error
4. GoogleChatAdapter.send_message() with no credentials returns error dict
5. Full bus.roundtrip() via MessageBus with mocked Google Chat delivery
6. Session affinity: two messages in the same Space route to the same session
7. POST /nexus/googlechat/events — MESSAGE event routes through bus
8. POST /nexus/googlechat/events — ADDED_TO_SPACE lifecycle event returns empty text

No real Google Chat credentials are needed — httpx.AsyncClient.post is patched.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from channels.googlechat import GoogleChatAdapter
from gateway.bus import MessageBus
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent
from routers import nexus as nexus_router
import shared.state as state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ok_response(message_name: str = "spaces/SPACE1/messages/MSG1") -> MagicMock:
    """Build a mock httpx Response that Google Chat returns on success (HTTP 200)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "name": message_name,
        "createTime": "2026-02-27T10:00:00.000000Z",
        "text": "reply",
    }
    return mock_resp


def _make_error_response(status: int = 403, message: str = "Permission denied") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.json.return_value = {"error": {"code": status, "message": message}}
    return mock_resp


def _make_adapter_with_webhook() -> GoogleChatAdapter:
    """Return a GoogleChatAdapter configured with a dummy webhook URL."""
    return GoogleChatAdapter(config={"webhook_url": "https://chat.googleapis.com/v1/spaces/SPACE1/messages?key=TOKEN"})


def _make_bus_with_googlechat(adapter: GoogleChatAdapter) -> MessageBus:
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    return MessageBus(
        router=router,
        formatter=formatter,
        adapters={"googlechat": adapter},
    )


def _googlechat_envelope(
    space_name: str = "spaces/SPACE1",
    text: str = "Hello Arcturus",
) -> MessageEnvelope:
    return MessageEnvelope.from_googlechat(
        space_name=space_name,
        sender_id="users/12345",
        sender_name="Alice",
        text=text,
        message_name=f"{space_name}/messages/MSG1",
    )


def _make_nexus_client() -> TestClient:
    """Minimal FastAPI app with the nexus router for webhook tests.

    Injects a bus with a no-token GoogleChatAdapter so verification is skipped.
    """
    adapter = GoogleChatAdapter(config={"webhook_url": "https://chat.googleapis.com/v1/spaces/SPACE1/messages?key=TOKEN"})
    bus = _make_bus_with_googlechat(adapter)
    state._message_bus = bus
    nexus_router._bus = bus
    app = FastAPI()
    app.include_router(nexus_router.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# GoogleChatAdapter unit tests
# ---------------------------------------------------------------------------


def test_googlechat_send_message_success():
    """send_message() returns success=True and message_id when Google Chat responds 200."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ):
            adapter = _make_adapter_with_webhook()
            result = await adapter.send_message("spaces/SPACE1", "**Hello** world!")

        assert result["success"] is True
        assert result["message_id"] == "spaces/SPACE1/messages/MSG1"
        assert result["channel"] == "googlechat"
        assert result.get("error") is None

    asyncio.run(_run())


def test_googlechat_send_message_api_error():
    """send_message() returns success=False when Google Chat returns a non-2xx status."""

    async def _run():
        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            return_value=_make_error_response(403, "Permission denied"),
        ):
            adapter = _make_adapter_with_webhook()
            result = await adapter.send_message("spaces/SPACE1", "hello")

        assert result["success"] is False
        assert "Permission denied" in result["error"]
        assert result["message_id"] is None

    asyncio.run(_run())


def test_googlechat_send_message_network_error():
    """send_message() returns success=False when a network error occurs."""

    async def _run():
        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("connection refused"),
        ):
            adapter = _make_adapter_with_webhook()
            result = await adapter.send_message("spaces/SPACE1", "hello")

        assert result["success"] is False
        assert "connection refused" in result["error"]

    asyncio.run(_run())


def test_googlechat_send_message_no_credentials():
    """send_message() returns a descriptive error when no credentials are configured."""

    async def _run():
        adapter = GoogleChatAdapter(config={})  # no webhook_url, no token
        result = await adapter.send_message("spaces/SPACE1", "hello")

        assert result["success"] is False
        assert "credentials" in result["error"].lower()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bus integration test — full roundtrip via MessageBus
# ---------------------------------------------------------------------------


def test_googlechat_roundtrip_via_bus():
    """bus.roundtrip() ingests a Google Chat envelope, formats reply, and delivers it."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ) as mock_post:
            adapter = _make_adapter_with_webhook()
            bus = _make_bus_with_googlechat(adapter)
            envelope = _googlechat_envelope(text="ping")
            result = await bus.roundtrip(envelope)

        assert result.success is True
        assert result.operation == "roundtrip"
        assert result.channel == "googlechat"
        # Google Chat API must have been called exactly once
        assert mock_post.call_count == 1
        # Payload must have a "text" field with non-empty content
        sent_json = mock_post.call_args.kwargs.get("json", {})
        assert isinstance(sent_json.get("text"), str)
        assert len(sent_json["text"]) > 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Session affinity test
# ---------------------------------------------------------------------------


def test_googlechat_session_affinity():
    """Two messages in the same Space route to the same agent session."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ):
            adapter = _make_adapter_with_webhook()
            bus = _make_bus_with_googlechat(adapter)

            env1 = _googlechat_envelope(space_name="spaces/SPACE99", text="first message")
            env2 = MessageEnvelope.from_googlechat(
                space_name="spaces/SPACE99",
                sender_id="users/12345",
                sender_name="Alice",
                text="second message",
                message_name="spaces/SPACE99/messages/MSG2",
            )

            r1 = await bus.ingest(env1)
            r2 = await bus.ingest(env2)

        assert r1.success is True
        assert r2.success is True
        assert r1.session_id == r2.session_id  # same space → same session

        n1 = r1.agent_response["message_number"]
        n2 = r2.agent_response["message_number"]
        assert n2 > n1

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Webhook endpoint tests — MESSAGE event + lifecycle event
# ---------------------------------------------------------------------------


def test_googlechat_webhook_message_event_returns_ok():
    """POST /googlechat/events with a MESSAGE event must return empty text response."""
    client = _make_nexus_client()

    with patch.object(
        httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
    ):
        resp = client.post(
            "/api/nexus/googlechat/events",
            json={
                "type": "MESSAGE",
                "space": {"name": "spaces/SPACE1"},
                "message": {
                    "name": "spaces/SPACE1/messages/MSG99",
                    "sender": {
                        "name": "users/99999",
                        "displayName": "Bob",
                        "type": "HUMAN",
                    },
                    "text": "@Arcturus what is 2+2?",
                    "argumentText": "what is 2+2?",
                },
            },
        )

    assert resp.status_code == 200
    # Google Chat expects a JSON body (even if empty text)
    assert "text" in resp.json()


def test_googlechat_webhook_added_to_space_returns_empty():
    """POST /googlechat/events with ADDED_TO_SPACE must return empty text silently."""
    client = _make_nexus_client()

    resp = client.post(
        "/api/nexus/googlechat/events",
        json={
            "type": "ADDED_TO_SPACE",
            "space": {"name": "spaces/SPACE1"},
        },
    )

    assert resp.status_code == 200
    assert resp.json() == {"text": ""}
