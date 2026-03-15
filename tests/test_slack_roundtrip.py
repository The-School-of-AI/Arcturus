"""Unit and integration tests for the Slack channel adapter and webhook endpoint.

Tests cover:
- SlackAdapter.send_message() happy path (mocked httpx)
- SlackAdapter.send_message() Slack API error
- SlackAdapter.send_message() network/transport error
- Full bus.roundtrip() via MessageBus with mocked Slack delivery
- Session affinity across two messages in the same Slack channel

No real Slack token is needed — httpx.AsyncClient.post is patched throughout.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import httpx

from channels.slack import SlackAdapter
from gateway.bus import MessageBus
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent
from routers import nexus as nexus_router
import shared.state as state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ok_response(ts: str = "1700000000.000001") -> MagicMock:
    """Build a mock httpx Response that Slack returns on success."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "ts": ts, "channel": "C1234"}
    return mock_resp


def _make_error_response(error: str = "not_in_channel") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "error": error}
    return mock_resp


def _make_bus_with_slack(slack_adapter: SlackAdapter) -> MessageBus:
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    return MessageBus(
        router=router,
        formatter=formatter,
        adapters={"slack": slack_adapter},
    )


def _slack_envelope(channel_id: str = "C1234", text: str = "Hello agent") -> MessageEnvelope:
    return MessageEnvelope.from_slack(
        channel_id=channel_id,
        sender_id="U999",
        sender_name="Alice",
        text=text,
        message_id="1700000001.000001",
    )


def _make_nexus_client() -> TestClient:
    """Minimal FastAPI app with the nexus router for webhook tests.

    Injects a bus with a no-secret SlackAdapter so signature verification
    is skipped — tests run without a real SLACK_SIGNING_SECRET in the env.
    """
    slack_adapter = SlackAdapter()
    slack_adapter.signing_secret = ""  # force-disable signature check for tests
    bus = _make_bus_with_slack(slack_adapter)
    state._message_bus = bus
    nexus_router._bus = bus
    app = FastAPI()
    app.include_router(nexus_router.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# SlackAdapter unit tests
# ---------------------------------------------------------------------------


def test_slack_send_message_success():
    """send_message() returns success=True and message_id when Slack responds ok."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ):
            adapter = SlackAdapter()
            result = await adapter.send_message("C1234", "hello *world*")

        assert result["success"] is True
        assert result["message_id"] == "1700000000.000001"
        assert result["channel"] == "slack"
        assert result["recipient_id"] == "C1234"
        assert "error" not in result or result.get("error") is None

    asyncio.run(_run())


def test_slack_send_message_api_error():
    """send_message() returns success=False when Slack returns ok=false."""

    async def _run():
        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            return_value=_make_error_response("not_in_channel"),
        ):
            adapter = SlackAdapter()
            result = await adapter.send_message("C9999", "hello")

        assert result["success"] is False
        assert result["error"] == "not_in_channel"
        assert result["message_id"] is None

    asyncio.run(_run())


def test_slack_send_message_network_error():
    """send_message() returns success=False when a network error occurs."""

    async def _run():
        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("connection refused"),
        ):
            adapter = SlackAdapter()
            result = await adapter.send_message("C1234", "hello")

        assert result["success"] is False
        assert "connection refused" in result["error"]

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bus integration test — full roundtrip via MessageBus
# ---------------------------------------------------------------------------


def test_slack_roundtrip_via_bus():
    """bus.roundtrip() ingests a Slack envelope, formats reply as mrkdwn, and delivers it."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ) as mock_post:
            adapter = SlackAdapter()
            bus = _make_bus_with_slack(adapter)
            envelope = _slack_envelope(text="ping")
            result = await bus.roundtrip(envelope)

        assert result.success is True
        assert result.operation == "roundtrip"
        assert result.channel == "slack"
        # Slack API must have been called exactly once
        assert mock_post.call_count == 1
        # The payload sent to Slack should contain the mrkdwn-formatted reply
        call_kwargs = mock_post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs.args[0] if call_kwargs.args else {}
        assert "channel" in body or body == {}  # body is in kwargs["json"]
        sent_json = mock_post.call_args.kwargs.get("json", {})
        assert sent_json.get("channel") == envelope.conversation_id
        assert isinstance(sent_json.get("text"), str)
        assert len(sent_json["text"]) > 0

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Session affinity test
# ---------------------------------------------------------------------------


def test_slack_session_affinity():
    """Two messages in the same Slack channel route to the same agent session."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ):
            adapter = SlackAdapter()
            bus = _make_bus_with_slack(adapter)

            env1 = _slack_envelope(channel_id="C5555", text="first message")
            env2 = _slack_envelope(channel_id="C5555", text="second message")
            # Give each a unique ts so dedup doesn't skip the second
            env2 = MessageEnvelope.from_slack(
                channel_id="C5555",
                sender_id="U999",
                sender_name="Alice",
                text="second message",
                message_id="1700000002.000002",
            )

            r1 = await bus.ingest(env1)
            r2 = await bus.ingest(env2)

        assert r1.success is True
        assert r2.success is True
        assert r1.session_id == r2.session_id  # same channel → same session

        # Mock agent increments message_number per session
        n1 = r1.agent_response["message_number"]
        n2 = r2.agent_response["message_number"]
        assert n2 > n1

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Webhook endpoint tests (url_verification + event routing)
# ---------------------------------------------------------------------------


def test_slack_webhook_url_verification():
    """POST /slack/events with type=url_verification must echo the challenge."""
    client = _make_nexus_client()
    resp = client.post(
        "/api/nexus/slack/events",
        json={"type": "url_verification", "challenge": "abc-123-xyz"},
    )
    assert resp.status_code == 200
    assert resp.json()["challenge"] == "abc-123-xyz"


def test_slack_webhook_message_event_returns_ok():
    """POST /slack/events with a message event must return ok=True."""
    client = _make_nexus_client()

    with patch.object(
        httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
    ):
        resp = client.post(
            "/api/nexus/slack/events",
            json={
                "type": "event_callback",
                "event_id": "Ev001",
                "event": {
                    "type": "message",
                    "channel": "C1234",
                    "user": "U001",
                    "text": "hello bot",
                    "ts": "1700000003.000001",
                },
            },
        )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_slack_webhook_bot_messages_ignored():
    """POST /slack/events from a bot (bot_id present) must return ok=True but not route."""
    client = _make_nexus_client()

    with patch.object(
        httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
    ) as mock_post:
        resp = client.post(
            "/api/nexus/slack/events",
            json={
                "type": "event_callback",
                "event": {
                    "type": "message",
                    "channel": "C1234",
                    "bot_id": "B001",   # bot message — must be ignored
                    "text": "I am a bot",
                    "ts": "1700000004.000001",
                },
            },
        )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    # Slack API must NOT have been called (bot messages don't trigger agent)
    assert mock_post.call_count == 0
