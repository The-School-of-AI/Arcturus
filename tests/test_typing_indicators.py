"""Tests for typing indicator support across channel adapters and the message bus.

Tests cover:
- Base class no-op default
- Telegram sendChatAction typing
- Discord POST /channels/{id}/typing
- WebChat SSE typing event push
- Teams Bot Framework typing activity
- Matrix PUT /rooms/{roomId}/typing/{userId}
- Bus._send_typing() swallows exceptions
- Bus.roundtrip() fires typing before ingest
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from channels.base import ChannelAdapter
from channels.discord import DiscordAdapter
from channels.matrix import MatrixAdapter
from channels.teams import TeamsAdapter
from channels.telegram import TelegramAdapter
from channels.webchat import WebChatAdapter
from gateway.bus import MessageBus
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope(channel: str = "telegram", sender: str = "u1") -> MessageEnvelope:
    return MessageEnvelope.from_webchat(
        session_id=f"sess-{sender}",
        sender_id=sender,
        sender_name="Test User",
        text="hello",
        message_id="MSG-001",
    )


# ---------------------------------------------------------------------------
# 1. Base class default is a no-op
# ---------------------------------------------------------------------------


class _ConcreteAdapter(ChannelAdapter):
    """Minimal concrete adapter for testing the base class."""

    async def send_message(self, recipient_id, content, **kw):
        return {"success": True}

    async def initialize(self):
        pass

    async def shutdown(self):
        pass


def test_base_class_typing_is_noop():
    adapter = _ConcreteAdapter("test")
    # Should return None and not raise
    result = asyncio.run(adapter.send_typing_indicator("recipient-1"))
    assert result is None


# ---------------------------------------------------------------------------
# 2. Telegram — sendChatAction
# ---------------------------------------------------------------------------


def test_telegram_typing_calls_send_chat_action():
    adapter = TelegramAdapter({"token": "TEST_TOKEN"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(status_code=200)
    adapter.client = mock_client

    asyncio.run(adapter.send_typing_indicator("12345"))

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert "/sendChatAction" in call_args[0][0]
    assert call_args[1]["json"]["action"] == "typing"
    assert call_args[1]["json"]["chat_id"] == "12345"


def test_telegram_typing_swallows_errors():
    adapter = TelegramAdapter({"token": "TEST_TOKEN"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.RequestError("network down")
    adapter.client = mock_client

    # Should not raise
    asyncio.run(adapter.send_typing_indicator("12345"))


# ---------------------------------------------------------------------------
# 3. Discord — POST /channels/{id}/typing
# ---------------------------------------------------------------------------


def test_discord_typing_calls_typing_endpoint():
    adapter = DiscordAdapter({"token": "Bot TEST_TOKEN"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(status_code=204)
    adapter.client = mock_client

    asyncio.run(adapter.send_typing_indicator("chan-999"))

    mock_client.post.assert_called_once()
    url = mock_client.post.call_args[0][0]
    assert "/channels/chan-999/typing" in url


# ---------------------------------------------------------------------------
# 4. WebChat — SSE typing event
# ---------------------------------------------------------------------------


def test_webchat_typing_pushes_sse_event():
    adapter = WebChatAdapter()
    q = adapter.subscribe_sse("sess-1")

    asyncio.run(adapter.send_typing_indicator("sess-1"))

    assert not q.empty()
    event = q.get_nowait()
    assert event["type"] == "typing"
    assert event["session_id"] == "sess-1"

    # Cleanup
    adapter.unsubscribe_sse("sess-1", q)


def test_webchat_typing_no_subscribers_is_noop():
    adapter = WebChatAdapter()
    # No subscribers — should not raise
    asyncio.run(adapter.send_typing_indicator("no-one"))


# ---------------------------------------------------------------------------
# 5. Teams — Bot Framework typing activity
# ---------------------------------------------------------------------------


def test_teams_typing_sends_typing_activity():
    adapter = TeamsAdapter({"app_password": "secret", "service_url": "https://bot.example.com"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(status_code=200)
    adapter.client = mock_client

    asyncio.run(adapter.send_typing_indicator("conv-123"))

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert "conv-123" in call_args[0][0]
    assert call_args[1]["json"]["type"] == "typing"


# ---------------------------------------------------------------------------
# 6. Matrix — PUT /rooms/{roomId}/typing/{userId}
# ---------------------------------------------------------------------------


def test_matrix_typing_calls_typing_endpoint():
    adapter = MatrixAdapter({
        "homeserver_url": "https://matrix.example.com",
        "user_id": "@bot:example.com",
        "access_token": "syt_token",
    })
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.put.return_value = MagicMock(status_code=200)
    adapter.client = mock_client

    asyncio.run(adapter.send_typing_indicator("!room123:example.com"))

    mock_client.put.assert_called_once()
    url = mock_client.put.call_args[0][0]
    assert "/rooms/!room123:example.com/typing/@bot:example.com" in url
    body = mock_client.put.call_args[1]["json"]
    assert body["typing"] is True
    assert body["timeout"] == 30000


# ---------------------------------------------------------------------------
# 7. Bus._send_typing swallows exceptions
# ---------------------------------------------------------------------------


def test_bus_send_typing_swallows_errors():
    async def _run():
        formatter = MessageFormatter()
        router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)

        mock_adapter = AsyncMock(spec=ChannelAdapter)
        mock_adapter.send_typing_indicator.side_effect = Exception("boom")

        bus = MessageBus(
            router=router,
            formatter=formatter,
            adapters={"webchat": mock_adapter},
        )

        envelope = _make_envelope(channel="webchat")
        # Should not raise
        await bus._send_typing(envelope)
        mock_adapter.send_typing_indicator.assert_called_once()

    asyncio.run(_run())


def test_bus_send_typing_noop_for_unknown_channel():
    async def _run():
        formatter = MessageFormatter()
        router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
        bus = MessageBus(router=router, formatter=formatter, adapters={})

        envelope = _make_envelope(channel="unknown")
        # Should not raise even with no adapter
        await bus._send_typing(envelope)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 8. Bus.roundtrip fires typing before ingest
# ---------------------------------------------------------------------------


def test_bus_roundtrip_sends_typing_before_ingest():
    async def _run():
        formatter = MessageFormatter()
        router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
        mock_adapter = AsyncMock(spec=ChannelAdapter)
        mock_adapter.send_typing_indicator.return_value = None
        mock_adapter.send_message.return_value = {"message_id": "m1", "success": True}

        bus = MessageBus(
            router=router,
            formatter=formatter,
            adapters={"webchat": mock_adapter},
        )

        envelope = _make_envelope(channel="webchat")
        result = await bus.roundtrip(envelope)

        # Typing should have been called
        mock_adapter.send_typing_indicator.assert_called_once()
        # And send_message should also have been called (for the reply)
        mock_adapter.send_message.assert_called_once()

    asyncio.run(_run())
