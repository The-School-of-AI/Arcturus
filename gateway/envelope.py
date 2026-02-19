"""MessageEnvelope: Unified message format for all channels.

This module defines the standard message envelope that normalizes
inbound messages from any channel (Telegram, WebChat, Slack, etc.)
into a common format for agent processing.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MediaAttachment:
    """Represents a media file attached to a message."""

    media_type: str  # "image", "video", "audio", "document"
    url: str  # URL or file path
    filename: Optional[str] = None
    size_bytes: Optional[int] = None
    mime_type: Optional[str] = None


@dataclass
class MessageEnvelope:
    """Unified message format across all channels.

    This envelope normalizes messages from any channel into a standard
    format that the agent loop can process uniformly.
    """

    # Channel information (required)
    channel: str  # "telegram", "webchat", "slack", "discord", etc.
    channel_message_id: str  # Unique ID from the source channel

    # Sender information (required)
    sender_id: str  # Channel-specific sender identifier
    sender_name: str  # Display name

    # Message content (required)
    content: str  # Normalized plain text content

    # Optional fields with defaults
    sender_is_bot: bool = False

    # Content details
    content_type: str = "text"  # "text", "media", "mixed"

    # Threading and context
    thread_id: Optional[str] = None  # For conversation threading
    conversation_id: Optional[str] = None  # Unique conversation identifier
    parent_message_id: Optional[str] = None  # If this is a reply

    # Media attachments
    attachments: List[MediaAttachment] = field(default_factory=list)

    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Deduplication and idempotency
    message_hash: Optional[str] = None  # For detecting duplicates

    # Session/routing context
    session_id: Optional[str] = None  # Multi-agent routing identifier

    def __post_init__(self):
        """Validate and normalize the envelope after initialization."""
        if not self.channel:
            raise ValueError("channel is required")
        if not self.sender_id:
            raise ValueError("sender_id is required")
        if not self.content:
            raise ValueError("content is required")

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text content across channels.

        Args:
            text: Raw text from any channel

        Returns:
            Normalized plain text (stripped, no excessive whitespace)
        """
        if not text:
            return ""
        # Remove leading/trailing whitespace
        normalized = text.strip()
        # Collapse multiple whitespace into single spaces
        normalized = " ".join(normalized.split())
        return normalized

    @classmethod
    def from_telegram(
        cls,
        chat_id: str,
        sender_id: str,
        sender_name: str,
        text: str,
        message_id: str,
        is_bot: bool = False,
        **kwargs,
    ) -> "MessageEnvelope":
        """Create a MessageEnvelope from a Telegram message.

        Args:
            chat_id: Telegram chat_id (for threading)
            sender_id: Telegram user_id
            sender_name: User's display name
            text: Message text
            message_id: Telegram message_id
            is_bot: Whether sender is a bot
            **kwargs: Additional metadata to store

        Returns:
            MessageEnvelope instance
        """
        return cls(
            channel="telegram",
            channel_message_id=str(message_id),
            sender_id=str(sender_id),
            sender_name=sender_name,
            content=cls.normalize_text(text),
            thread_id=str(chat_id),
            conversation_id=str(chat_id),
            sender_is_bot=is_bot,
            metadata=kwargs,
        )

    @classmethod
    def from_webchat(
        cls,
        session_id: str,
        sender_id: str,
        sender_name: str,
        text: str,
        message_id: str,
        **kwargs,
    ) -> "MessageEnvelope":
        """Create a MessageEnvelope from a WebChat message.

        Args:
            session_id: WebChat session identifier
            sender_id: Session user identifier
            sender_name: User's display name
            text: Message text
            message_id: WebChat message_id
            **kwargs: Additional metadata to store

        Returns:
            MessageEnvelope instance
        """
        return cls(
            channel="webchat",
            channel_message_id=str(message_id),
            sender_id=str(sender_id),
            sender_name=sender_name,
            content=cls.normalize_text(text),
            thread_id=session_id,
            conversation_id=session_id,
            session_id=session_id,
            metadata=kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert envelope to dictionary for serialization."""
        return {
            "channel": self.channel,
            "channel_message_id": self.channel_message_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "sender_is_bot": self.sender_is_bot,
            "content": self.content,
            "content_type": self.content_type,
            "thread_id": self.thread_id,
            "conversation_id": self.conversation_id,
            "parent_message_id": self.parent_message_id,
            "attachments": [
                {
                    "media_type": a.media_type,
                    "url": a.url,
                    "filename": a.filename,
                    "size_bytes": a.size_bytes,
                    "mime_type": a.mime_type,
                }
                for a in self.attachments
            ],
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "message_hash": self.message_hash,
            "session_id": self.session_id,
        }
