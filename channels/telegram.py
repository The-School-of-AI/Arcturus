"""Telegram channel adapter for Arcturus gateway.

Provides send/receive functionality for Telegram via the Bot API.

Inbound messages are received via a long-poll ``getUpdates`` loop started in
``initialize()`` and cancelled in ``shutdown()``.  No webhook or sidecar is
needed — the loop runs entirely inside the FastAPI event loop.
"""

import asyncio
import logging
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

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

    def __init__(self, config: dict[str, Any] | None = None):
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
        self.client: httpx.AsyncClient | None = None
        self._poll_task: asyncio.Task | None = None
        self._bus_callback: Callable | None = None
        self._update_offset: int = 0
        # Per-user interaction mode selected via inline keyboard / slash commands
        self._user_modes: dict[str, str] = {}

        # Mode definitions for the inline keyboard
        self.MODES = {
            "simple":   {"label": "Simple Query (Gemma)", "icon": "🔍"},
            "complex":  {"label": "Complex Research (Gemini)", "icon": "🧠"},
            "runs":     {"label": "RUNS (Multi-Agent)", "icon": "📊"},
            "slides":   {"label": "Presentations (Forge)", "icon": "📑"},
            "schedule": {"label": "Schedule (Cron)", "icon": "⏰"},
            "rag":      {"label": "RAG (Knowledge Base)", "icon": "📚"},
        }

    def set_bus_callback(self, callback: Callable) -> None:
        """Register the MessageBus roundtrip callback for inbound dispatch."""
        self._bus_callback = callback

    async def initialize(self) -> None:
        """Initialize the Telegram adapter and start the getUpdates polling loop."""
        self.client = httpx.AsyncClient(timeout=self._LONG_POLL_TIMEOUT + 10.0)
        if not self.token:
            logger.warning("TelegramAdapter: TELEGRAM_TOKEN not set — inbound polling disabled")
            return
        # Register bot commands with Telegram menu
        await self._set_my_commands()
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

        # Flush stale updates from before this server start.
        # Fetch with offset=-1 to get only the last update, then advance past it.
        try:
            resp = await self.client.get(
                f"{base}/getUpdates", params={"offset": -1, "timeout": 0}
            )
            data = resp.json()
            if data.get("ok"):
                stale = data.get("result", [])
                if stale:
                    self._update_offset = stale[-1]["update_id"] + 1
                    logger.info("TelegramAdapter: flushed %d stale update(s), offset now %d", len(stale), self._update_offset)
        except Exception as exc:
            logger.warning("TelegramAdapter: failed to flush stale updates: %s", exc)

        while True:
            try:
                resp = await self.client.get(
                    f"{base}/getUpdates",
                    params={
                        "offset": self._update_offset,
                        "timeout": self._LONG_POLL_TIMEOUT,
                        "allowed_updates": ["message", "callback_query"],
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

    async def _handle_update(self, update: dict[str, Any]) -> None:
        """Convert a Telegram update to a MessageEnvelope and roundtrip it."""
        # Handle inline keyboard button presses
        callback_query = update.get("callback_query")
        if callback_query:
            await self._handle_callback_query(callback_query)
            return

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

        # Handle slash commands that set mode (handled locally, not sent to agent)
        if text.startswith("/"):
            handled = await self._handle_slash_mode(chat_id, sender_id, text)
            if handled:
                return
            # If _handle_slash_mode returned False with a mode set (e.g. "/simple What is 2+2"),
            # strip the command prefix so the router sees clean query text.
            cmd = text.split()[0].lower()
            mode_commands = ("/simple", "/complex", "/run", "/runs", "/slides", "/forge", "/schedule", "/rag")
            if cmd in mode_commands:
                text = text[len(cmd):].strip()
                if not text:
                    return  # nothing left after stripping

        # Inject the user's selected mode into envelope metadata
        user_mode = self._user_modes.get(sender_id, "runs")  # default: full RUNS pipeline

        envelope = MessageEnvelope.from_telegram(
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            text=text,
            message_id=message_id,
            mode=user_mode,
        )

        if self._bus_callback:
            try:
                print(f"[TELEGRAM] mode={user_mode} | Dispatching: chat_id={chat_id} text='{text[:60]}'")
                result = await self._bus_callback(envelope)
                print(f"[TELEGRAM] Bus roundtrip returned: success={getattr(result, 'success', '?')}")
            except Exception as exc:
                print(f"[TELEGRAM] Bus roundtrip EXCEPTION: {exc}")
                logger.error("TelegramAdapter: bus roundtrip failed: %s", exc, exc_info=True)
        else:
            logger.warning("TelegramAdapter: no bus callback set — message dropped")

    # ------------------------------------------------------------------
    # Telegram interactive menu
    # ------------------------------------------------------------------

    async def _handle_callback_query(self, callback_query: dict[str, Any]) -> None:
        """Handle an inline keyboard button press."""
        cq_id = callback_query.get("id", "")
        data = callback_query.get("data", "")
        sender = callback_query.get("from", {})
        sender_id = str(sender.get("id", ""))
        message = callback_query.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))

        if data.startswith("mode:"):
            mode = data.split(":", 1)[1]
            if mode in self.MODES:
                self._user_modes[sender_id] = mode
                info = self.MODES[mode]
                print(f"[TELEGRAM] Button pressed: mode={mode} for sender={sender_id} (stored modes: {dict(self._user_modes)})")
                await self._answer_callback(cq_id, f"{info['icon']} {info['label']}")
                await self.send_message(
                    chat_id,
                    f"{info['icon']} Mode: {info['label']}\n\nSend your message now.",
                    parse_mode="",
                )
            else:
                await self._answer_callback(cq_id, "Unknown mode")
        elif data == "menu":
            await self._answer_callback(cq_id, "Menu")
            await self._send_menu(chat_id)
        else:
            await self._answer_callback(cq_id, "OK")

    async def _handle_slash_mode(self, chat_id: str, sender_id: str, text: str) -> bool:
        """Handle slash commands that set mode. Returns True if handled locally."""
        cmd = text.split()[0].lower()
        mode_map = {
            "/simple": "simple",
            "/complex": "complex",
            "/run": "runs",
            "/runs": "runs",
            "/slides": "slides",
            "/forge": "slides",
            "/schedule": "schedule",
            "/rag": "rag",
        }

        if cmd in ("/start", "/menu"):
            await self._send_menu(chat_id)
            return True

        if cmd in mode_map:
            mode = mode_map[cmd]
            self._user_modes[sender_id] = mode
            info = self.MODES[mode]
            # Check if there's a query after the command (e.g., "/simple what is 2+2")
            rest = text[len(cmd):].strip()
            if rest:
                # User sent command + query in one message — don't just set mode,
                # send the query through the pipeline with this mode
                return False  # let it fall through to normal processing
            await self.send_message(
                chat_id,
                f"{info['icon']} Mode: {info['label']}\n\nSend your message now.",
                parse_mode="",
            )
            return True

        # /help, /status, /clear — pass through to the agent router
        if cmd in ("/help", "/status", "/clear"):
            return False

        return False  # unknown command, let agent handle

    async def _send_menu(self, chat_id: str) -> None:
        """Send the main interactive menu with inline keyboard buttons."""
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🔍 Simple Query (Gemma)", "callback_data": "mode:simple"},
                    {"text": "🧠 Complex Research", "callback_data": "mode:complex"},
                ],
                [
                    {"text": "📊 RUNS (Multi-Agent)", "callback_data": "mode:runs"},
                    {"text": "📑 Presentations", "callback_data": "mode:slides"},
                ],
                [
                    {"text": "⏰ Schedule (Cron)", "callback_data": "mode:schedule"},
                    {"text": "📚 RAG (Knowledge)", "callback_data": "mode:rag"},
                ],
            ]
        }
        welcome = (
            "Welcome to Arcturus!\n\n"
            "Choose a mode, then send your message:\n\n"
            "🔍 Simple Query — Fast answers, local Gemma (free)\n"
            "🧠 Complex Research — Deep analysis via Gemini\n"
            "📊 RUNS — Full multi-agent research pipeline\n"
            "📑 Presentations — Create slides & decks\n"
            "⏰ Schedule — Set up recurring tasks\n"
            "📚 RAG — Search your knowledge base\n\n"
            "Or use: /simple /complex /run /slides /schedule /rag"
        )
        await self.send_message(chat_id, welcome, reply_markup=keyboard, parse_mode="")

    async def _answer_callback(self, callback_query_id: str, text: str = "") -> None:
        """Answer a callback query (dismiss the loading indicator)."""
        if not self.client:
            return
        url = f"{self.TELEGRAM_API_URL}{self.token}/answerCallbackQuery"
        try:
            await self.client.post(url, json={
                "callback_query_id": callback_query_id,
                "text": text,
            })
        except Exception:
            pass  # best-effort

    async def _set_my_commands(self) -> None:
        """Register bot commands with Telegram so they appear in the / menu."""
        if not self.client or not self.token:
            return
        url = f"{self.TELEGRAM_API_URL}{self.token}/setMyCommands"
        commands = [
            {"command": "start", "description": "Show interactive menu"},
            {"command": "menu", "description": "Show mode selection menu"},
            {"command": "simple", "description": "Simple Query (Gemma — free)"},
            {"command": "complex", "description": "Complex Research (Gemini)"},
            {"command": "run", "description": "RUNS multi-agent mode"},
            {"command": "slides", "description": "Create presentation (Forge)"},
            {"command": "schedule", "description": "Schedule a recurring task"},
            {"command": "rag", "description": "Search knowledge base (RAG)"},
            {"command": "help", "description": "Show help"},
            {"command": "status", "description": "Session status"},
        ]
        try:
            await self.client.post(url, json={"commands": commands})
            logger.info("TelegramAdapter: registered %d bot commands", len(commands))
        except Exception as exc:
            logger.warning("TelegramAdapter: setMyCommands failed: %s", exc)

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

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> dict[str, Any]:
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
        # Default to MarkdownV2 (formatter pre-escapes text).
        # If Telegram rejects the formatting, retry as plain text automatically.
        use_parse_mode = kwargs.pop("parse_mode", "MarkdownV2")

        media_attachments = kwargs.pop("attachments", [])
        chunks = self._split_message(content, self._MAX_MSG_LEN)
        last_result: dict[str, Any] = {}

        for i, chunk in enumerate(chunks):
            payload = {
                "chat_id": recipient_id,
                "text": chunk,
                "parse_mode": use_parse_mode,
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
                elif use_parse_mode and "parse" in data.get("description", "").lower():
                    # MarkdownV2 rejected — retry this chunk as plain text
                    logger.warning("Telegram rejected MarkdownV2 for chunk %d, retrying as plain text", i + 1)
                    payload.pop("parse_mode", None)
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

    async def send_document(self, chat_id: str, file_path: str, caption: str = "") -> dict[str, Any]:
        """Upload a local file to a Telegram chat via sendDocument (multipart)."""
        if not self.client:
            await self.initialize()
        url = f"{self.TELEGRAM_API_URL}{self.token}/sendDocument"
        from pathlib import Path as _P
        fp = _P(file_path)
        if not fp.exists():
            return {"success": False, "error": f"File not found: {file_path}"}
        try:
            files = {"document": (fp.name, fp.read_bytes())}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption[:1024]
            response = await self.client.post(url, data=data, files=files)
            resp = response.json()
            if resp.get("ok"):
                return {"success": True, "message_id": resp["result"]["message_id"]}
            return {"success": False, "error": resp.get("description", "Unknown error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

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
