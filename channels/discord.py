"""Discord channel adapter for Arcturus gateway.

Provides outbound messaging via the Discord REST API (POST /channels/{id}/messages)
and inbound webhook signature verification using Ed25519 (Discord Interactions API).
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from channels.base import ChannelAdapter

# Load .env file if it exists (mirrors Slack/Telegram pattern)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


class DiscordAdapter(ChannelAdapter):
    """Discord channel adapter.

    Integrates with the Discord REST API to send messages to text channels.
    Supports inbound webhook signature verification (Ed25519) for the
    Discord Interactions endpoint.

    Outbound:  POST https://discord.com/api/v10/channels/{channel_id}/messages
    Inbound:   handled by routers/nexus.py POST /nexus/discord/events
    Formatter: MessageFormatter._format_discord() → Discord markdown
    """

    DISCORD_API_BASE = "https://discord.com/api/v10"

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialise the Discord adapter.

        Args:
            config: Dict containing 'token' (Bot token, ``Bot …``) and
                    optionally 'public_key' (Ed25519 public key for signature
                    verification).  If not provided, reads from
                    ``DISCORD_BOT_TOKEN`` / ``DISCORD_PUBLIC_KEY`` env vars.
        """
        super().__init__("discord", config)
        cfg = config or {}
        raw_token = cfg.get("token") or os.getenv("DISCORD_BOT_TOKEN", "")
        # Ensure the token is prefixed with "Bot " for the Authorization header
        if raw_token and not raw_token.startswith("Bot "):
            self.token = f"Bot {raw_token}"
        else:
            self.token = raw_token
        self.public_key = cfg.get("public_key") or os.getenv("DISCORD_PUBLIC_KEY", "")
        self.client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Create the async HTTP client."""
        self.client = httpx.AsyncClient(timeout=30.0)

    async def shutdown(self) -> None:
        """Gracefully close the HTTP client."""
        if self.client:
            await self.client.aclose()

    async def send_typing_indicator(self, recipient_id: str, **kwargs) -> None:
        """Trigger a typing indicator in a Discord channel (lasts ~10 seconds)."""
        if not self.client:
            return
        url = f"{self.DISCORD_API_BASE}/channels/{recipient_id}/typing"
        headers = {"Authorization": self.token}
        try:
            await self.client.post(url, headers=headers)
        except Exception:
            pass  # typing is cosmetic — never fail the pipeline

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> dict[str, Any]:
        """Send a message to a Discord text channel.

        Args:
            recipient_id: Discord channel ID (snowflake string).
            content: Message text, pre-formatted as Discord markdown
                     by MessageFormatter.
            **kwargs: Additional Discord API fields (``embeds``, ``tts``,
                      ``message_reference`` for replies, etc.)

        Returns:
            Dict with ``message_id`` (Discord snowflake), ``timestamp``,
            ``channel``, ``recipient_id``, ``success``, and ``error`` on failure.
        """
        if not self.client:
            await self.initialize()

        url = f"{self.DISCORD_API_BASE}/channels/{recipient_id}/messages"
        headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
        }
        # Discord has a 2000-character limit per message; truncate gracefully
        if len(content) > 2000:
            content = content[:1997] + "..."

        media_attachments = kwargs.pop("attachments", [])
        payload: dict[str, Any] = {"content": content, **kwargs}

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            if response.status_code in (200, 201):
                data = response.json()
                result = {
                    "message_id": data.get("id", ""),
                    "timestamp": data.get("timestamp", datetime.utcnow().isoformat()),
                    "channel": "discord",
                    "recipient_id": recipient_id,
                    "success": True,
                }
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", f"HTTP {response.status_code}")
                except Exception:
                    error_msg = f"HTTP {response.status_code}"
                return {
                    "message_id": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "channel": "discord",
                    "recipient_id": recipient_id,
                    "success": False,
                    "error": error_msg,
                }
        except httpx.RequestError as exc:
            return {
                "message_id": None,
                "timestamp": datetime.utcnow().isoformat(),
                "channel": "discord",
                "recipient_id": recipient_id,
                "success": False,
                "error": str(exc),
            }

        # Send any media attachments as embeds after text
        for att in media_attachments:
            await self._send_attachment(recipient_id, att)

        return result

    async def _send_attachment(self, channel_id: str, att) -> None:
        """Send a single media attachment as a Discord embed."""
        url = f"{self.DISCORD_API_BASE}/channels/{channel_id}/messages"
        headers = {"Authorization": self.token, "Content-Type": "application/json"}
        embed: dict[str, Any] = {"url": att.url}
        if att.media_type == "image":
            embed["image"] = {"url": att.url}
        else:
            embed["description"] = f"[{att.filename or 'file'}]({att.url})"
        try:
            await self.client.post(url, json={"embeds": [embed]}, headers=headers)
        except Exception:
            pass  # best-effort media delivery

    @staticmethod
    def verify_signature(body: bytes, timestamp: str, signature: str, public_key: str) -> bool:
        """Verify a Discord webhook signature using Ed25519.

        Discord signs every inbound Interactions request with Ed25519 over
        ``timestamp + raw_body`` using the application's public key.

        Args:
            body: Raw request body bytes.
            timestamp: Value of the ``X-Signature-Timestamp`` header.
            signature: Value of the ``X-Signature-Ed25519`` header (hex-encoded).
            public_key: Discord application public key (hex-encoded).

        Returns:
            True if the signature is valid, False otherwise.
            Returns False (not raises) if the ``nacl`` library is unavailable.
        """
        try:
            from nacl.signing import VerifyKey

            vk = VerifyKey(bytes.fromhex(public_key))
            message = timestamp.encode() + body
            vk.verify(message, bytes.fromhex(signature))
            return True
        except Exception:
            # Covers BadSignatureError, ValueError (bad hex), ImportError (no nacl)
            return False
