"""Tests for media attachment send support across channel adapters.

Tests cover:
- Telegram: _send_attachment calls correct endpoint per media_type
- Discord: _send_attachment sends embed with image URL
- Slack: _send_attachment sends image block / link fallback
- WebChat: attachments key added to outbox dict
- Teams: attachments array in activity payload
- Matrix: _send_attachment sends correct msgtype
- Bridge adapters: attachment URLs appended as text links
- Bus roundtrip: attachments passed through deliver()
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from channels.discord import DiscordAdapter
from channels.googlechat import GoogleChatAdapter
from channels.imessage import iMessageAdapter
from channels.matrix import MatrixAdapter
from channels.signal import SignalAdapter
from channels.slack import SlackAdapter
from channels.teams import TeamsAdapter
from channels.telegram import TelegramAdapter
from channels.webchat import WebChatAdapter
from channels.whatsapp import WhatsAppAdapter
from gateway.bus import MessageBus
from gateway.envelope import MediaAttachment, MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_attachment(media_type="image", url="https://example.com/photo.jpg",
                     filename="photo.jpg", mime_type="image/jpeg"):
    return MediaAttachment(
        media_type=media_type,
        url=url,
        filename=filename,
        mime_type=mime_type,
    )


def _make_envelope_with_attachment(channel="webchat", sender="u1"):
    env = MessageEnvelope.from_webchat(
        session_id=f"sess-{sender}",
        sender_id=sender,
        sender_name="Test User",
        text="hello",
        message_id="MSG-001",
    )
    env.attachments = [_make_attachment()]
    env.content_type = "mixed"
    return env


# ---------------------------------------------------------------------------
# 1. Telegram — sendPhoto / sendDocument / sendVideo / sendAudio
# ---------------------------------------------------------------------------


def test_telegram_send_attachment_image():
    adapter = TelegramAdapter({"token": "TEST_TOKEN"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"ok": True, "result": {"message_id": 1, "date": 0}}),
    )
    adapter.client = mock_client

    att = _make_attachment(media_type="image")
    asyncio.run(adapter._send_attachment("12345", att))

    # Find the call that used sendPhoto
    calls = mock_client.post.call_args_list
    assert any("/sendPhoto" in str(c) for c in calls)


def test_telegram_send_attachment_document():
    adapter = TelegramAdapter({"token": "TEST_TOKEN"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(status_code=200)
    adapter.client = mock_client

    att = _make_attachment(media_type="document", filename="report.pdf",
                           mime_type="application/pdf")
    asyncio.run(adapter._send_attachment("12345", att))

    calls = mock_client.post.call_args_list
    assert any("/sendDocument" in str(c) for c in calls)


def test_telegram_send_attachment_video():
    adapter = TelegramAdapter({"token": "TEST_TOKEN"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(status_code=200)
    adapter.client = mock_client

    att = _make_attachment(media_type="video", url="https://example.com/video.mp4",
                           filename="video.mp4", mime_type="video/mp4")
    asyncio.run(adapter._send_attachment("12345", att))

    calls = mock_client.post.call_args_list
    assert any("/sendVideo" in str(c) for c in calls)


def test_telegram_send_message_with_attachments():
    adapter = TelegramAdapter({"token": "TEST_TOKEN"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"ok": True, "result": {"message_id": 1, "date": 0}}),
    )
    adapter.client = mock_client

    att = _make_attachment()
    asyncio.run(adapter.send_message("12345", "hello", attachments=[att]))

    # Should have called post at least twice: sendMessage + sendPhoto
    assert mock_client.post.call_count >= 2
    urls = [str(c) for c in mock_client.post.call_args_list]
    assert any("sendMessage" in u for u in urls)
    assert any("sendPhoto" in u for u in urls)


# ---------------------------------------------------------------------------
# 2. Discord — embed with image URL
# ---------------------------------------------------------------------------


def test_discord_send_attachment_image():
    adapter = DiscordAdapter({"token": "Bot TEST_TOKEN"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(status_code=200)
    adapter.client = mock_client

    att = _make_attachment(media_type="image")
    asyncio.run(adapter._send_attachment("chan-1", att))

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    payload = call_args[1]["json"]
    assert "embeds" in payload
    assert payload["embeds"][0]["image"]["url"] == att.url


def test_discord_send_attachment_document():
    adapter = DiscordAdapter({"token": "Bot TEST_TOKEN"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(status_code=200)
    adapter.client = mock_client

    att = _make_attachment(media_type="document", filename="report.pdf")
    asyncio.run(adapter._send_attachment("chan-1", att))

    payload = mock_client.post.call_args[1]["json"]
    assert "report.pdf" in payload["embeds"][0]["description"]


def test_discord_send_message_strips_attachments_from_payload():
    adapter = DiscordAdapter({"token": "Bot TEST_TOKEN"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"id": "msg1", "timestamp": "2026-01-01T00:00:00"}),
    )
    adapter.client = mock_client

    att = _make_attachment()
    result = asyncio.run(adapter.send_message("chan-1", "hello", attachments=[att]))

    # First call is the text message — should NOT have "attachments" in json
    text_call = mock_client.post.call_args_list[0]
    assert "attachments" not in text_call[1]["json"]
    assert result["success"] is True


# ---------------------------------------------------------------------------
# 3. Slack — image blocks
# ---------------------------------------------------------------------------


def test_slack_send_attachment_image():
    adapter = SlackAdapter({"token": "xoxb-TEST"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"ok": True, "ts": "123.456"}),
    )
    adapter.client = mock_client

    att = _make_attachment(media_type="image")
    asyncio.run(adapter._send_attachment("C123", att))

    payload = mock_client.post.call_args[1]["json"]
    assert "blocks" in payload
    assert payload["blocks"][0]["type"] == "image"
    assert payload["blocks"][0]["image_url"] == att.url


def test_slack_send_attachment_document():
    adapter = SlackAdapter({"token": "xoxb-TEST"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(status_code=200)
    adapter.client = mock_client

    att = _make_attachment(media_type="document", filename="report.pdf")
    asyncio.run(adapter._send_attachment("C123", att))

    payload = mock_client.post.call_args[1]["json"]
    assert "report.pdf" in payload["text"]


# ---------------------------------------------------------------------------
# 4. WebChat — attachments in outbox dict
# ---------------------------------------------------------------------------


def test_webchat_send_message_includes_attachments():
    adapter = WebChatAdapter()
    att = _make_attachment()
    result = asyncio.run(adapter.send_message("sess-1", "hello", attachments=[att]))

    assert result["success"] is True
    outbox = adapter.drain_outbox("sess-1")
    assert len(outbox) == 1
    msg = outbox[0]
    assert "attachments" in msg
    assert msg["attachments"][0]["media_type"] == "image"
    assert msg["attachments"][0]["url"] == att.url


def test_webchat_send_message_no_attachments_key_when_empty():
    adapter = WebChatAdapter()
    asyncio.run(adapter.send_message("sess-1", "hello"))

    outbox = adapter.drain_outbox("sess-1")
    assert len(outbox) == 1
    assert "attachments" not in outbox[0]


# ---------------------------------------------------------------------------
# 5. Teams — attachments in activity payload
# ---------------------------------------------------------------------------


def test_teams_send_message_includes_attachments():
    adapter = TeamsAdapter({"app_password": "secret", "service_url": "https://bot.example.com"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"id": "msg1"}),
    )
    adapter.client = mock_client

    att = _make_attachment()
    result = asyncio.run(adapter.send_message("conv-1", "hello", attachments=[att]))

    assert result["success"] is True
    payload = mock_client.post.call_args[1]["json"]
    assert "attachments" in payload
    assert payload["attachments"][0]["contentUrl"] == att.url
    assert payload["attachments"][0]["contentType"] == "image/jpeg"


def test_teams_send_message_no_attachments_when_empty():
    adapter = TeamsAdapter({"app_password": "secret", "service_url": "https://bot.example.com"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"id": "msg1"}),
    )
    adapter.client = mock_client

    asyncio.run(adapter.send_message("conv-1", "hello"))

    payload = mock_client.post.call_args[1]["json"]
    assert "attachments" not in payload


# ---------------------------------------------------------------------------
# 6. Matrix — m.image / m.file events
# ---------------------------------------------------------------------------


def test_matrix_send_attachment_image():
    adapter = MatrixAdapter({
        "homeserver_url": "https://matrix.example.com",
        "user_id": "@bot:example.com",
        "access_token": "syt_token",
    })
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.put.return_value = MagicMock(status_code=200)
    adapter.client = mock_client

    att = _make_attachment(media_type="image")
    asyncio.run(adapter._send_attachment("!room:example.com", att))

    mock_client.put.assert_called_once()
    body = mock_client.put.call_args[1]["json"]
    assert body["msgtype"] == "m.image"
    assert body["url"] == att.url


def test_matrix_send_attachment_document():
    adapter = MatrixAdapter({
        "homeserver_url": "https://matrix.example.com",
        "user_id": "@bot:example.com",
        "access_token": "syt_token",
    })
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.put.return_value = MagicMock(status_code=200)
    adapter.client = mock_client

    att = _make_attachment(media_type="document", filename="report.pdf",
                           mime_type="application/pdf")
    asyncio.run(adapter._send_attachment("!room:example.com", att))

    body = mock_client.put.call_args[1]["json"]
    assert body["msgtype"] == "m.file"
    assert body["info"]["mimetype"] == "application/pdf"


# ---------------------------------------------------------------------------
# 7. Bridge adapters — URL text fallback
# ---------------------------------------------------------------------------


def test_whatsapp_appends_attachment_urls():
    adapter = WhatsAppAdapter({"bridge_url": "http://localhost:3001"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"ok": True, "message_id": "m1"}),
    )
    adapter.client = mock_client

    att = _make_attachment()
    asyncio.run(adapter.send_message("15551234567", "hello", attachments=[att]))

    payload = mock_client.post.call_args[1]["json"]
    assert att.url in payload["text"]
    assert "hello" in payload["text"]


def test_signal_appends_attachment_urls():
    adapter = SignalAdapter({"bridge_url": "http://localhost:3002"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"ok": True, "message_id": "m1"}),
    )
    adapter.client = mock_client

    att = _make_attachment()
    asyncio.run(adapter.send_message("+15551234567", "hello", attachments=[att]))

    payload = mock_client.post.call_args[1]["json"]
    assert att.url in payload["text"]


def test_imessage_appends_attachment_urls():
    adapter = iMessageAdapter({"bluebubbles_url": "http://localhost:1234"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"status": 200, "data": {"guid": "g1"}}),
    )
    adapter.client = mock_client

    att = _make_attachment()
    asyncio.run(adapter.send_message("chat123", "hello", attachments=[att]))

    payload = mock_client.post.call_args[1]["json"]
    assert att.url in payload["message"]


def test_googlechat_appends_attachment_urls():
    adapter = GoogleChatAdapter({"webhook_url": "https://chat.googleapis.com/v1/spaces/X/messages?key=K"})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"name": "spaces/X/messages/Y"}),
    )
    adapter.client = mock_client

    att = _make_attachment()
    asyncio.run(adapter.send_message("spaces/X", "hello", attachments=[att]))

    payload = mock_client.post.call_args[1]["json"]
    assert att.url in payload["text"]


# ---------------------------------------------------------------------------
# 8. Bus — attachments passed through roundtrip → deliver
# ---------------------------------------------------------------------------


def test_bus_roundtrip_passes_attachments():
    async def _run():
        formatter = MessageFormatter()
        router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
        mock_adapter = AsyncMock()
        mock_adapter.send_typing_indicator.return_value = None
        mock_adapter.send_message.return_value = {"message_id": "m1", "success": True}

        bus = MessageBus(
            router=router,
            formatter=formatter,
            adapters={"webchat": mock_adapter},
        )

        envelope = _make_envelope_with_attachment(channel="webchat")
        result = await bus.roundtrip(envelope)

        # send_message should have been called with attachments kwarg
        call_kwargs = mock_adapter.send_message.call_args[1]
        assert "attachments" in call_kwargs
        assert len(call_kwargs["attachments"]) == 1
        assert call_kwargs["attachments"][0].media_type == "image"

    asyncio.run(_run())


def test_bus_roundtrip_no_attachments_when_empty():
    async def _run():
        formatter = MessageFormatter()
        router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
        mock_adapter = AsyncMock()
        mock_adapter.send_typing_indicator.return_value = None
        mock_adapter.send_message.return_value = {"message_id": "m1", "success": True}

        bus = MessageBus(
            router=router,
            formatter=formatter,
            adapters={"webchat": mock_adapter},
        )

        envelope = MessageEnvelope.from_webchat(
            session_id="sess-u1",
            sender_id="u1",
            sender_name="Test User",
            text="hello",
            message_id="MSG-002",
        )
        await bus.roundtrip(envelope)

        # send_message should have been called with empty attachments
        call_kwargs = mock_adapter.send_message.call_args[1]
        assert call_kwargs.get("attachments") == []

    asyncio.run(_run())
