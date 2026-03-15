"""Unit and integration tests for the Matrix channel adapter.

Tests cover:
1. MatrixAdapter.send_message() happy path (mocked httpx)
2. MatrixAdapter.send_message() API error (non-2xx response)
3. MatrixAdapter.send_message() network/transport error
4. Full bus.roundtrip() via MessageBus with mocked Matrix delivery
5. Session affinity: two messages in the same room route to the same session
6. MessageEnvelope.from_matrix() — correct field population
7. _poll_once() dispatches a new m.room.message to the bus callback
8. _poll_once() skips messages sent by the bot itself (own user_id)
9. _poll_once() skips events with empty/missing body text

No real Matrix homeserver is needed — httpx.AsyncClient is patched.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from channels.matrix import MatrixAdapter
from gateway.bus import MessageBus
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HOMESERVER = "http://localhost:8448"
_USER_ID = "@arcturus:localhost"
_ROOM_ID = "!room123:localhost"
_EVENT_ID = "$eventabc:localhost"
_SENDER_ID = "@alice:localhost"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ok_send_response(event_id: str = _EVENT_ID) -> MagicMock:
    """Mock PUT /send response (HTTP 200 with event_id)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"event_id": event_id}
    return mock_resp


def _make_error_response(status: int = 403, error: str = "M_FORBIDDEN") -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.json.return_value = {"errcode": error, "error": error}
    return mock_resp


def _make_adapter() -> MatrixAdapter:
    return MatrixAdapter(
        config={
            "homeserver_url": _HOMESERVER,
            "user_id": _USER_ID,
            "access_token": "test-token",
            "sync_interval": 999,  # prevent auto-polling in unit tests
        }
    )


def _make_bus_with_matrix(adapter: MatrixAdapter) -> MessageBus:
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    return MessageBus(
        router=router,
        formatter=formatter,
        adapters={"matrix": adapter},
    )


def _matrix_envelope(
    room_id: str = _ROOM_ID,
    text: str = "Hey Arcturus",
    event_id: str = _EVENT_ID,
) -> MessageEnvelope:
    return MessageEnvelope.from_matrix(
        room_id=room_id,
        sender_id=_SENDER_ID,
        sender_name="Alice",
        text=text,
        event_id=event_id,
    )


def _make_sync_response(
    room_id: str = _ROOM_ID,
    sender: str = _SENDER_ID,
    text: str = "Hello",
    event_id: str = _EVENT_ID,
    msgtype: str = "m.text",
) -> dict:
    """Build a minimal Matrix /sync response containing one message event."""
    return {
        "next_batch": "s123_456",
        "rooms": {
            "join": {
                room_id: {
                    "timeline": {
                        "events": [
                            {
                                "type": "m.room.message",
                                "event_id": event_id,
                                "sender": sender,
                                "content": {"msgtype": msgtype, "body": text},
                            }
                        ]
                    }
                }
            }
        },
    }


# ---------------------------------------------------------------------------
# MatrixAdapter unit tests
# ---------------------------------------------------------------------------


def test_matrix_send_message_success():
    """send_message() returns success=True and event_id on HTTP 200."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "put", new_callable=AsyncMock,
            return_value=_make_ok_send_response()
        ):
            adapter = _make_adapter()
            result = await adapter.send_message(_ROOM_ID, "Hello from Arcturus")

        assert result["success"] is True
        assert result["message_id"] == _EVENT_ID
        assert result["channel"] == "matrix"
        assert result.get("error") is None

    asyncio.run(_run())


def test_matrix_send_message_api_error():
    """send_message() returns success=False on M_FORBIDDEN (403)."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "put", new_callable=AsyncMock,
            return_value=_make_error_response(403, "M_FORBIDDEN")
        ):
            adapter = _make_adapter()
            result = await adapter.send_message(_ROOM_ID, "hello")

        assert result["success"] is False
        assert result["message_id"] is None
        assert "M_FORBIDDEN" in result["error"]

    asyncio.run(_run())


def test_matrix_send_message_network_error():
    """send_message() returns success=False on network failure."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "put", new_callable=AsyncMock,
            side_effect=httpx.RequestError("connection refused"),
        ):
            adapter = _make_adapter()
            result = await adapter.send_message(_ROOM_ID, "hello")

        assert result["success"] is False
        assert "connection refused" in result["error"]

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Bus integration test — full roundtrip
# ---------------------------------------------------------------------------


def test_matrix_roundtrip_via_bus():
    """bus.roundtrip() ingests Matrix envelope, formats reply, and delivers it."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "put", new_callable=AsyncMock,
            return_value=_make_ok_send_response()
        ) as mock_put:
            adapter = _make_adapter()
            bus = _make_bus_with_matrix(adapter)
            envelope = _matrix_envelope(text="ping")
            result = await bus.roundtrip(envelope)

        assert result.success is True
        assert result.channel == "matrix"
        assert mock_put.call_count == 1
        call_json = mock_put.call_args.kwargs.get("json", {})
        assert call_json.get("msgtype") == "m.text"
        assert isinstance(call_json.get("body"), str)
        assert len(call_json["body"]) > 0

    asyncio.run(_run())


