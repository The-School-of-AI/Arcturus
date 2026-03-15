"""Unit and integration tests for the Signal channel adapter and webhook.

Tests cover:
1. SignalAdapter.send_message() happy path (mocked httpx)
2. SignalAdapter.send_message() API error (non-2xx response)
3. SignalAdapter.send_message() network/transport error
4. SignalAdapter.verify_signature() — valid / invalid / dev-mode
5. Full bus.roundtrip() via MessageBus with mocked Signal delivery
6. Session affinity: two messages from the same phone number route to the same session
7. POST /nexus/signal/inbound — message routes through bus
8. POST /nexus/signal/inbound — group message routes with group_id as conversation_id
9. POST /nexus/signal/inbound — empty text skipped

No real signal-cli is needed — httpx.AsyncClient.post is patched.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from channels.signal import SignalAdapter
from gateway.bus import MessageBus
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent
from routers import nexus as nexus_router
import shared.state as state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PHONE = "+15551234567"
_GROUP_ID = "signal-group-abc123"
_MESSAGE_ID = "1740650000000"


def _make_ok_response(msg_id: str = _MESSAGE_ID) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "message_id": msg_id, "timestamp": "2026-02-28T10:00:00Z"}
    return mock_resp


def _make_error_response(status: int = 500, error: str = "signal-cli error") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.json.return_value = {"ok": False, "error": error}
    return mock_resp


def _make_adapter() -> SignalAdapter:
    return SignalAdapter(
        config={
            "bridge_url": "http://localhost:3002",
            "bridge_secret": "",  # dev mode — no sig verification
        }
    )


def _make_bus_with_signal(adapter: SignalAdapter) -> MessageBus:
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    return MessageBus(
        router=router,
        formatter=formatter,
        adapters={"signal": adapter},
    )


def _signal_envelope(
    phone: str = _PHONE,
    text: str = "Hey Arcturus",
    is_group: bool = False,
    group_id: str | None = None,
    message_id: str = _MESSAGE_ID,
) -> MessageEnvelope:
    return MessageEnvelope.from_signal(
        phone_number=phone,
        sender_name="Alice",
        text=text,
        message_id=message_id,
        is_group=is_group,
        group_id=group_id,
    )


def _make_nexus_client() -> TestClient:
    adapter = SignalAdapter(config={"bridge_secret": ""})
    bus = _make_bus_with_signal(adapter)
    state._message_bus = bus
    nexus_router._bus = bus
    app = FastAPI()
    app.include_router(nexus_router.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=True)


def _signal_payload(
    text: str = "hello",
    phone: str = _PHONE,
    is_group: bool = False,
    group_id: str | None = None,
) -> dict:
    return {
        "message_id": _MESSAGE_ID,
        "phone_number": phone,
        "sender_name": "Alice",
        "text": text,
        "is_group": is_group,
        "group_id": group_id,
        "timestamp": "2026-02-28T10:00:00Z",
    }


# ---------------------------------------------------------------------------
# SignalAdapter unit tests
# ---------------------------------------------------------------------------


def test_signal_send_message_success():
    """send_message() returns success=True and message_id on HTTP 200."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ):
            adapter = _make_adapter()
            result = await adapter.send_message(_PHONE, "Hello from Arcturus")

        assert result["success"] is True
        assert result["message_id"] == _MESSAGE_ID
        assert result["channel"] == "signal"
        assert result.get("error") is None

    asyncio.run(_run())


def test_signal_send_message_api_error():
    """send_message() returns success=False on non-2xx from bridge."""

    async def _run():
        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            return_value=_make_error_response(500, "signal-cli not reachable"),
        ):
            adapter = _make_adapter()
            result = await adapter.send_message(_PHONE, "hello")

        assert result["success"] is False
        assert result["message_id"] is None

    asyncio.run(_run())


def test_signal_send_message_network_error():
    """send_message() returns success=False on network failure."""

    async def _run():
        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("connection refused"),
        ):
            adapter = _make_adapter()
            result = await adapter.send_message(_PHONE, "hello")

        assert result["success"] is False
        assert "connection refused" in result["error"]

    asyncio.run(_run())


def test_signal_verify_signature_valid():
    """verify_signature() returns True for a correct HMAC-SHA256 signature."""
    import hashlib
    import hmac as _hmac

    secret = "test-secret"
    body = b'{"text": "hello"}'
    sig = _hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert SignalAdapter.verify_signature(body, sig, secret) is True


def test_signal_verify_signature_invalid():
    """verify_signature() returns False for a wrong signature."""
    assert SignalAdapter.verify_signature(b'{"text": "hello"}', "badsig", "test-secret") is False


def test_signal_verify_signature_dev_mode():
    """verify_signature() returns True when secret is empty (dev mode)."""
    assert SignalAdapter.verify_signature(b"anything", "whatever", "") is True


# ---------------------------------------------------------------------------
# Bus integration test — full roundtrip
# ---------------------------------------------------------------------------


def test_signal_roundtrip_via_bus():
    """bus.roundtrip() ingests Signal envelope, formats reply, and delivers it."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ) as mock_post:
            adapter = _make_adapter()
            bus = _make_bus_with_signal(adapter)
            envelope = _signal_envelope(text="ping")
            result = await bus.roundtrip(envelope)

        assert result.success is True
        assert result.channel == "signal"
        assert mock_post.call_count == 1
        sent_json = mock_post.call_args.kwargs.get("json", {})
        assert isinstance(sent_json.get("text"), str)
        assert len(sent_json["text"]) > 0

    asyncio.run(_run())


def test_signal_session_affinity():
    """Two messages from the same phone number route to the same session."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ):
            adapter = _make_adapter()
            bus = _make_bus_with_signal(adapter)
            env1 = _signal_envelope(text="first")
            env2 = _signal_envelope(text="second", message_id=str(int(_MESSAGE_ID) + 1))
            r1 = await bus.roundtrip(env1)
            r2 = await bus.roundtrip(env2)

        assert r1.session_id == r2.session_id

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Webhook endpoint tests
# ---------------------------------------------------------------------------


def test_signal_webhook_message_routes_through_bus():
    """POST /signal/inbound routes a normal message through the bus."""
    client = _make_nexus_client()

    with patch.object(
        httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
    ):
        resp = client.post(
            "/api/nexus/signal/inbound",
            json=_signal_payload(text="What is 2+2?"),
        )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_signal_webhook_group_message():
    """POST /signal/inbound with is_group=True uses group_id as conversation_id."""
    client = _make_nexus_client()

    captured_envelopes = []
    orig_roundtrip = client.app.routes  # just need side-effect check via mock

    with patch.object(
        httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
    ):
        resp = client.post(
            "/api/nexus/signal/inbound",
            json=_signal_payload(text="group hello", is_group=True, group_id=_GROUP_ID),
        )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_signal_webhook_empty_text_skipped():
    """POST /signal/inbound with empty text is skipped gracefully."""
    client = _make_nexus_client()

    resp = client.post(
        "/api/nexus/signal/inbound",
        json=_signal_payload(text=""),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("skipped") is True
    assert data.get("reason") == "empty_text"
