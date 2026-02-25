"""Unified Message Bus for the Arcturus gateway.

Orchestrates the full inbound/outbound flow:

    Inbound:  envelope → MessageRouter → agent response
    Outbound: text → MessageFormatter → ChannelAdapter.send_message()
    Roundtrip: inbound + auto-deliver the agent reply back to the sender

Usage::

    from gateway.bus import MessageBus
    from gateway.formatter import MessageFormatter
    from gateway.router import MessageRouter, create_mock_agent
    from channels.telegram import TelegramAdapter

    formatter = MessageFormatter()
    router = MessageRouter(agent_factory=create_mock_agent, formatter=formatter)
    adapters = {"telegram": TelegramAdapter()}

    bus = MessageBus(router=router, formatter=formatter, adapters=adapters)

    # Ingest an inbound envelope (agent processes it)
    result = await bus.ingest(envelope)

    # Deliver an outbound message (format + send)
    result = await bus.deliver("telegram", "12345678", "**Hello** world!")

    # Full roundtrip (ingest + auto-reply)
    result = await bus.roundtrip(envelope)
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from channels.base import ChannelAdapter
from gateway.envelope import MessageEnvelope
from gateway.formatter import MessageFormatter
from gateway.router import MessageRouter

logger = logging.getLogger(__name__)


@dataclass
class BusResult:
    """Structured result returned by all MessageBus operations."""

    success: bool
    operation: str  # "ingest" | "deliver" | "roundtrip"
    channel: str
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    formatted_text: Optional[str] = None
    agent_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
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
    """

    def __init__(
        self,
        router: MessageRouter,
        formatter: MessageFormatter,
        adapters: Dict[str, ChannelAdapter],
    ):
        """Initialise the MessageBus.

        Args:
            router: MessageRouter that dispatches envelopes to agent sessions.
            formatter: MessageFormatter that converts text to channel-native format.
            adapters: Mapping of channel name → initialised ChannelAdapter instance.
                      e.g. ``{"telegram": TelegramAdapter(), "webchat": WebChatAdapter()}``
        """
        self.router = router
        self.formatter = formatter
        self.adapters = adapters

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
        try:
            routing = await self.router.route(envelope)
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
            send_result = await adapter.send_message(recipient_id, formatted, **kwargs)
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

    async def roundtrip(self, envelope: MessageEnvelope) -> BusResult:
        """Ingest an inbound envelope and auto-deliver the agent's reply.

        The agent reply text is taken from ``agent_response["reply"]``.
        The formatted reply is sent back to the original sender
        (``envelope.sender_id`` on ``envelope.channel``).

        Args:
            envelope: Inbound MessageEnvelope.

        Returns:
            BusResult from the deliver step (includes ingest data in agent_response).
        """
        ingest_result = await self.ingest(envelope)
        if not ingest_result.success:
            ingest_result.operation = "roundtrip"
            return ingest_result

        reply_text = ""
        if ingest_result.agent_response:
            reply_text = ingest_result.agent_response.get("reply", "")

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
        )
        # Merge ingest metadata into the deliver result for full context.
        deliver_result.operation = "roundtrip"
        deliver_result.session_id = ingest_result.session_id
        deliver_result.agent_response = ingest_result.agent_response
        return deliver_result

    async def shutdown(self) -> None:
        """Gracefully shut down the router and all registered adapters."""
        await self.router.shutdown()
        for name, adapter in self.adapters.items():
            try:
                await adapter.shutdown()
            except Exception as exc:
                logger.warning("Error shutting down adapter '%s': %s", name, exc)
