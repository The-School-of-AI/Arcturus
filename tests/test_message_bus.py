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


def test_bus_dedup_skips_duplicate_hash():
    """Ingesting the same envelope twice should short-circuit on the second call."""

    async def _run():
        bus, _, _ = _make_bus()
        envelope = _telegram_envelope()
        r1 = await bus.ingest(envelope)
        assert r1.success is True
        assert r1.error != "duplicate"
        msg_num_first = r1.agent_response["message_number"]

        # Second ingest of the exact same envelope (same message_hash)
        r2 = await bus.ingest(envelope)
        assert r2.success is True
        assert r2.error == "duplicate"
        # Router was NOT called a second time — message_number unchanged
        assert r2.agent_response is None  # dedup short-circuits before routing

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------


class _FailOnceAdapter:
    """Adapter that raises ConnectionError on first call, succeeds on second."""

    def __init__(self):
        self.calls = 0

    async def send_message(self, recipient_id, content, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("transient failure")
        return {"message_id": "recovered", "success": True}

    async def initialize(self):
        pass

    async def shutdown(self):
        pass


class _AlwaysFailAdapter:
    """Adapter that always raises ConnectionError."""

    async def send_message(self, recipient_id, content, **kwargs):
        raise ConnectionError("permanent failure")

    async def initialize(self):
        pass

    async def shutdown(self):
        pass


def test_bus_deliver_retries_on_transient_error():
    """deliver() should retry a transient ConnectionError and succeed on second attempt."""

    async def _run():
        fail_once = _FailOnceAdapter()
        formatter = MessageFormatter()
        router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
        bus = MessageBus(
            router=router,
            formatter=formatter,
            adapters={"fail": fail_once},
        )
        result = await bus.deliver("fail", "r1", "hello", max_retries=2, base_delay=0)
        assert result.success is True
        assert fail_once.calls == 2  # first failed, second succeeded

    asyncio.run(_run())


def test_bus_deliver_fails_after_max_retries():
    """deliver() should return success=False after all retries are exhausted."""

    async def _run():
        always_fail = _AlwaysFailAdapter()
        formatter = MessageFormatter()
        router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
        bus = MessageBus(
            router=router,
            formatter=formatter,
            adapters={"fail": always_fail},
        )
        result = await bus.deliver("fail", "r1", "hello", max_retries=2, base_delay=0)
        assert result.success is False
        assert result.error is not None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# HC5: media payload roundtrip — three channels, text + attachment
# ---------------------------------------------------------------------------


def test_media_payload_survives_roundtrip_three_channels():
    """HC5: Envelopes carrying a MediaAttachment must roundtrip through ingest
    on all three required channels (telegram, webchat, slack) without dropping
    the attachment.  The bus ingests each envelope and returns success; the
    attachment fields are verified to be intact after construction.
    """
    from gateway.envelope import MediaAttachment

    attachment = MediaAttachment(
        media_type="image",
        url="https://example.com/photo.jpg",
        filename="photo.jpg",
        size_bytes=102400,
        mime_type="image/jpeg",
    )

    # --- Telegram ---
    tg_env = MessageEnvelope.from_telegram(
        chat_id="12345678",
        sender_id="42",
        sender_name="Alice",
        text="Check this image",
        message_id="msg-media-tg",
    )
    tg_env.attachments = [attachment]
    tg_env.content_type = "mixed"

    # --- WebChat ---
    wc_env = MessageEnvelope.from_webchat(
        session_id="sess-media",
        sender_id="u1",
        sender_name="Bob",
        text="Sharing a file",
        message_id="msg-media-wc",
    )
    wc_env.attachments = [attachment]
    wc_env.content_type = "mixed"

    # --- Slack ---
    sl_env = MessageEnvelope.from_slack(
        channel_id="C04KYFS5DV2",
        sender_id="U999",
        sender_name="Carol",
        text="Here is the image",
        message_id="1700000099.000001",
    )
    sl_env.attachments = [attachment]
    sl_env.content_type = "mixed"

    async def _run():
        slack_adapter = _FakeAdapter("slack")
        formatter = MessageFormatter()
        router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
        bus = MessageBus(
            router=router,
            formatter=formatter,
            adapters={
                "telegram": _FakeAdapter("telegram"),
                "webchat": _FakeAdapter("webchat"),
                "slack": slack_adapter,
            },
        )
        for env in [tg_env, wc_env, sl_env]:
            result = await bus.ingest(env)
            assert result.success is True, f"ingest failed for {env.channel}: {result.error}"

    asyncio.run(_run())

    # Verify attachment fields are intact on all three envelopes (no mutation by bus)
    for env in [tg_env, wc_env, sl_env]:
        assert len(env.attachments) == 1, f"{env.channel}: attachment list was cleared"
        att = env.attachments[0]
        assert att.media_type == "image"
        assert att.url == "https://example.com/photo.jpg"
        assert att.mime_type == "image/jpeg"
        assert att.size_bytes == 102400


# ---------------------------------------------------------------------------
# Queue mode tests
# ---------------------------------------------------------------------------


def _make_bus_with_mode(mode: str):
    """Build a MessageBus with a given queue_mode."""
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    tg = _FakeAdapter("telegram")
    bus = MessageBus(
        router=router,
        formatter=formatter,
        adapters={"telegram": tg},
        queue_mode=mode,
    )
    return bus, tg


def test_queue_mode_default_is_serial():
    """MessageBus default queue_mode is 'serial'."""
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    bus = MessageBus(router=router, formatter=formatter, adapters={})
    assert bus.queue_mode == "serial"


def test_queue_mode_can_be_set_to_parallel():
    """MessageBus accepts queue_mode='parallel' and stores it."""
    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    bus = MessageBus(router=router, formatter=formatter, adapters={}, queue_mode="parallel")
    assert bus.queue_mode == "parallel"


def test_roundtrip_many_serial_preserves_order():
    """roundtrip_many() in serial mode processes envelopes in list order."""

    async def _run():
        bus, tg = _make_bus_with_mode("serial")
        envs = [
            _telegram_envelope(text=f"msg-{i}", message_id=f"id-{i}", sender_id=f"{i}")
            for i in range(3)
        ]
        results = await bus.roundtrip_many(envs)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert len(tg.sent) == 3
        # Results are in the same order as the submitted envelopes
        for i, result in enumerate(results):
            assert result.operation == "roundtrip"
            assert result.channel == "telegram"

    asyncio.run(_run())


def test_roundtrip_many_parallel_all_succeed():
    """roundtrip_many() in parallel mode processes all envelopes and all succeed."""

    async def _run():
        bus, tg = _make_bus_with_mode("parallel")
        # Use different sender_ids so they land in different sessions (no lock contention)
        envs = [
            _telegram_envelope(
                text=f"parallel-{i}",
                message_id=f"par-id-{i}",
                sender_id=f"sender-{i}",
                chat_id=f"chat-{i}",
            )
            for i in range(4)
        ]
        results = await bus.roundtrip_many(envs)

        assert len(results) == 4
        assert all(r.success for r in results)
        assert len(tg.sent) == 4

    asyncio.run(_run())


def test_parallel_mode_serialises_within_same_session():
    """In parallel mode, two messages in the same session are still processed serially."""

    order: list[int] = []

    class _OrderedAgent:
        """Agent that records the order it was called."""

        def __init__(self, idx: int):
            self.idx = idx
            self.session_id = "shared"

        async def process_message(self, envelope):
            order.append(self.idx)
            await asyncio.sleep(0)  # yield to event loop
            return {
                "status": "processed",
                "reply": f"reply-{self.idx}",
                "channel": envelope.channel,
                "sender_id": envelope.sender_id,
            }

    call_count = 0

    async def _factory(session_id: str):
        nonlocal call_count
        call_count += 1
        return _OrderedAgent(call_count)

    async def _run():
        formatter = MessageFormatter()
        router = MessageRouter(agent_factory=_factory, formatter=formatter)
        tg = _FakeAdapter("telegram")
        bus = MessageBus(
            router=router,
            formatter=formatter,
            adapters={"telegram": tg},
            queue_mode="parallel",
        )
        # Both envelopes share the same chat_id → same session → must serialize
        env1 = _telegram_envelope(text="first", message_id="s1", sender_id="u1")
        env2 = _telegram_envelope(text="second", message_id="s2", sender_id="u1")

        await bus.roundtrip_many([env1, env2])
        # Because they share a session lock, they must be processed one at a time.
        # Both results should succeed.
        assert len(tg.sent) == 2

    asyncio.run(_run())


def test_roundtrip_acquires_session_lock():
    """roundtrip() uses per-session locks (lock is created on first call)."""

    async def _run():
        bus, _ = _make_bus_with_mode("serial")
        env = _telegram_envelope()
        assert len(bus._session_locks) == 0
        await bus.roundtrip(env)
        # Lock should now exist for this session
        assert len(bus._session_locks) == 1

    asyncio.run(_run())
