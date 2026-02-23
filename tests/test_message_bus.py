"""Unit tests for gateway.bus.MessageBus.

Tests ingest, deliver, and roundtrip operations using mocked adapters
and the real MessageFormatter / MessageRouter with a mock agent factory.

Uses asyncio.run() for async tests (compatible with the project's test setup).
"""

import asyncio

from gateway.bus import BusResult, MessageBus
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter, create_mock_agent


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _FakeAdapter:
    """Minimal ChannelAdapter stub that records what was sent."""

    def __init__(self, channel: str):
        self.channel = channel
        self.sent: list = []

    async def send_message(self, recipient_id: str, content: str, **kwargs):
        record = {"recipient_id": recipient_id, "content": content, **kwargs}
        self.sent.append(record)
        return {"message_id": f"fake-{len(self.sent)}", "success": True}

    async def initialize(self):
        pass

    async def shutdown(self):
        pass


def _make_bus(telegram_adapter=None, webchat_adapter=None):
    """Build a MessageBus with mock components."""
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    tg = telegram_adapter or _FakeAdapter("telegram")
    wc = webchat_adapter or _FakeAdapter("webchat")
    bus = MessageBus(
        router=router,
        formatter=formatter,
        adapters={"telegram": tg, "webchat": wc},
    )
    return bus, tg, wc


def _telegram_envelope(**overrides) -> MessageEnvelope:
    kwargs = dict(
        chat_id="12345678",
        sender_id="42",
        sender_name="Alice",
        text="Hello agent",
        message_id="msg-001",
    )
    kwargs.update(overrides)
    return MessageEnvelope.from_telegram(**kwargs)


# ---------------------------------------------------------------------------
# ingest tests
# ---------------------------------------------------------------------------


def test_bus_ingest_routes_to_agent():
    """Ingest should successfully route the envelope and return an agent response."""

    async def _run():
        bus, _, _ = _make_bus()
        envelope = _telegram_envelope()
        result = await bus.ingest(envelope)
        assert isinstance(result, BusResult)
        assert result.success is True
        assert result.operation == "ingest"
        assert result.channel == "telegram"
        assert result.agent_response is not None
        assert "reply" in result.agent_response

    asyncio.run(_run())


def test_bus_ingest_session_affinity():
    """Two messages from the same conversation must route to the same session."""

    async def _run():
        bus, _, _ = _make_bus()
        env1 = MessageEnvelope.from_telegram("99", "7", "Bob", "msg 1", "id-1")
        env2 = MessageEnvelope.from_telegram("99", "7", "Bob", "msg 2", "id-2")
        r1 = await bus.ingest(env1)
        r2 = await bus.ingest(env2)
        assert r1.session_id == r2.session_id

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# deliver tests
# ---------------------------------------------------------------------------


def test_bus_deliver_formats_and_sends():
    """Deliver should format the text and call the adapter's send_message."""

    async def _run():
        tg_adapter = _FakeAdapter("telegram")
        bus, tg, _ = _make_bus(telegram_adapter=tg_adapter)
        result = await bus.deliver("telegram", "12345678", "**Hello** world!")
        assert result.success is True
        assert result.operation == "deliver"
        assert result.channel == "telegram"
        # Formatter converts **bold** → *bold* for Telegram MarkdownV2
        assert result.formatted_text is not None
        assert "**Hello**" not in result.formatted_text
        # Adapter was called once
        assert len(tg.sent) == 1
        assert tg.sent[0]["recipient_id"] == "12345678"

    asyncio.run(_run())


def test_bus_deliver_missing_adapter_returns_error():
    """Deliver to an unregistered channel should return a failed BusResult."""

    async def _run():
        bus, _, _ = _make_bus()
        result = await bus.deliver("discord", "some-channel", "Hello!")
        assert result.success is False
        assert result.error is not None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# roundtrip tests
# ---------------------------------------------------------------------------


def test_bus_roundtrip_ingest_and_deliver():
    """Roundtrip should ingest the envelope AND deliver the agent reply."""

    async def _run():
        tg_adapter = _FakeAdapter("telegram")
        bus, tg, _ = _make_bus(telegram_adapter=tg_adapter)
        envelope = _telegram_envelope()
        result = await bus.roundtrip(envelope)
        assert result.success is True
        assert result.operation == "roundtrip"
        # Adapter should have been called once (the reply delivery)
        assert len(tg.sent) == 1

    asyncio.run(_run())


def test_bus_roundtrip_returns_session_id():
    """Roundtrip BusResult should carry the session_id from ingest."""

    async def _run():
        bus, _, _ = _make_bus()
        envelope = _telegram_envelope()
        result = await bus.roundtrip(envelope)
        assert result.session_id is not None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# deduplication via message_hash
# ---------------------------------------------------------------------------


def test_bus_deduplication_via_message_hash():
    """Envelopes must have a 16-char message_hash; different content → different hash."""
    env = MessageEnvelope.from_webchat(
        session_id="sess-1",
        sender_id="u1",
        sender_name="User",
        text="duplicate message",
        message_id="m1",
    )
    assert env.message_hash is not None
    assert len(env.message_hash) == 16  # SHA-256 hex truncated to 16 chars

    env2 = MessageEnvelope.from_webchat(
        session_id="sess-1",
        sender_id="u1",
        sender_name="User",
        text="completely different",
        message_id="m2",
    )
    # Different content → different hash
    assert env.message_hash != env2.message_hash
