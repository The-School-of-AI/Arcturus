"""Base channel adapter interface for Arcturus gateway."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ChannelAdapter(ABC):
    """Abstract base class for channel adapters.

    Each channel (Telegram, WebChat, Slack, etc.) implements this interface
    to normalize inbound messages and format outbound responses.
    """

    def __init__(self, channel_name: str, config: Optional[Dict[str, Any]] = None):
        """Initialize the channel adapter.

        Args:
            channel_name: Identifier for this channel (e.g., "telegram", "webchat")
            config: Channel-specific configuration dict
        """
        self.channel_name = channel_name
        self.config = config or {}

    @abstractmethod
    async def send_message(self, recipient_id: str, content: str, **kwargs) -> Dict[str, Any]:
        """Send a message to a recipient on this channel.

        Args:
            recipient_id: Channel-specific recipient identifier
            content: Message content (plain text or formatted per channel)
            **kwargs: Channel-specific options (media, buttons, etc.)

        Returns:
            Dict with response metadata (message_id, timestamp, etc.)
        """
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the channel adapter (connect, authenticate, etc.)."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully shutdown the channel adapter."""
        pass
