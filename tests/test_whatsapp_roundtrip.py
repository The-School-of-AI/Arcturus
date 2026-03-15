"""Unit and integration tests for the WhatsApp channel adapter and webhook endpoint.

Tests cover:
- WhatsAppAdapter.send_message() happy path (mocked httpx)
- WhatsAppAdapter.send_message() bridge error response
- WhatsAppAdapter.send_message() network/transport error
- Full bus.roundtrip() via MessageBus with mocked WhatsApp delivery
- Session affinity for two messages from the same phone number
- GET /whatsapp/inbound hub.challenge handshake
- POST /whatsapp/inbound message event routes through bus
- POST /whatsapp/inbound empty text (fromMe guard) is skipped

No real bridge or WhatsApp account is needed — httpx.AsyncClient.post
is patched throughout.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from channels.whatsapp import WhatsAppAdapter
from gateway.bus import MessageBus
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent
from routers import nexus as nexus_router
import shared.state as state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ok_bridge_response(message_id: str = "ABCDEF123456") -> MagicMock:
    """Build a mock httpx Response that the bridge returns on success."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ok": True,
        "message_id": message_id,
        "timestamp": "2026-02-23T10:00:00.000000Z",
    }
    return mock_resp


def _make_error_bridge_response(error: str = "not_connected") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.json.return_value = {"ok": False, "error": error}
    return mock_resp


def _make_bus_with_whatsapp(wa_adapter: WhatsAppAdapter) -> MessageBus:
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    return MessageBus(
        router=router,
        formatter=formatter,
        adapters={"whatsapp": wa_adapter},
    )


def _whatsapp_envelope(
    phone_number: str = "15551234567",
    text: str = "Hello agent",
    is_group: bool = False,
    group_id: str = None,
) -> MessageEnvelope:
    return MessageEnvelope.from_whatsapp(
        phone_number=phone_number,
        contact_name="Alice",
        text=text,
        message_id="WA-MSG-001",
        is_group=is_group,
        group_id=group_id,
    )


def _make_nexus_client() -> TestClient:
    """Minimal FastAPI app with nexus router for webhook tests.

    Injects a bus with a no-secret WhatsAppAdapter so HMAC verification
    is skipped — tests run without a real WHATSAPP_BRIDGE_SECRET in the env.
    """
    wa_adapter = WhatsAppAdapter()
    wa_adapter.bridge_secret = ""  # force-disable HMAC check for tests
    bus = _make_bus_with_whatsapp(wa_adapter)
    state._message_bus = bus
    nexus_router._bus = bus
    app = FastAPI()
    app.include_router(nexus_router.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Test 1: send_message() happy path
# ---------------------------------------------------------------------------


def test_whatsapp_send_message_success():
    """send_message() returns success=True and message_id when bridge responds ok."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock,
            return_value=_make_ok_bridge_response(),
        ):
            adapter = WhatsAppAdapter()
            result = await adapter.send_message("15551234567", "Hello from Arcturus")

        assert result["success"] is True
        assert result["message_id"] == "ABCDEF123456"
        assert result["channel"] == "whatsapp"
        assert result["recipient_id"] == "15551234567"
        assert result.get("error") is None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 2: send_message() bridge error response
# ---------------------------------------------------------------------------


def test_whatsapp_send_message_api_error():
    """send_message() returns success=False when bridge returns ok=false."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock,
            return_value=_make_error_bridge_response("not_connected"),
        ):
            adapter = WhatsAppAdapter()
            result = await adapter.send_message("15559999999", "hello")

        assert result["success"] is False
        assert "not_connected" in result["error"]
        assert result["message_id"] is None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 3: send_message() network/transport error
# ---------------------------------------------------------------------------


