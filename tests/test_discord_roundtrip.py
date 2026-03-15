"""Unit and integration tests for the Discord channel adapter and webhook endpoint.

Tests cover:
- DiscordAdapter.send_message() happy path (mocked httpx)
- DiscordAdapter.send_message() Discord API error (non-2xx)
- DiscordAdapter.send_message() network/transport error
- DiscordAdapter 2000-char content truncation
- Full bus.roundtrip() via MessageBus with mocked Discord delivery
- Session affinity across two messages in the same Discord channel
- POST /nexus/discord/events — PING handshake returns type 1
- POST /nexus/discord/events — message relay routes through bus

No real Discord token is needed — httpx.AsyncClient.post is patched throughout.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from channels.discord import DiscordAdapter
from gateway.bus import MessageBus
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent
from routers import nexus as nexus_router
import shared.state as state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ok_response(message_id: str = "1234567890123456789") -> MagicMock:
    """Build a mock httpx Response that Discord returns on success (HTTP 200)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": message_id,
        "timestamp": "2026-02-23T10:00:00.000000+00:00",
        "channel_id": "111222333444555666",
        "content": "reply",
    }
    return mock_resp


def _make_error_response(status: int = 403, message: str = "Missing Permissions") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.json.return_value = {"code": 50013, "message": message}
    return mock_resp


def _make_bus_with_discord(discord_adapter: DiscordAdapter) -> MessageBus:
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    return MessageBus(
        router=router,
        formatter=formatter,
        adapters={"discord": discord_adapter},
    )


def _discord_envelope(
    channel_id: str = "111222333444555666",
    guild_id: str = "999888777666555444",
    text: str = "Hello agent",
) -> MessageEnvelope:
    return MessageEnvelope.from_discord(
        guild_id=guild_id,
        channel_id=channel_id,
        sender_id="123456789012345678",
        sender_name="Alice",
        text=text,
        message_id="999000111222333444",
    )


def _make_nexus_client() -> TestClient:
    """Minimal FastAPI app with the nexus router for webhook tests.

    Injects a bus with a no-key DiscordAdapter so signature verification
    is skipped — tests run without a real DISCORD_PUBLIC_KEY in the env.
    """
    discord_adapter = DiscordAdapter()
    discord_adapter.public_key = ""  # force-disable Ed25519 check for tests
    bus = _make_bus_with_discord(discord_adapter)
    state._message_bus = bus
    nexus_router._bus = bus
    app = FastAPI()
    app.include_router(nexus_router.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# DiscordAdapter unit tests
# ---------------------------------------------------------------------------


def test_discord_send_message_success():
    """send_message() returns success=True and message_id when Discord responds 200."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ):
            adapter = DiscordAdapter()
            result = await adapter.send_message("111222333444555666", "**Hello** world!")

        assert result["success"] is True
        assert result["message_id"] == "1234567890123456789"
        assert result["channel"] == "discord"
        assert result["recipient_id"] == "111222333444555666"
        assert result.get("error") is None

    asyncio.run(_run())


def test_discord_send_message_api_error():
    """send_message() returns success=False when Discord returns a non-2xx status."""

    async def _run():
        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            return_value=_make_error_response(403, "Missing Permissions"),
        ):
            adapter = DiscordAdapter()
            result = await adapter.send_message("111222333444555666", "hello")

        assert result["success"] is False
        assert "Missing Permissions" in result["error"]
        assert result["message_id"] is None

    asyncio.run(_run())


def test_discord_send_message_network_error():
    """send_message() returns success=False when a network error occurs."""

    async def _run():
        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("connection refused"),
        ):
            adapter = DiscordAdapter()
            result = await adapter.send_message("111222333444555666", "hello")

        assert result["success"] is False
        assert "connection refused" in result["error"]

    asyncio.run(_run())


def test_discord_send_message_truncates_long_content():
    """Content longer than 2000 chars must be truncated with ellipsis before sending."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ) as mock_post:
            adapter = DiscordAdapter()
            long_text = "x" * 2500
            await adapter.send_message("111222333444555666", long_text)

        sent_json = mock_post.call_args.kwargs.get("json", {})
        assert len(sent_json["content"]) == 2000
        assert sent_json["content"].endswith("...")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bus integration test — full roundtrip via MessageBus
# ---------------------------------------------------------------------------


def test_discord_roundtrip_via_bus():
    """bus.roundtrip() ingests a Discord envelope, formats reply as Discord markdown,
    and delivers it via the DiscordAdapter."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ) as mock_post:
            adapter = DiscordAdapter()
            bus = _make_bus_with_discord(adapter)
            envelope = _discord_envelope(text="ping")
            result = await bus.roundtrip(envelope)

        assert result.success is True
        assert result.operation == "roundtrip"
        assert result.channel == "discord"
        # Discord REST API must have been called exactly once
        assert mock_post.call_count == 1
        # The payload content must be non-empty Discord markdown
        sent_json = mock_post.call_args.kwargs.get("json", {})
        assert isinstance(sent_json.get("content"), str)
        assert len(sent_json["content"]) > 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Session affinity test
# ---------------------------------------------------------------------------


def test_discord_session_affinity():
    """Two messages in the same Discord channel route to the same agent session."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ):
            adapter = DiscordAdapter()
            bus = _make_bus_with_discord(adapter)

            env1 = _discord_envelope(channel_id="C111", text="first message")
            env2 = MessageEnvelope.from_discord(
                guild_id="999888777666555444",
                channel_id="C111",
                sender_id="123456789012345678",
                sender_name="Alice",
                text="second message",
                message_id="999000111222333445",  # different message_id → no dedup
            )

            r1 = await bus.ingest(env1)
            r2 = await bus.ingest(env2)

        assert r1.success is True
        assert r2.success is True
        assert r1.session_id == r2.session_id  # same channel → same session

        n1 = r1.agent_response["message_number"]
        n2 = r2.agent_response["message_number"]
        assert n2 > n1

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Webhook endpoint tests — PING + message relay
# ---------------------------------------------------------------------------


def test_discord_webhook_ping_handshake():
    """POST /discord/events with type=1 (PING) must return {"type": 1}."""
    client = _make_nexus_client()
    resp = client.post(
        "/api/nexus/discord/events",
        json={"type": 1},
    )
    assert resp.status_code == 200
    assert resp.json()["type"] == 1


def test_discord_webhook_message_relay_returns_ok():
    """POST /discord/events with a message relay payload must return ok=True."""
    client = _make_nexus_client()

    with patch.object(
        httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
    ):
        resp = client.post(
            "/api/nexus/discord/events",
            json={
                "type": "message",
                "guild_id": "999888777666555444",
                "channel_id": "111222333444555666",
                "id": "555000111222333444",
                "author": {
                    "id": "123456789012345678",
                    "username": "Alice",
                    "bot": False,
                },
                "content": "hello Arcturus",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
