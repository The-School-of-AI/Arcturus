"""Telegram channel adapter for Arcturus gateway.

Provides send/receive functionality for Telegram via the Bot API.

Inbound messages are received via a long-poll ``getUpdates`` loop started in
``initialize()`` and cancelled in ``shutdown()``.  No webhook or sidecar is
needed — the loop runs entirely inside the FastAPI event loop.
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import httpx
from dotenv import load_dotenv

from channels.base import ChannelAdapter
from gateway.envelope import MessageEnvelope

logger = logging.getLogger(__name__)

# Load .env file if it exists
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


class TelegramAdapter(ChannelAdapter):
    """Telegram channel adapter.

    Integrates with Telegram Bot API to send and receive messages.
    Supports text, media, and inline keyboards.

    Inbound messages are received via a long-poll ``getUpdates`` loop that
    starts when ``initialize()`` is called.  Each update is converted to a
    ``MessageEnvelope`` and dispatched through ``_bus_callback`` (set by the
    MessageBus via ``set_bus_callback()``).
    """

    TELEGRAM_API_URL = "https://api.telegram.org/bot"
    _LONG_POLL_TIMEOUT = 30  # seconds per getUpdates call

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
        self.client: Optional[httpx.AsyncClient] = None
        self._poll_task: Optional[asyncio.Task] = None
        self._bus_callback: Optional[Callable] = None
        self._update_offset: int = 0

    def set_bus_callback(self, callback: Callable) -> None:
        """Register the MessageBus roundtrip callback for inbound dispatch."""
        self._bus_callback = callback

    async def initialize(self) -> None:
        """Initialize the Telegram adapter and start the getUpdates polling loop."""
        self.client = httpx.AsyncClient(timeout=self._LONG_POLL_TIMEOUT + 10.0)
        if not self.token:
            logger.warning("TelegramAdapter: TELEGRAM_TOKEN not set — inbound polling disabled")
            return
        # Start the long-poll loop as a background task
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("TelegramAdapter: getUpdates polling loop started")

    async def shutdown(self) -> None:
        """Gracefully shutdown the Telegram adapter."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self.client:
            await self.client.aclose()

    # ------------------------------------------------------------------
    # Inbound polling loop
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Long-poll Telegram getUpdates and dispatch each message to the bus."""
        base = f"{self.TELEGRAM_API_URL}{self.token}"
        backoff = 1.0
        while True:
            try:
                resp = await self.client.get(
                    f"{base}/getUpdates",
                    params={
                        "offset": self._update_offset,
                        "timeout": self._LONG_POLL_TIMEOUT,
                        "allowed_updates": ["message"],
                    },
                )
                data = resp.json()
                if not data.get("ok"):
                    logger.warning("TelegramAdapter poll error: %s", data)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                    continue

                backoff = 1.0
                updates = data.get("result", [])
                for update in updates:
                    self._update_offset = update["update_id"] + 1
                    await self._handle_update(update)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("TelegramAdapter poll exception: %s", exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    async def _handle_update(self, update: Dict[str, Any]) -> None:
        """Convert a Telegram update to a MessageEnvelope and roundtrip it."""
        message = update.get("message")
        if not message:
            return  # skip non-message updates (edited_message, etc.)

        text = message.get("text", "").strip()
        if not text:
            return  # skip media-only messages

        chat = message.get("chat", {})
        sender = message.get("from", {})
        chat_id = str(chat.get("id", ""))
        sender_id = str(sender.get("id", chat_id))
        sender_name = sender.get("first_name") or sender.get("username") or "Telegram User"
        message_id = str(message.get("message_id", ""))

        envelope = MessageEnvelope.from_telegram(
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            text=text,
            message_id=message_id,
        )

        if self._bus_callback:
            try:
                print(f"[TELEGRAM] Dispatching to bus: chat_id={chat_id} sender={sender_id} text='{text[:60]}'")
                result = await self._bus_callback(envelope)
                print(f"[TELEGRAM] Bus roundtrip returned: success={getattr(result, 'success', '?')} error={getattr(result, 'error', None)}")
            except Exception as exc:
                print(f"[TELEGRAM] Bus roundtrip EXCEPTION: {exc}")
                logger.error("TelegramAdapter: bus roundtrip failed: %s", exc, exc_info=True)
        else:
            print("[TELEGRAM] WARNING: no bus callback set — message dropped")
            logger.warning("TelegramAdapter: no bus callback set — message dropped")

    async def send_typing_indicator(self, recipient_id: str, **kwargs) -> None:
        """Send a 'typing' chat action to a Telegram chat."""
        if not self.client:
            return
        url = f"{self.TELEGRAM_API_URL}{self.token}/sendChatAction"
        try:
            await self.client.post(url, json={"chat_id": recipient_id, "action": "typing"})
        except Exception:
            pass  # typing is cosmetic — never fail the pipeline

    # ------------------------------------------------------------------
    # Outbound
    # ------------------------------------------------------------------

    # Telegram's hard limit for a single message
    _MAX_MSG_LEN = 4096

    @staticmethod
    def _split_message(text: str, limit: int = 4096) -> list[str]:
        """Split *text* into chunks that fit within Telegram's message limit.

        Tries to break on newlines first, then on spaces, to avoid mid-word cuts.
        """
        if len(text) <= limit:
            return [text]

        chunks: list[str] = []
        while text:
            if len(text) <= limit:
                chunks.append(text)
                break
            # Try to break at the last newline within the limit
            cut = text.rfind("\n", 0, limit)
            if cut <= 0:
                # No newline — try a space
                cut = text.rfind(" ", 0, limit)
            if cut <= 0:
                # No space either — hard cut
                cut = limit
            chunks.append(text[:cut])
            text = text[cut:].lstrip("\n")
        return chunks

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> Dict[str, Any]:
        """Send a message to a Telegram chat.

        Long messages (>4096 chars) are automatically split into multiple
        sequential messages so they are never rejected by the Telegram API.

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
        # Do NOT default to MarkdownV2 — it rejects unescaped special chars
        # (., !, -, etc.) which are common in agent output.  Callers that
        # pre-escape their text can pass parse_mode="MarkdownV2" explicitly.

        media_attachments = kwargs.pop("attachments", [])
        chunks = self._split_message(content, self._MAX_MSG_LEN)
        last_result: Dict[str, Any] = {}

        for i, chunk in enumerate(chunks):
            payload = {
                "chat_id": recipient_id,
                "text": chunk,
                **kwargs,
            }

            try:
                response = await self.client.post(url, json=payload)
                data = response.json()

                if data.get("ok"):
                    message = data.get("result", {})
                    last_result = {
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
                        "failed_chunk": i + 1,
                    }
            except httpx.RequestError as e:
                return {
                    "message_id": None,
                    "timestamp": datetime.now().isoformat(),
                    "channel": "telegram",
                    "recipient_id": recipient_id,
                    "success": False,
                    "error": str(e),
                    "failed_chunk": i + 1,
                }

        # Send any media attachments after text
        for att in media_attachments:
            await self._send_attachment(recipient_id, att)

        return last_result

    async def _send_attachment(self, chat_id: str, att) -> None:
        """Send a single media attachment via the appropriate Telegram API."""
        _ENDPOINTS = {
            "image": ("sendPhoto", "photo"),
            "video": ("sendVideo", "video"),
            "audio": ("sendAudio", "audio"),
            "document": ("sendDocument", "document"),
        }
        method, key = _ENDPOINTS.get(att.media_type, ("sendDocument", "document"))
        url = f"{self.TELEGRAM_API_URL}{self.token}/{method}"
        try:
            await self.client.post(url, json={"chat_id": chat_id, key: att.url})
        except Exception:
            pass  # best-effort media delivery
