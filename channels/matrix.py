"""Matrix channel adapter for Arcturus gateway.

Provides outbound messaging via the Matrix Client-Server API v3 and
inbound message delivery via an internal polling loop (no webhook/sidecar needed).

Architecture:
  Outbound:  MatrixAdapter.send_message() →
             PUT {homeserver}/_matrix/client/v3/rooms/{roomId}/send/m.room.message/{txnId}
  Inbound:   MatrixAdapter._sync_loop() polls GET /_matrix/client/v3/sync every N seconds,
             dispatches new m.room.message events to the bus via set_bus_callback()
  Formatter: MessageFormatter._format_plain() (Matrix clients render Markdown client-side)

No sidecar process is required — the adapter manages the sync poll loop internally.
The poll loop is started in initialize() and cancelled in shutdown().

Authentication:
  Matrix uses a Bearer access token obtained from the homeserver
  (via /login or an admin token for bot accounts).

Setup:
  1. Create a Matrix account for the bot on any homeserver.
  2. Obtain an access token:
       POST {homeserver}/_matrix/client/v3/login
         {"type": "m.login.password", "user": "@bot:matrix.org", "password": "..."}
  3. Invite the bot to rooms where it should respond.
  4. Set MATRIX_HOMESERVER_URL, MATRIX_USER_ID, MATRIX_ACCESS_TOKEN in .env.

Environment variables:
  MATRIX_HOMESERVER_URL   Homeserver base URL (e.g. https://matrix.org)
  MATRIX_USER_ID          Bot's full Matrix user ID (@bot:matrix.org)
  MATRIX_ACCESS_TOKEN     Bot's access token (Bearer auth)
  MATRIX_SYNC_INTERVAL    Seconds between sync polls (default: 2.0)
"""

import asyncio
import logging
import os
import time
from collections.abc import Callable, Coroutine
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from channels.base import ChannelAdapter

# Load .env file if it exists
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

logger = logging.getLogger(__name__)

_CS_API = "/_matrix/client/v3"


