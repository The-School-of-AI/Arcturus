"""Message router for the Arcturus omni-channel gateway.

Routes normalized MessageEnvelopes to the appropriate agent instances
based on channel, conversation ID, and session affinity policies.
"""

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from gateway.envelope import MessageEnvelope

if TYPE_CHECKING:
    from gateway.formatter import MessageFormatter

logger = logging.getLogger(__name__)


class MessageRouter:
    """Routes messages to agent instances based on conversation context.

    Implements session affinity: ensures messages from the same conversation
    are routed to the same agent instance for continuity.
    """

    def __init__(
        self,
        agent_factory: Callable[..., Any],
        formatter: Optional["MessageFormatter"] = None,
    ):
        """Initialize the message router.

        Args:
            agent_factory: Callable that creates or retrieves an agent instance
                          (e.g., async function that takes session_id and returns agent)
            formatter: Optional MessageFormatter; if provided, the agent reply text
                       in the routing result will be formatted for the envelope's channel.
        """
        self.agent_factory = agent_factory
        self.formatter = formatter
        self.sessions: Dict[str, Any] = {}  # In-memory session map

    async def route(self, envelope: MessageEnvelope) -> Dict[str, Any]:
        """Route a message envelope to the appropriate agent.

        Args:
            envelope: MessageEnvelope to route

        Returns:
            Dict with routing result, agent response, and metadata
        """
        # Determine session ID for routing
        session_id = envelope.session_id or envelope.conversation_id or envelope.thread_id
        if not session_id:
            # Fallback: create session from channel + sender
            session_id = f"{envelope.channel}_{envelope.sender_id}"

        logger.info(
            f"Routing message from {envelope.sender_name} on {envelope.channel} to session {session_id}"
        )

        # Get or create agent instance for this session
        agent = await self._get_or_create_agent(session_id)

        # Process message through agent
        result = await self._process_message(agent, envelope)

        # Format the reply text for the envelope's channel if a formatter is wired in
        if self.formatter and isinstance(result, dict) and "reply" in result:
            result["reply"] = self.formatter.format(result["reply"], envelope.channel)

        return {
            "routed": True,
            "session_id": session_id,
            "channel": envelope.channel,
            "message_id": envelope.channel_message_id,
            "agent_response": result,
            "status": "success",
        }

    async def _get_or_create_agent(self, session_id: str) -> Any:
        """Get existing agent or create new one for session.

        Implements session affinity: same session always routes to same agent.

        Args:
            session_id: Unique session identifier

        Returns:
            Agent instance for this session
        """
        if session_id in self.sessions:
            logger.debug(f"Reusing agent for session {session_id}")
            return self.sessions[session_id]

        logger.debug(f"Creating new agent for session {session_id}")
        agent = await self.agent_factory(session_id=session_id)
        self.sessions[session_id] = agent
        return agent

    async def _process_message(self, agent: Any, envelope: MessageEnvelope) -> Dict[str, Any]:
        """Process a message through an agent.

        Args:
            agent: Agent instance
            envelope: MessageEnvelope to process

        Returns:
            Agent response dict
        """
        # Call agent's message processing method
        # The agent object should have an async method like process_message()
        # or we can call it as a callable
        if hasattr(agent, "process_message") and callable(agent.process_message):
            response = await agent.process_message(envelope)
        elif callable(agent):
            response = await agent(envelope)
        else:
            # Fallback: return mock response
            response = self._mock_agent_response(envelope)

        return response

    @staticmethod
    def _mock_agent_response(envelope: MessageEnvelope) -> Dict[str, Any]:
        """Generate a mock agent response for testing/stub purposes.

        Args:
            envelope: MessageEnvelope that was processed

        Returns:
            Mock agent response dict
        """
        return {
            "status": "processed",
            "message_id": envelope.channel_message_id,
            "reply": f"Echo: {envelope.content}",
            "channel": envelope.channel,
            "sender_id": envelope.sender_id,
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown all agent sessions."""
        logger.info(f"Shutting down {len(self.sessions)} agent sessions")
        # Clean up any resources associated with agents if needed
        self.sessions.clear()


async def create_mock_agent(session_id: str) -> Any:
    """Factory function to create a mock agent for testing.

    Args:
        session_id: Unique session identifier

    Returns:
        Mock agent object with process_message method
    """

    class MockAgent:
        """Simple mock agent for testing."""

        def __init__(self, session_id: str):
            self.session_id = session_id
            self.message_count = 0

        async def process_message(self, envelope: MessageEnvelope) -> Dict[str, Any]:
            """Process a message (mock implementation).

            Args:
                envelope: MessageEnvelope to process

            Returns:
                Mock response dict
            """
            self.message_count += 1
            return {
                "status": "processed",
                "message_id": envelope.channel_message_id,
                "reply": f"[Session {self.session_id}] Processed: {envelope.content}",
                "channel": envelope.channel,
                "sender_id": envelope.sender_id,
                "message_number": self.message_count,
            }

    return MockAgent(session_id)
