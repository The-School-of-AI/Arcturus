"""Unified Message Bus for the Arcturus gateway.

Orchestrates the full inbound/outbound flow:

    Inbound:  envelope → MessageRouter → agent response
    Outbound: text → MessageFormatter → ChannelAdapter.send_message()
    Roundtrip: inbound + auto-deliver the agent reply back to the sender

Queue modes
-----------
``serial`` (default)
    Each ``roundtrip()`` call is awaited inline.  Within a session the bus also
    acquires a per-session ``asyncio.Lock`` so that concurrent callers for the
    *same* session are serialised (messages are never interleaved).

``parallel``
    When multiple ``roundtrip()`` calls arrive for *different* sessions they run
    concurrently via ``asyncio.gather``.  Use ``roundtrip_many()`` to submit a
    batch.  Within a single session the per-session lock still guarantees serial
    order, so parallel mode only speeds up *cross-session* throughput.

Usage::

    from gateway.bus import MessageBus
    from gateway.formatter import MessageFormatter
    from gateway.router import MessageRouter, create_mock_agent
    from channels.telegram import TelegramAdapter

    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    adapters = {"telegram": TelegramAdapter()}

    # Serial mode (default)
    bus = MessageBus(router=router, formatter=formatter, adapters=adapters)
    result = await bus.roundtrip(envelope)

    # Parallel mode — process multiple envelopes concurrently
    bus = MessageBus(router=router, formatter=formatter, adapters=adapters,
                     queue_mode="parallel")
    results = await bus.roundtrip_many([env1, env2, env3])
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

from channels.base import ChannelAdapter
from core.loop import retry_with_backoff
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter

logger = logging.getLogger(__name__)

QueueMode = Literal["serial", "parallel"]


@dataclass
class BusResult:
    """Structured result returned by all MessageBus operations."""

    success: bool
    operation: str  # "ingest" | "deliver" | "roundtrip"
    channel: str
    session_id: str | None = None
    message_id: str | None = None
    formatted_text: str | None = None
    agent_response: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "operation": self.operation,
            "channel": self.channel,
            "session_id": self.session_id,
            "message_id": self.message_id,
            "formatted_text": self.formatted_text,
            "agent_response": self.agent_response,
            "error": self.error,
        }


class MessageBus:
    """Unified bus that wires envelope → formatter → router → adapter.

    Responsibilities:
    - **Ingest**: Route an inbound MessageEnvelope to the correct agent session.
    - **Deliver**: Format an agent reply and send it via the correct ChannelAdapter.
    - **Roundtrip**: Ingest + auto-deliver the agent's reply in one call.
    - **Queue mode**: ``serial`` (default) serialises within each session;
      ``parallel`` allows concurrent dispatch across different sessions.
    """

    def __init__(
        self,
        router: MessageRouter,
        formatter: MessageFormatter,
        adapters: dict[str, ChannelAdapter],
        queue_mode: QueueMode = "serial",
    ):
        """Initialise the MessageBus.

        Args:
            router: MessageRouter that dispatches envelopes to agent sessions.
            formatter: MessageFormatter that converts text to channel-native format.
            adapters: Mapping of channel name → initialised ChannelAdapter instance.
                      e.g. ``{"telegram": TelegramAdapter(), "webchat": WebChatAdapter()}``
            queue_mode: ``"serial"`` (default) — each roundtrip awaited inline;
                        ``"parallel"`` — use ``roundtrip_many()`` to dispatch
                        multiple envelopes concurrently across sessions.
        """
        self.router = router
        self.formatter = formatter
        self.adapters = adapters
        self.queue_mode: QueueMode = queue_mode
        self._seen_hashes: set[str] = set()
        # Per-session locks ensure messages within a session are always serialised,
        # regardless of queue_mode.
        self._session_locks: dict[str, asyncio.Lock] = {}

    async def ingest(self, envelope: MessageEnvelope) -> BusResult:
        """Route an inbound envelope to the appropriate agent.

        Args:
            envelope: Normalised MessageEnvelope from any channel.

        Returns:
            BusResult with agent_response populated on success.
        """
        logger.info(
            "Bus.ingest: channel=%s sender=%s hash=%s",
            envelope.channel,
            envelope.sender_id,
            envelope.message_hash,
        )
        # Idempotency: skip envelopes we have already processed.
        print(f"[BUS.ingest] hash={envelope.message_hash} seen={envelope.message_hash in self._seen_hashes}")
        if envelope.message_hash and envelope.message_hash in self._seen_hashes:
            logger.info(
                "Bus.ingest: duplicate message_hash=%s — skipped", envelope.message_hash
            )
            print(f"[BUS.ingest] SKIPPING duplicate")
            return BusResult(
                success=True,
                operation="ingest",
                channel=envelope.channel,
                message_id=envelope.channel_message_id,
                error="duplicate",
            )
        if envelope.message_hash:
            self._seen_hashes.add(envelope.message_hash)

        try:
            routing = await self.router.route(envelope)
            print(f"[BUS.ingest] routing={str(routing)[:300]}")
            return BusResult(
                success=True,
                operation="ingest",
                channel=envelope.channel,
                session_id=routing.get("session_id"),
                message_id=routing.get("message_id"),
                agent_response=routing.get("agent_response"),
            )
        except Exception as exc:
            logger.exception("Bus.ingest failed: %s", exc)
            print(f"[BUS.ingest] EXCEPTION: {exc}")
            return BusResult(
                success=False,
                operation="ingest",
                channel=envelope.channel,
                error=str(exc),
            )

    async def deliver(
        self,
        channel: str,
        recipient_id: str,
        text: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        **kwargs,
    ) -> BusResult:
        """Format *text* and send it to *recipient_id* on *channel*.

        Args:
            channel: Target channel (``"telegram"``, ``"webchat"``, …).
            recipient_id: Channel-specific recipient identifier (chat_id, session_id, …).
            text: Agent response text (Markdown).
            **kwargs: Passed through to the ChannelAdapter.send_message().

        Returns:
            BusResult with formatted_text and message_id populated on success.
        """
        formatted = self.formatter.format(text, channel)
        logger.debug(
            "Bus.deliver: channel=%s recipient=%s len=%d",
            channel,
            recipient_id,
            len(formatted),
        )

        adapter = self.adapters.get(channel)
        if adapter is None:
            msg = f"No adapter registered for channel '{channel}'"
            logger.error(msg)
            return BusResult(
                success=False,
                operation="deliver",
                channel=channel,
                formatted_text=formatted,
                error=msg,
            )

        try:
            async def _send():
                return await adapter.send_message(recipient_id, formatted, **kwargs)

            send_result = await retry_with_backoff(
                _send,
                max_retries=max_retries,
                base_delay=base_delay,
                retryable_errors=(asyncio.TimeoutError, ConnectionError, TimeoutError),
            )
            return BusResult(
                success=send_result.get("success", True),
                operation="deliver",
                channel=channel,
                message_id=str(send_result.get("message_id", "")),
                formatted_text=formatted,
                error=send_result.get("error"),
            )
        except Exception as exc:
            logger.exception("Bus.deliver failed: %s", exc)
            return BusResult(
                success=False,
                operation="deliver",
                channel=channel,
                formatted_text=formatted,
                error=str(exc),
            )

    def _session_lock(self, envelope: MessageEnvelope) -> asyncio.Lock:
        """Return (creating if needed) the per-session asyncio.Lock."""
        key = (
            envelope.session_id
            or envelope.conversation_id
            or envelope.thread_id
            or f"{envelope.channel}_{envelope.sender_id}"
        )
        if key not in self._session_locks:
            self._session_locks[key] = asyncio.Lock()
        return self._session_locks[key]

    async def _send_typing(self, envelope: MessageEnvelope) -> None:
        """Best-effort typing indicator — never blocks or raises."""
        adapter = self.adapters.get(envelope.channel)
        if adapter is None:
            return
        recipient = (
            envelope.session_id
            or envelope.conversation_id
            or envelope.sender_id
        )
        try:
            await adapter.send_typing_indicator(recipient)
        except Exception:
            pass  # typing is cosmetic — never fail the pipeline

    async def roundtrip(self, envelope: MessageEnvelope) -> BusResult:
        """Ingest an inbound envelope and auto-deliver the agent's reply.

        The agent reply text is taken from ``agent_response["reply"]``.
        The formatted reply is sent back to the original sender
        (``envelope.sender_id`` on ``envelope.channel``).

        Within a session, the per-session lock serialises concurrent callers so
        messages are never processed out of order.  In ``"parallel"`` queue mode
        the lock still guarantees intra-session ordering while allowing
        *inter-session* concurrency via ``roundtrip_many()``.

        Args:
            envelope: Inbound MessageEnvelope.

        Returns:
            BusResult from the deliver step (includes ingest data in agent_response).
        """
        async with self._session_lock(envelope):
            # Send typing indicator before agent processes
            await self._send_typing(envelope)
            ingest_result = await self.ingest(envelope)
            print(f"[BUS] ingest done: success={ingest_result.success} agent_response={type(ingest_result.agent_response).__name__}={ingest_result.agent_response}")
            if not ingest_result.success:
                ingest_result.operation = "roundtrip"
                return ingest_result

            reply_text = ""
            if ingest_result.agent_response:
                reply_text = ingest_result.agent_response.get("reply", "")

            print(f"[BUS] reply_text ({len(reply_text)} chars): {reply_text[:120] if reply_text else '(empty)'}")
            if not reply_text:
                # Nothing to deliver; return the ingest result as-is.
                ingest_result.operation = "roundtrip"
                return ingest_result

            # Use the most specific routing key for the reply recipient.
            # For WebChat, session_id is the outbox key (not raw sender_id).
            # For Telegram/Slack, conversation_id or sender_id is appropriate.
            reply_recipient = (
                envelope.session_id
                or envelope.conversation_id
                or envelope.sender_id
            )
            deliver_result = await self.deliver(
                channel=envelope.channel,
                recipient_id=reply_recipient,
                text=reply_text,
                attachments=envelope.attachments,
            )
            # Merge ingest metadata into the deliver result for full context.
            deliver_result.operation = "roundtrip"
            deliver_result.session_id = ingest_result.session_id
            deliver_result.agent_response = ingest_result.agent_response
            return deliver_result

    async def roundtrip_many(
        self, envelopes: list[MessageEnvelope]
    ) -> list[BusResult]:
        """Process multiple envelopes, respecting the configured queue_mode.

        ``serial``: envelopes are processed one at a time in list order.
        ``parallel``: envelopes from *different* sessions run concurrently via
        ``asyncio.gather``; envelopes sharing a session are still serialised by
        the per-session lock.

        Args:
            envelopes: List of inbound MessageEnvelopes to process.

        Returns:
            List of BusResults in the same order as *envelopes*.
        """
        if self.queue_mode == "parallel":
            return list(
                await asyncio.gather(*(self.roundtrip(env) for env in envelopes))
            )
        # Serial: process one at a time in order
        results = []
        for env in envelopes:
            results.append(await self.roundtrip(env))
        return results

    async def shutdown(self) -> None:
        """Gracefully shut down the router and all registered adapters."""
        await self.router.shutdown()
        for name, adapter in self.adapters.items():
            try:
                await adapter.shutdown()
            except Exception as exc:
                logger.warning("Error shutting down adapter '%s': %s", name, exc)