class MatrixAdapter(ChannelAdapter):
    """Matrix channel adapter using the Matrix Client-Server API v3.

    Communicates directly with a Matrix homeserver to send and receive
    messages.  The adapter maintains an internal sync polling loop so no
    external sidecar process is required.

    Outbound:  PUT {homeserver}/_matrix/client/v3/rooms/{roomId}/send/m.room.message/{txnId}
    Inbound:   internal polling via GET /_matrix/client/v3/sync
    Formatter: plain text (Matrix clients render Markdown natively)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialise the Matrix adapter.

        Args:
            config: Dict optionally containing:
                - ``homeserver_url``: Homeserver base URL.
                - ``user_id``: Bot's full Matrix user ID.
                - ``access_token``: Bot's Bearer access token.
                - ``sync_interval``: Polling interval in seconds (default 2.0).
                Falls back to env vars if not supplied.
        """
        super().__init__("matrix", config)
        cfg = config or {}
        self.homeserver_url = (
            cfg.get("homeserver_url") or os.getenv("MATRIX_HOMESERVER_URL", "https://matrix.org")
        ).rstrip("/")
        self.user_id = cfg.get("user_id") or os.getenv("MATRIX_USER_ID", "")
        self.access_token = cfg.get("access_token") or os.getenv("MATRIX_ACCESS_TOKEN", "")
        self.sync_interval = float(
            cfg.get("sync_interval") or os.getenv("MATRIX_SYNC_INTERVAL", "2.0")
        )
        self.client: httpx.AsyncClient | None = None
        self._poll_task: asyncio.Task | None = None
        self._bus_callback: Callable[..., Coroutine] | None = None
        # Persist since_token across restarts so we never replay old history
        self._since_token_path = Path(__file__).parent.parent / "memory" / "matrix_since_token.txt"
        self._since_token: str | None = self._load_since_token()

    def _load_since_token(self) -> str | None:
        """Load a persisted since_token from disk (survives restarts)."""
        try:
            if self._since_token_path.exists():
                token = self._since_token_path.read_text().strip()
                if token:
                    logger.info("Matrix: loaded since_token from disk")
                    return token
        except Exception:
            pass
        return None

    def _save_since_token(self, token: str) -> None:
        """Persist the since_token to disk so restarts don't replay history."""
        try:
            self._since_token_path.parent.mkdir(parents=True, exist_ok=True)
            self._since_token_path.write_text(token)
        except Exception as exc:
            logger.debug("Matrix: could not save since_token: %s", exc)

    def set_bus_callback(self, callback: Callable[..., Coroutine]) -> None:
        """Register the async callback invoked for each inbound message.

        Args:
            callback: An async callable (e.g. ``bus.roundtrip``) that accepts
                      a ``MessageEnvelope`` and processes it through the bus.
        """
        self._bus_callback = callback

    async def initialize(self) -> None:
        """Create the HTTP client and start the background sync loop."""
        self.client = httpx.AsyncClient(timeout=35.0)
        if self.access_token and self.user_id:
            self._poll_task = asyncio.create_task(self._sync_loop())
            logger.info(
                "Matrix sync loop started (user=%s, homeserver=%s, interval=%.1fs)",
                self.user_id,
                self.homeserver_url,
                self.sync_interval,
            )
        else:
            logger.warning(
                "MATRIX_ACCESS_TOKEN or MATRIX_USER_ID not set — inbound polling disabled"
            )

    async def shutdown(self) -> None:
        """Cancel the sync loop and close the HTTP client."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        if self.client:
            await self.client.aclose()

    async def send_typing_indicator(self, recipient_id: str, **kwargs) -> None:
        """Send a typing indicator to a Matrix room."""
        if not self.client or not self.access_token or not self.user_id:
            return
        url = (
            f"{self.homeserver_url}{_CS_API}"
            f"/rooms/{recipient_id}/typing/{self.user_id}"
        )
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            await self.client.put(
                url,
                json={"typing": True, "timeout": 30000},
                headers=headers,
            )
        except Exception:
            pass  # typing is cosmetic — never fail the pipeline

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> dict[str, Any]:
        """Send a text message to a Matrix room.

        Args:
            recipient_id: Matrix room ID (``!roomId:homeserver``).
            content: Message text (plain text; clients render Markdown).
            **kwargs: Reserved for future m.room.message content extensions.

        Returns:
            Dict with ``message_id``, ``timestamp``, ``channel``,
            ``recipient_id``, ``success``, and ``error`` on failure.
        """
        if not self.client:
            await self.initialize()

        if not self.access_token:
            return {
                "message_id": None,
                "timestamp": datetime.utcnow().isoformat(),
                "channel": "matrix",
                "recipient_id": recipient_id,
                "success": False,
                "error": "MATRIX_ACCESS_TOKEN not configured",
            }

        # Unique transaction ID prevents duplicate sends on retry
        txn_id = f"arcturus-{int(time.time() * 1000)}"
        url = (
            f"{self.homeserver_url}{_CS_API}"
            f"/rooms/{recipient_id}/send/m.room.message/{txn_id}"
        )
        media_attachments = kwargs.pop("attachments", [])
        body: dict[str, Any] = {"msgtype": "m.text", "body": content, **kwargs}
        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            response = await self.client.put(url, json=body, headers=headers)
            if response.status_code in (200, 201):
                data = response.json()
                result = {
                    "message_id": data.get("event_id", ""),
                    "timestamp": datetime.utcnow().isoformat(),
                    "channel": "matrix",
                    "recipient_id": recipient_id,
                    "success": True,
                }
            else:
                try:
                    err_data = response.json()
                    error_msg = err_data.get("error") or f"HTTP {response.status_code}"
                except Exception:
                    error_msg = f"HTTP {response.status_code}"
                logger.error("Matrix send_message failed: %s (room=%s)", error_msg, recipient_id)
                return {
                    "message_id": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "channel": "matrix",
                    "recipient_id": recipient_id,
                    "success": False,
                    "error": error_msg,
                }
        except httpx.RequestError as exc:
            return {
                "message_id": None,
                "timestamp": datetime.utcnow().isoformat(),
                "channel": "matrix",
                "recipient_id": recipient_id,
                "success": False,
                "error": str(exc),
            }

        # Send any media attachments as separate Matrix events
        for att in media_attachments:
            await self._send_attachment(recipient_id, att)

        return result

    _MATRIX_MSGTYPES = {"image": "m.image", "video": "m.video", "audio": "m.audio"}

    async def _send_attachment(self, room_id: str, att) -> None:
        """Send a single media attachment as a Matrix room event."""
        msgtype = self._MATRIX_MSGTYPES.get(att.media_type, "m.file")
        txn_id = f"arcturus-media-{int(time.time() * 1000)}"
        url = (
            f"{self.homeserver_url}{_CS_API}"
            f"/rooms/{room_id}/send/m.room.message/{txn_id}"
        )
        body = {
            "msgtype": msgtype,
            "body": att.filename or "attachment",
            "url": att.url,
            "info": {"mimetype": att.mime_type or "application/octet-stream"},
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            await self.client.put(url, json=body, headers=headers)
        except Exception:
            pass  # best-effort media delivery

    # ------------------------------------------------------------------
    # Internal sync loop
    # ------------------------------------------------------------------

    async def _sync_loop(self) -> None:
        """Background task: poll the Matrix /sync endpoint for new events."""
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("Matrix sync error: %s", exc)
            await asyncio.sleep(self.sync_interval)

    async def _poll_once(self) -> None:
        """Perform one Matrix /sync request and dispatch new messages."""
        if not self.client:
            return

        params: dict[str, Any] = {"timeout": 0}
        if self._since_token:
            params["since"] = self._since_token

        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"{self.homeserver_url}{_CS_API}/sync"

        response = await self.client.get(url, params=params, headers=headers, timeout=10.0)
        if response.status_code != 200:
            return

        data = response.json()
        new_token = data.get("next_batch")
        if new_token and new_token != self._since_token:
            self._since_token = new_token
            self._save_since_token(new_token)

        # Walk joined rooms for new message events
        rooms = data.get("rooms", {}).get("join", {})
        for room_id, room_data in rooms.items():
            events = room_data.get("timeline", {}).get("events", [])
            for event in events:
                if event.get("type") == "m.room.message":
                    await self._dispatch(room_id, event)

    async def _dispatch(self, room_id: str, event: dict[str, Any]) -> None:
        """Process a single Matrix m.room.message event."""
        sender = event.get("sender", "")

        # Skip messages sent by the bot itself to prevent reply loops
        if sender == self.user_id:
            return

        # Skip server/system senders (e.g. @server:matrix.org automated messages)
        if sender.startswith("@server:") or sender.startswith("@_"):
            return

        content = event.get("content", {})
        # Only handle m.text messages (skip m.image, m.file, reactions, etc.)
        if content.get("msgtype") != "m.text":
            return

        text = (content.get("body") or "").strip()
        if not text:
            return

        event_id = event.get("event_id", "")
        # Extract display name — prefer content.displayname, fall back to sender
        sender_name = content.get("displayname") or sender

        if not self._bus_callback:
            logger.debug("Matrix: no bus_callback set, dropping event %s", event_id)
            return

        from gateway.envelope import MessageEnvelope

        envelope = MessageEnvelope.from_matrix(
            room_id=room_id,
            sender_id=sender,
            sender_name=sender_name,
            text=text,
            event_id=event_id,
        )
        try:
            await self._bus_callback(envelope)
        except Exception as exc:
            logger.error("Matrix dispatch error for event %s: %s", event_id, exc)