def test_whatsapp_send_message_network_error():
    """send_message() returns success=False when the bridge is unreachable."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock,
            side_effect=httpx.RequestError("connection refused"),
        ):
            adapter = WhatsAppAdapter()
            result = await adapter.send_message("15551234567", "hello")

        assert result["success"] is False
        assert "connection refused" in result["error"]

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 4: Full bus.roundtrip() with mocked WhatsApp delivery
# ---------------------------------------------------------------------------


def test_whatsapp_roundtrip_via_bus():
    """bus.roundtrip() ingests a WhatsApp envelope and delivers reply via bridge."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock,
            return_value=_make_ok_bridge_response(),
        ) as mock_post:
            adapter = WhatsAppAdapter()
            bus = _make_bus_with_whatsapp(adapter)
            envelope = _whatsapp_envelope(text="ping")
            result = await bus.roundtrip(envelope)

        assert result.success is True
        assert result.operation == "roundtrip"
        assert result.channel == "whatsapp"
        # Bridge POST /send must have been called exactly once
        assert mock_post.call_count == 1
        # WhatsApp adapter uses content= (bytes) for compact HMAC — decode and parse
        import json as _json
        raw = mock_post.call_args.kwargs.get("content") or mock_post.call_args.kwargs.get("json")
        if isinstance(raw, bytes):
            sent_json = _json.loads(raw.decode("utf-8"))
        elif isinstance(raw, dict):
            sent_json = raw
        else:
            sent_json = {}
        assert sent_json.get("recipient_id") == "15551234567"
        assert isinstance(sent_json.get("text"), str)
        assert len(sent_json["text"]) > 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 5: Session affinity — two DMs from same phone → same session
# ---------------------------------------------------------------------------


def test_whatsapp_session_affinity():
    """Two DMs from the same phone number route to the same agent session."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock,
            return_value=_make_ok_bridge_response(),
        ):
            adapter = WhatsAppAdapter()
            bus = _make_bus_with_whatsapp(adapter)

            env1 = _whatsapp_envelope(phone_number="15551234567", text="first message")
            env2 = MessageEnvelope.from_whatsapp(
                phone_number="15551234567",
                contact_name="Alice",
                text="second message",
                message_id="WA-MSG-002",  # different message_id → no dedup
            )

            r1 = await bus.ingest(env1)
            r2 = await bus.ingest(env2)

        assert r1.success is True
        assert r2.success is True
        assert r1.session_id == r2.session_id  # same phone → same session

        n1 = r1.agent_response["message_number"]
        n2 = r2.agent_response["message_number"]
        assert n2 > n1  # mock agent increments message_number per session

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Test 6: GET /whatsapp/inbound hub.challenge handshake
# ---------------------------------------------------------------------------


def test_whatsapp_webhook_challenge():
    """GET /whatsapp/inbound must echo hub.challenge for hub.mode=subscribe."""
    client = _make_nexus_client()
    resp = client.get(
        "/api/nexus/whatsapp/inbound",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "token-abc-123",
            "hub.verify_token": "",  # no secret in test mode
        },
    )
    assert resp.status_code == 200
    assert resp.json()["hub.challenge"] == "token-abc-123"


# ---------------------------------------------------------------------------
# Test 7: POST /whatsapp/inbound message event routes through bus
# ---------------------------------------------------------------------------


def test_whatsapp_webhook_message_event_returns_ok():
    """POST /whatsapp/inbound with valid message payload must return ok=True."""
    client = _make_nexus_client()

    with patch.object(
        httpx.AsyncClient, "post", new_callable=AsyncMock,
        return_value=_make_ok_bridge_response(),
    ):
        resp = client.post(
            "/api/nexus/whatsapp/inbound",
            json={
                "message_id": "WA-MSG-TEST-001",
                "phone_number": "15551234567",
                "contact_name": "Alice",
                "text": "hello Arcturus",
                "is_group": False,
                "group_id": None,
                "timestamp": "2026-02-23T10:00:00.000000Z",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# Test 8: POST /whatsapp/inbound empty text is skipped (fromMe guard)
# ---------------------------------------------------------------------------


def test_whatsapp_webhook_bot_messages_ignored():
    """POST /whatsapp/inbound with empty text must return ok=True, skipped=True
    and must NOT call the bridge (no routing for empty text)."""
    client = _make_nexus_client()

    with patch.object(
        httpx.AsyncClient, "post", new_callable=AsyncMock,
        return_value=_make_ok_bridge_response(),
    ) as mock_post:
        # Bridge filters fromMe before forwarding; simulating slip-through with empty text
        resp = client.post(
            "/api/nexus/whatsapp/inbound",
            json={
                "message_id": "WA-MSG-FROMME-001",
                "phone_number": "15559999999",
                "contact_name": "Bot",
                "text": "",  # empty text → skip routing
                "is_group": False,
                "group_id": None,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body.get("skipped") is True
    # Bridge /send must NOT have been called
    assert mock_post.call_count == 0