def test_matrix_session_affinity():
    """Two messages from the same room_id map to the same session."""

    async def _run():
        with patch.object(
            httpx.AsyncClient, "put", new_callable=AsyncMock,
            return_value=_make_ok_send_response()
        ):
            adapter = _make_adapter()
            bus = _make_bus_with_matrix(adapter)
            env1 = _matrix_envelope(text="first")
            env2 = _matrix_envelope(text="second", event_id="$eventxyz:localhost")
            r1 = await bus.roundtrip(env1)
            r2 = await bus.roundtrip(env2)

        assert r1.session_id == r2.session_id
        assert r1.channel == "matrix"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Envelope tests
# ---------------------------------------------------------------------------


def test_matrix_from_envelope_fields():
    """from_matrix() populates all fields correctly."""
    env = MessageEnvelope.from_matrix(
        room_id=_ROOM_ID,
        sender_id=_SENDER_ID,
        sender_name="Alice",
        text="  Hello world  ",
        event_id=_EVENT_ID,
        is_direct=True,
    )
    assert env.channel == "matrix"
    assert env.channel_message_id == _EVENT_ID
    assert env.sender_id == _SENDER_ID
    assert env.sender_name == "Alice"
    assert env.content == "Hello world"
    assert env.conversation_id == _ROOM_ID
    assert env.thread_id == _ROOM_ID
    assert env.metadata["room_id"] == _ROOM_ID
    assert env.metadata["homeserver"] == "localhost"
    assert env.metadata["is_direct"] is True


# ---------------------------------------------------------------------------
# Sync loop unit tests (no asyncio.create_task — test _poll_once directly)
# ---------------------------------------------------------------------------


def test_matrix_sync_loop_dispatches_message():
    """_poll_once() calls the bus callback for a new m.room.message event."""

    async def _run():
        adapter = _make_adapter()
        adapter.client = httpx.AsyncClient()

        dispatched = []

        async def capture(envelope):
            dispatched.append(envelope)

        adapter.set_bus_callback(capture)

        sync_resp = MagicMock()
        sync_resp.status_code = 200
        sync_resp.json.return_value = _make_sync_response(text="Hello Arcturus")

        with patch.object(adapter.client, "get", new_callable=AsyncMock, return_value=sync_resp):
            await adapter._poll_once()

        await adapter.client.aclose()

        assert len(dispatched) == 1
        env = dispatched[0]
        assert env.channel == "matrix"
        assert env.content == "Hello Arcturus"
        assert env.conversation_id == _ROOM_ID

    asyncio.run(_run())


def test_matrix_sync_loop_skips_own_messages():
    """_poll_once() skips events where sender == bot user_id."""

    async def _run():
        adapter = _make_adapter()
        adapter.client = httpx.AsyncClient()

        dispatched = []

        async def capture(envelope):
            dispatched.append(envelope)

        adapter.set_bus_callback(capture)

        # sender is the bot itself
        sync_resp = MagicMock()
        sync_resp.status_code = 200
        sync_resp.json.return_value = _make_sync_response(sender=_USER_ID, text="I sent this")

        with patch.object(adapter.client, "get", new_callable=AsyncMock, return_value=sync_resp):
            await adapter._poll_once()

        await adapter.client.aclose()
        assert len(dispatched) == 0

    asyncio.run(_run())


def test_matrix_sync_loop_skips_empty_text():
    """_poll_once() skips m.room.message events with empty body."""

    async def _run():
        adapter = _make_adapter()
        adapter.client = httpx.AsyncClient()

        dispatched = []

        async def capture(envelope):
            dispatched.append(envelope)

        adapter.set_bus_callback(capture)

        sync_resp = MagicMock()
        sync_resp.status_code = 200
        sync_resp.json.return_value = _make_sync_response(text="")

        with patch.object(adapter.client, "get", new_callable=AsyncMock, return_value=sync_resp):
            await adapter._poll_once()

        await adapter.client.aclose()
        assert len(dispatched) == 0

    asyncio.run(_run())
