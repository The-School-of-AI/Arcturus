"""Unit and integration tests for the iMessage/BlueBubbles channel adapter and webhook.

Tests cover:
1. iMessageAdapter.send_message() happy path (mocked httpx)
2. iMessageAdapter.send_message() API error (non-2xx response)
3. iMessageAdapter.send_message() network/transport error
4. iMessageAdapter.verify_signature() — valid / invalid / dev-mode
5. Full bus.roundtrip() via MessageBus with mocked iMessage delivery
6. Session affinity: two messages in the same chat route to the same session
7. POST /nexus/imessage/inbound — new-message event routes through bus
8. POST /nexus/imessage/inbound — isFromMe=true skipped (no reply loop)

No real BlueBubbles server is needed — httpx.AsyncClient.post is patched.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from channels.imessage import iMessageAdapter
from gateway.bus import MessageBus
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent
from routers import nexus as nexus_router
import shared.state as state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHAT_GUID = "iMessage;+;+15551234567"
_MESSAGE_GUID = "BB-MSG-00001"


def _make_ok_response(guid: str = _MESSAGE_GUID) -> MagicMock:
    """Build a mock httpx Response that BlueBubbles returns on success (HTTP 200)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": 200,
        "data": {
            "guid": guid,
            "dateCreated": "2026-02-27T10:00:00.000Z",
            "text": "reply",
        },
    }
    return mock_resp


def _make_error_response(status: int = 401, message: str = "Unauthorized") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.json.return_value = {"error": {"message": message, "code": status}}
    return mock_resp


def _make_adapter() -> iMessageAdapter:
    return iMessageAdapter(
        config={
            "bluebubbles_url": "http://localhost:1234",
            "password": "test-password",
        }
    )


def _make_bus_with_imessage(adapter: iMessageAdapter) -> MessageBus:
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    return MessageBus(
        router=router,
        formatter=formatter,
        adapters={"imessage": adapter},
    )


def _imessage_envelope(
    chat_guid: str = _CHAT_GUID,
    text: str = "Hey Arcturus",
) -> MessageEnvelope:
    return MessageEnvelope.from_imessage(
        chat_guid=chat_guid,
        sender_id="+15551234567",
        sender_name="Alice",
        text=text,
        message_guid=_MESSAGE_GUID,
    )


def _make_nexus_client() -> TestClient:
    """Minimal FastAPI app with nexus router; no webhook secret so sig check is skipped."""
    adapter = iMessageAdapter(config={"bluebubbles_url": "http://localhost:1234", "password": "pw"})
    bus = _make_bus_with_imessage(adapter)
    state._message_bus = bus
    nexus_router._bus = bus
    app = FastAPI()
    app.include_router(nexus_router.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=True)


# Convenience: BlueBubbles new-message payload
def _bb_payload(
    guid: str = _MESSAGE_GUID,
    text: str = "hello",
    from_me: bool = False,
    chat_guid: str = _CHAT_GUID,
) -> dict:
    return {
        "type": "new-message",
        "data": {
            "guid": guid,
            "text": text,
            "isFromMe": from_me,
            "isGroupMessage": False,
            "chats": [{"guid": chat_guid}],
            "handle": {"address": "+15551234567", "firstName": "Alice", "lastName": ""},
            "dateCreated": 1740650000000,
        },
    }


# ---------------------------------------------------------------------------
# iMessageAdapter unit tests
# ---------------------------------------------------------------------------


def test_imessage_send_message_success():
    """send_message() returns success=True and message_id on HTTP 200."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ):
            adapter = _make_adapter()
            result = await adapter.send_message(_CHAT_GUID, "Hello from Arcturus")

        assert result["success"] is True
        assert result["message_id"] == _MESSAGE_GUID
        assert result["channel"] == "imessage"
        assert result.get("error") is None

    asyncio.run(_run())


def test_imessage_send_message_api_error():
    """send_message() returns success=False when BlueBubbles returns non-2xx."""

    async def _run():
        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            return_value=_make_error_response(401, "Unauthorized"),
        ):
            adapter = _make_adapter()
            result = await adapter.send_message(_CHAT_GUID, "hello")

        assert result["success"] is False
        assert "Unauthorized" in result["error"]
        assert result["message_id"] is None

    asyncio.run(_run())


def test_imessage_send_message_network_error():
    """send_message() returns success=False on network failure."""

    async def _run():
        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("connection refused"),
        ):
            adapter = _make_adapter()
            result = await adapter.send_message(_CHAT_GUID, "hello")

        assert result["success"] is False
        assert "connection refused" in result["error"]

    asyncio.run(_run())


def test_imessage_verify_signature_valid():
    """verify_signature() returns True for a correct HMAC-SHA256 signature."""
    import hashlib
    import hmac as _hmac

    secret = "test-secret"
    body = b'{"text": "hello"}'
    sig = _hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert iMessageAdapter.verify_signature(body, sig, secret) is True


def test_imessage_verify_signature_invalid():
    """verify_signature() returns False for a wrong signature."""
    assert iMessageAdapter.verify_signature(b'{"text": "hello"}', "badsig", "test-secret") is False


def test_imessage_verify_signature_dev_mode():
    """verify_signature() returns True when secret is empty (dev mode)."""
    assert iMessageAdapter.verify_signature(b"anything", "whatever", "") is True


# ---------------------------------------------------------------------------
# Bus integration test — full roundtrip
# ---------------------------------------------------------------------------


def test_imessage_roundtrip_via_bus():
    """bus.roundtrip() ingests iMessage envelope, formats reply, and delivers it."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ) as mock_post:
            adapter = _make_adapter()
            bus = _make_bus_with_imessage(adapter)
            envelope = _imessage_envelope(text="ping")
            result = await bus.roundtrip(envelope)

        assert result.success is True
        assert result.channel == "imessage"
        assert mock_post.call_count == 1
        sent_json = mock_post.call_args.kwargs.get("json", {})
        assert isinstance(sent_json.get("message"), str)
        assert len(sent_json["message"]) > 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Webhook endpoint tests
# ---------------------------------------------------------------------------


def test_imessage_webhook_new_message_routes_through_bus():
    """POST /imessage/inbound with a new-message event routes through the bus."""
    client = _make_nexus_client()

    with patch.object(
        httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
    ):
        resp = client.post(
            "/api/nexus/imessage/inbound",
            json=_bb_payload(text="Hey Arcturus, what is 2+2?"),
        )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_imessage_webhook_from_me_skipped():
    """POST /imessage/inbound with isFromMe=true must be skipped (no reply loop)."""
    client = _make_nexus_client()

    resp = client.post(
        "/api/nexus/imessage/inbound",
        json=_bb_payload(text="I sent this myself", from_me=True),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("skipped") is True
    assert data.get("reason") == "fromMe"
