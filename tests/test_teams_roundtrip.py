"""Unit and integration tests for the Microsoft Teams channel adapter and webhook.

Tests cover:
1. TeamsAdapter.send_message() happy path (mocked httpx)
2. TeamsAdapter.send_message() API error (non-2xx response)
3. TeamsAdapter.send_message() network/transport error
4. TeamsAdapter.verify_token() — valid / invalid / dev-mode
5. Full bus.roundtrip() via MessageBus with mocked Teams delivery
6. Session affinity: two messages from the same team/channel route to the same session
7. POST /nexus/teams/events — message activity routes through bus
8. POST /nexus/teams/events — non-message activity (typing) skipped
9. POST /nexus/teams/events — bot message skipped (fromBot)

No real Azure Bot Service is needed — httpx.AsyncClient.post is patched.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from channels.teams import TeamsAdapter
from gateway.bus import MessageBus
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent
from routers import nexus as nexus_router
import shared.state as state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEAM_ID = "19:team-abc123"
_CHANNEL_ID = "19:channel-def456"
_CONVERSATION_ID = "a:conv-ghi789"
_MESSAGE_ID = "1-activity-00001"


def _make_ok_response(msg_id: str = _MESSAGE_ID) -> MagicMock:
    """Build a mock httpx Response that Bot Framework returns on success (HTTP 200)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": msg_id}
    return mock_resp


def _make_error_response(status: int = 403, message: str = "Forbidden") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.json.return_value = {"error": {"message": message, "code": str(status)}}
    return mock_resp


def _make_adapter() -> TeamsAdapter:
    return TeamsAdapter(
        config={
            "app_id": "test-app-id",
            "app_password": "",  # dev mode — no token verification
            "service_url": "http://localhost:4040",
        }
    )


def _make_bus_with_teams(adapter: TeamsAdapter) -> MessageBus:
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    return MessageBus(
        router=router,
        formatter=formatter,
        adapters={"teams": adapter},
    )


def _teams_envelope(
    team_id: str = _TEAM_ID,
    channel_id: str = _CHANNEL_ID,
    text: str = "Hey Arcturus",
    message_id: str = _MESSAGE_ID,
) -> MessageEnvelope:
    return MessageEnvelope.from_teams(
        team_id=team_id,
        channel_id=channel_id,
        sender_id="29:user-aad-001",
        sender_name="Alice",
        text=text,
        message_id=message_id,
        service_url="http://localhost:4040",
    )


def _make_nexus_client() -> TestClient:
    """Minimal FastAPI app with nexus router; no app_password so token check is skipped."""
    adapter = TeamsAdapter(config={"app_password": "", "service_url": "http://localhost:4040"})
    bus = _make_bus_with_teams(adapter)
    state._message_bus = bus
    nexus_router._bus = bus
    app = FastAPI()
    app.include_router(nexus_router.router, prefix="/api")
    return TestClient(app, raise_server_exceptions=True)


def _teams_activity_payload(
    activity_type: str = "message",
    text: str = "Hello Arcturus",
    from_role: str = "user",
    team_id: str = _TEAM_ID,
    channel_id: str = _CHANNEL_ID,
) -> dict:
    return {
        "type": activity_type,
        "id": _MESSAGE_ID,
        "text": text,
        "from": {
            "id": "29:user-aad-001",
            "aadObjectId": "aad-001",
            "name": "Alice",
            "role": from_role,
        },
        "conversation": {"id": _CONVERSATION_ID, "isGroup": True},
        "channelData": {
            "teamsChannelId": channel_id,
            "team": {"id": team_id},
        },
        "serviceUrl": "http://localhost:4040",
    }


# ---------------------------------------------------------------------------
# TeamsAdapter unit tests
# ---------------------------------------------------------------------------


