"""MessageEnvelope: Unified message format for all channels.

This module defines the standard message envelope that normalizes
inbound messages from any channel (Telegram, WebChat, Slack, etc.)
into a common format for agent processing.
"""

import hashlib
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
        if self.message_hash is None:
            self.message_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute a deduplication hash from channel, sender, content, and timestamp.

        Returns:
            First 16 hex characters of SHA-256 over key fields.
        """
        raw = f"{self.channel}:{self.sender_id}:{self.content}:{self.timestamp.isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

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

    @classmethod
    def from_slack(
        cls,
        channel_id: str,
        sender_id: str,
        sender_name: str,
        text: str,
        message_id: str,
        is_bot: bool = False,
        thread_ts: Optional[str] = None,
        **kwargs,
    ) -> "MessageEnvelope":
        """Create a MessageEnvelope from a Slack event payload.

        Args:
            channel_id: Slack channel or DM ID (C…, D…)
            sender_id: Slack user ID (U…)
            sender_name: User display name
            text: Message text (mrkdwn)
            message_id: Slack event ``ts`` field
            is_bot: Whether sender is a bot/app
            thread_ts: Parent ``ts`` for threaded messages
            **kwargs: Additional metadata to store

        Returns:
            MessageEnvelope instance
        """
        return cls(
            channel="slack",
            channel_message_id=str(message_id),
            sender_id=str(sender_id),
            sender_name=sender_name,
            content=cls.normalize_text(text),
            thread_id=thread_ts or str(channel_id),
            conversation_id=str(channel_id),
            sender_is_bot=is_bot,
            metadata={"channel_id": channel_id, "thread_ts": thread_ts, **kwargs},
        )

    @classmethod
    def from_discord(
        cls,
        guild_id: str,
        channel_id: str,
        sender_id: str,
        sender_name: str,
        text: str,
        message_id: str,
        is_bot: bool = False,
        **kwargs,
    ) -> "MessageEnvelope":
        """Create a MessageEnvelope from a Discord message event.

        Args:
            guild_id: Discord server (guild) ID
            channel_id: Discord channel ID
            sender_id: Discord user ID
            sender_name: User display name
            text: Message content
            message_id: Discord message snowflake ID
            is_bot: Whether sender is a bot
            **kwargs: Additional metadata to store

        Returns:
            MessageEnvelope instance
        """
        return cls(
            channel="discord",
            channel_message_id=str(message_id),
            sender_id=str(sender_id),
            sender_name=sender_name,
            content=cls.normalize_text(text),
            thread_id=str(channel_id),
            conversation_id=f"{guild_id}:{channel_id}",
            sender_is_bot=is_bot,
            metadata={"guild_id": guild_id, "channel_id": channel_id, **kwargs},
        )

    @classmethod
    def from_whatsapp(
        cls,
        phone_number: str,
        contact_name: str,
        text: str,
        message_id: str,
        is_group: bool = False,
        group_id: Optional[str] = None,
        is_bot: bool = False,
        **kwargs,
    ) -> "MessageEnvelope":
        """Create a MessageEnvelope from a WhatsApp message (via Baileys bridge).

        For DMs, the phone number is both the sender_id and the conversation_id.
        For group messages, the group JID becomes the conversation_id so all
        group members share one agent session.

        Args:
            phone_number: Sender's normalized phone number (digits only, no @suffix).
            contact_name: Sender's WhatsApp display name (push name).
            text: Message text (plain UTF-8).
            message_id: Baileys message key ID (globally unique).
            is_group: True if the message came from a group chat.
            group_id: Group JID (e.g. ``"123456789@g.us"``) when is_group=True.
            is_bot: Whether the sender is the bot (bridge filters fromMe, always False).
            **kwargs: Additional metadata to store.

        Returns:
            MessageEnvelope instance.
        """
        # DM    → conversation_id = phone_number (one session per contact)
        # Group → conversation_id = group_id     (one session per group)
        conversation_id = group_id if is_group and group_id else phone_number
        return cls(
            channel="whatsapp",
            channel_message_id=str(message_id),
            sender_id=phone_number,
            sender_name=contact_name,
            content=cls.normalize_text(text),
            thread_id=conversation_id,
            conversation_id=conversation_id,
            sender_is_bot=is_bot,
            metadata={
                "phone_number": phone_number,
                "is_group": is_group,
                "group_id": group_id,
                **kwargs,
            },
        )

    @classmethod
    def from_imessage(
        cls,
        chat_guid: str,
        sender_id: str,
        sender_name: str,
        text: str,
        message_guid: str,
        is_group: bool = False,
        is_bot: bool = False,
        **kwargs,
    ) -> "MessageEnvelope":
        """Create a MessageEnvelope from a BlueBubbles webhook payload.

        Args:
            chat_guid: BlueBubbles chat GUID (e.g. ``iMessage;+;+15551234567``
                       for DMs or ``iMessage;+;chat{guid}`` for groups).
            sender_id: Sender's iMessage handle (phone or email).
            sender_name: Sender's display name (from Contacts or address book).
            text: Message text.
            message_guid: BlueBubbles message GUID (globally unique).
            is_group: True if the message came from a group iMessage chat.
            is_bot: Whether the sender is the bot itself (filtered upstream).
            **kwargs: Additional metadata to store.

        Returns:
            MessageEnvelope instance.
        """
        return cls(
            channel="imessage",
            channel_message_id=message_guid,
            sender_id=sender_id,
            sender_name=sender_name,
            content=cls.normalize_text(text),
            thread_id=chat_guid,
            conversation_id=chat_guid,
            sender_is_bot=is_bot,
            metadata={
                "chat_guid": chat_guid,
                "is_group": is_group,
                **kwargs,
            },
        )

    @classmethod
    def from_googlechat(
        cls,
        space_name: str,
        sender_id: str,
        sender_name: str,
        text: str,
        message_name: str,
        is_bot: bool = False,
        thread_name: Optional[str] = None,
        **kwargs,
    ) -> "MessageEnvelope":
        """Create a MessageEnvelope from a Google Chat event payload.

        Args:
            space_name: Google Chat Space resource name (``spaces/XXXXXXXXX``).
            sender_id: Sender's Google user ID or email.
            sender_name: Sender's display name.
            text: Message text (may include @mentions like ``<users/123>``).
            message_name: Message resource name (``spaces/X/messages/Y``).
            is_bot: Whether the sender is a bot.
            thread_name: Thread resource name for threaded conversations.
            **kwargs: Additional metadata to store.

        Returns:
            MessageEnvelope instance.
        """
        return cls(
            channel="googlechat",
            channel_message_id=message_name,
            sender_id=sender_id,
            sender_name=sender_name,
            content=cls.normalize_text(text),
            thread_id=thread_name or space_name,
            conversation_id=space_name,
            sender_is_bot=is_bot,
            metadata={"space_name": space_name, "thread_name": thread_name, **kwargs},
        )

    @classmethod
    def from_teams(
        cls,
        team_id: str,
        channel_id: str,
        sender_id: str,
        sender_name: str,
        text: str,
        message_id: str,
        is_bot: bool = False,
        thread_id_in: Optional[str] = None,
        service_url: str = "",
        **kwargs,
    ) -> "MessageEnvelope":
        """Create a MessageEnvelope from a Microsoft Teams Bot Framework Activity.

        Args:
            team_id: Teams team ID (from ``channelData.team.id``).
            channel_id: Teams channel ID (from ``channelData.teamsChannelId``
                or ``conversation.id`` for DMs).
            sender_id: Sender's AAD object ID (``from.aadObjectId``) or
                ``from.id``.
            sender_name: Sender's display name (``from.name``).
            text: Message text (may include HTML entities from Teams).
            message_id: Activity ID (``activity.id``).
            is_bot: Whether the sender is a bot (``from.role == "bot"``).
            thread_id_in: Conversation thread ID for threaded replies.
            service_url: Bot Framework service URL from the Activity (used
                for outbound replies).
            **kwargs: Additional metadata to store.

        Returns:
            MessageEnvelope instance.
        """
        return cls(
            channel="teams",
            channel_message_id=message_id,
            sender_id=sender_id,
            sender_name=sender_name,
            content=cls.normalize_text(text),
            thread_id=thread_id_in or channel_id,
            conversation_id=f"{team_id}:{channel_id}",
            sender_is_bot=is_bot,
            metadata={
                "team_id": team_id,
                "channel_id": channel_id,
                "thread_id": thread_id_in,
                "service_url": service_url,
                **kwargs,
            },
        )

    @classmethod
    def from_signal(
        cls,
        phone_number: str,
        sender_name: str,
        text: str,
        message_id: str,
        is_group: bool = False,
        group_id: Optional[str] = None,
        is_bot: bool = False,
        **kwargs,
    ) -> "MessageEnvelope":
        """Create a MessageEnvelope from a Signal inbound message.

        Args:
            phone_number: Sender's E.164 phone number (``+15551234567``).
            sender_name: Sender's Signal display name or phone number.
            text: Message text.
            message_id: signal-cli message timestamp (used as unique ID).
            is_group: Whether the message was sent to a group.
            group_id: Signal group ID when ``is_group`` is True.
            is_bot: Whether the sender is a bot (always False for Signal).
            **kwargs: Additional metadata to store.

        Returns:
            MessageEnvelope instance.
        """
        conversation_id = group_id if is_group and group_id else phone_number
        return cls(
            channel="signal",
            channel_message_id=message_id,
            sender_id=phone_number,
            sender_name=sender_name,
            content=cls.normalize_text(text),
            thread_id=conversation_id,
            conversation_id=conversation_id,
            sender_is_bot=is_bot,
            metadata={
                "phone_number": phone_number,
                "is_group": is_group,
                "group_id": group_id,
                **kwargs,
            },
        )

    @classmethod
    def from_matrix(
        cls,
        room_id: str,
        sender_id: str,
        sender_name: str,
        text: str,
        event_id: str,
        is_direct: bool = False,
        is_bot: bool = False,
        **kwargs,
    ) -> "MessageEnvelope":
        """Create a MessageEnvelope from a Matrix m.room.message event.

        Args:
            room_id: Matrix room ID (``!roomId:homeserver``).
            sender_id: Sender's full Matrix user ID (``@user:homeserver``).
            sender_name: Sender's display name or user ID.
            text: Message body text.
            event_id: Matrix event ID (globally unique, ``$eventId:homeserver``).
            is_direct: Whether the room is a direct message room.
            is_bot: Whether the sender is a bot.
            **kwargs: Additional metadata to store.

        Returns:
            MessageEnvelope instance.
        """
        # Extract homeserver domain from sender_id (@user:homeserver → homeserver)
        homeserver = sender_id.split(":", 1)[1] if ":" in sender_id else ""
        return cls(
            channel="matrix",
            channel_message_id=event_id,
            sender_id=sender_id,
            sender_name=sender_name,
            content=cls.normalize_text(text),
            thread_id=room_id,
            conversation_id=room_id,
            sender_is_bot=is_bot,
            metadata={
                "room_id": room_id,
                "sender_id": sender_id,
                "homeserver": homeserver,
                "is_direct": is_direct,
                **kwargs,
            },
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
