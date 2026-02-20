"""Telegram channel adapter for Arcturus gateway.

Provides send/receive functionality for Telegram via the Bot API.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

from channels.base import ChannelAdapter

# Load .env file if it exists
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


class TelegramAdapter(ChannelAdapter):
    """Telegram channel adapter.

    Integrates with Telegram Bot API to send and receive messages.
    Supports text, media, and inline keyboards.
    """

    TELEGRAM_API_URL = "https://api.telegram.org/bot"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Telegram adapter.

        Args:
            config: Dict containing 'token' (Telegram Bot API token).
                   If not provided, reads from TELEGRAM_TOKEN env var.
        """
        super().__init__("telegram", config)
        self.token = self.config.get("token") if config else None
        if not self.token:
            self.token = os.getenv("TELEGRAM_TOKEN", "")
        self.bot_name = self.config.get("bot_name", "arcturus_bot") if config else "arcturus_bot"
        self.client = None

    async def initialize(self) -> None:
        """Initialize the Telegram adapter.

        Creates an async HTTP client for communicating with Telegram Bot API.
        """
        self.client = httpx.AsyncClient(timeout=30.0)

    async def shutdown(self) -> None:
        """Gracefully shutdown the Telegram adapter."""
        if self.client:
            await self.client.aclose()

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> Dict[str, Any]:
        """Send a message to a Telegram chat.

        Args:
            recipient_id: Telegram chat_id (user or group)
            content: Message text
            **kwargs: Options like parse_mode, reply_markup, etc.

        Returns:
            Dict with message_id, timestamp, and response metadata
        """
        if not self.client:
            await self.initialize()

        url = f"{self.TELEGRAM_API_URL}{self.token}/sendMessage"
        # Default to MarkdownV2 so the formatter's output renders correctly.
        # Callers can override by passing parse_mode=None or another value.
        if "parse_mode" not in kwargs:
            kwargs["parse_mode"] = "MarkdownV2"
        payload = {
            "chat_id": recipient_id,
            "text": content,
            **kwargs,
        }

        try:
            response = await self.client.post(url, json=payload)
            data = response.json()

            if data.get("ok"):
                message = data.get("result", {})
                return {
                    "message_id": message.get("message_id"),
                    "timestamp": datetime.fromtimestamp(message.get("date", 0)).isoformat(),
                    "channel": "telegram",
                    "recipient_id": recipient_id,
                    "success": True,
                }
            else:
                return {
                    "message_id": None,
                    "timestamp": datetime.now().isoformat(),
                    "channel": "telegram",
                    "recipient_id": recipient_id,
                    "success": False,
                    "error": data.get("description", "Unknown error"),
                }
        except httpx.RequestError as e:
            return {
                "message_id": None,
                "timestamp": datetime.now().isoformat(),
                "channel": "telegram",
                "recipient_id": recipient_id,
                "success": False,
                "error": str(e),
            }