def test_teams_send_message_success():
    """send_message() returns success=True and message_id on HTTP 200."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ):
            adapter = _make_adapter()
            result = await adapter.send_message(_CONVERSATION_ID, "Hello from Arcturus")

        assert result["success"] is True
        assert result["message_id"] == _MESSAGE_ID
        assert result["channel"] == "teams"
        assert result.get("error") is None

    asyncio.run(_run())


def test_teams_send_message_api_error():
    """send_message() returns success=False when Bot Framework returns non-2xx."""

    async def _run():
        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            return_value=_make_error_response(403, "Forbidden"),
        ):
            adapter = _make_adapter()
            result = await adapter.send_message(_CONVERSATION_ID, "hello")

        assert result["success"] is False
        assert "Forbidden" in result["error"]
        assert result["message_id"] is None

    asyncio.run(_run())


def test_teams_send_message_network_error():
    """send_message() returns success=False on network failure."""

    async def _run():
        with patch.object(
            httpx.AsyncClient,
            "post",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("connection refused"),
        ):
            adapter = _make_adapter()
            result = await adapter.send_message(_CONVERSATION_ID, "hello")

        assert result["success"] is False
        assert "connection refused" in result["error"]

    asyncio.run(_run())


def test_teams_verify_token_valid():
    """verify_token() returns True when token matches expected_password."""
    assert TeamsAdapter.verify_token("secret-pw", "secret-pw") is True


def test_teams_verify_token_invalid():
    """verify_token() returns False when token does not match."""
    assert TeamsAdapter.verify_token("wrong-token", "secret-pw") is False


def test_teams_verify_token_dev_mode():
    """verify_token() returns True when expected_password is empty (dev mode)."""
    assert TeamsAdapter.verify_token("anything", "") is True


# ---------------------------------------------------------------------------
# Bus integration test — full roundtrip
# ---------------------------------------------------------------------------


def test_teams_roundtrip_via_bus():
    """bus.roundtrip() ingests Teams envelope, formats reply, and delivers it."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ) as mock_post:
            adapter = _make_adapter()
            bus = _make_bus_with_teams(adapter)
            envelope = _teams_envelope(text="ping")
            result = await bus.roundtrip(envelope)

        assert result.success is True
        assert result.channel == "teams"
        assert mock_post.call_count == 1
        sent_json = mock_post.call_args.kwargs.get("json", {})
        assert isinstance(sent_json.get("text"), str)
        assert len(sent_json["text"]) > 0

    asyncio.run(_run())


def test_teams_session_affinity():
    """Two messages from the same team/channel map to the same session_id."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
        ):
            adapter = _make_adapter()
            bus = _make_bus_with_teams(adapter)

            env1 = _teams_envelope(text="first message")
            env2 = _teams_envelope(text="second message", message_id="1-activity-00002")
            r1 = await bus.roundtrip(env1)
            r2 = await bus.roundtrip(env2)

        assert r1.session_id == r2.session_id
        assert r1.channel == "teams"
        assert r2.channel == "teams"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Webhook endpoint tests
# ---------------------------------------------------------------------------


def test_teams_webhook_message_event_returns_ok():
    """POST /teams/events with a message activity routes through the bus."""
    client = _make_nexus_client()

    with patch.object(
        httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=_make_ok_response()
    ):
        resp = client.post(
            "/api/nexus/teams/events",
            json=_teams_activity_payload(text="What is the capital of France?"),
        )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_teams_webhook_non_message_skipped():
    """POST /teams/events with a non-message activity type is skipped."""
    client = _make_nexus_client()

    resp = client.post(
        "/api/nexus/teams/events",
        json=_teams_activity_payload(activity_type="typing", text=""),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("skipped") is True
    assert "activity_type=typing" in data.get("reason", "")


def test_teams_webhook_bot_message_skipped():
    """POST /teams/events with from.role=bot must be skipped (no reply loop)."""
    client = _make_nexus_client()

    resp = client.post(
        "/api/nexus/teams/events",
        json=_teams_activity_payload(text="I am a bot", from_role="bot"),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("skipped") is True
    assert data.get("reason") == "fromBot"
