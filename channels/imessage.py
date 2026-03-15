"""iMessage/BlueBubbles channel adapter for Arcturus gateway.

Provides outbound messaging via a local BlueBubbles server REST API and
inbound webhook signature verification (HMAC-SHA256) for messages
BlueBubbles forwards to POST /api/nexus/imessage/inbound.

Architecture:
  Outbound:  iMessageAdapter.send_message() → POST http://localhost:1234/api/v1/message/text
  Inbound:   BlueBubbles POSTs to FastAPI → routers/nexus.py → MessageEnvelope.from_imessage()
  Formatter: plain text (iMessage renders rich text client-side; we send plain)

BlueBubbles is an open-source macOS server that bridges iMessage to a REST API.
It must be running on a Mac with an active Apple ID signed into Messages.app.

Setup:
  1. Install BlueBubbles (https://bluebubbles.app) on a Mac.
  2. Set a server password in BlueBubbles settings.
  3. Configure the webhook URL in BlueBubbles → Webhooks → Add webhook:
       http://<your-host>:8000/api/nexus/imessage/inbound
  4. Set BLUEBUBBLES_URL and BLUEBUBBLES_PASSWORD in .env.

Environment variables:
  BLUEBUBBLES_URL       Base URL of the BlueBubbles server (default: http://localhost:1234)
  BLUEBUBBLES_PASSWORD  BlueBubbles server password (used as query param for auth)
  BLUEBUBBLES_WEBHOOK_SECRET  Shared HMAC-SHA256 secret for inbound webhook auth (optional)
"""

import hashlib
import hmac
import os
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


class iMessageAdapter(ChannelAdapter):
    """iMessage channel adapter using the BlueBubbles REST API bridge.

    Communicates with a local BlueBubbles server process to send and receive
    iMessages.  BlueBubbles maintains the Apple ID / Messages.app session on
    a dedicated Mac.

    Outbound:  POST {bluebubbles_url}/api/v1/message/text?password={password}
    Inbound:   handled by routers/nexus.py POST /nexus/imessage/inbound
    Formatter: plain text

    Authentication:
        BlueBubbles uses a server password as a query parameter on all API calls.
        Inbound webhooks are optionally signed with HMAC-SHA256 in the
        ``X-BB-Secret`` header using a shared webhook secret.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialise the iMessage adapter.

        Args:
            config: Dict optionally containing:
                - ``bluebubbles_url``: Base URL of the BlueBubbles server.
                - ``password``: BlueBubbles server password.
                - ``webhook_secret``: Shared HMAC-SHA256 secret for inbound auth.
                Falls back to env vars if not supplied.
        """
        super().__init__("imessage", config)
        cfg = config or {}
        self.bluebubbles_url = (
            cfg.get("bluebubbles_url") or os.getenv("BLUEBUBBLES_URL", "http://localhost:1234")
        ).rstrip("/")
        self.password = cfg.get("password") or os.getenv("BLUEBUBBLES_PASSWORD", "")
        self.webhook_secret = (
            cfg.get("webhook_secret") or os.getenv("BLUEBUBBLES_WEBHOOK_SECRET", "")
        )
        self.client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Create the async HTTP client."""
        self.client = httpx.AsyncClient(timeout=30.0)

    async def shutdown(self) -> None:
        """Gracefully close the HTTP client."""
        if self.client:
            await self.client.aclose()

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> dict[str, Any]:
        """Send a message to an iMessage address via BlueBubbles.

        Args:
            recipient_id: iMessage address — phone number (``+15551234567``),
                          Apple ID email (``user@example.com``), or
                          group chat GUID (``chat{guid}``).
            content: Message text (plain text; iMessage client renders as-is).
            **kwargs: Reserved for future media/effect support.

        Returns:
            Dict with ``message_id``, ``timestamp``, ``channel``,
            ``recipient_id``, ``success``, and ``error`` on failure.
        """
        if not self.client:
            await self.initialize()

        media_attachments = kwargs.pop("attachments", [])
        # Append attachment URLs as text links (BlueBubbles binary upload not wired)
        if media_attachments:
            links = "\n".join(
                f"[{a.filename or a.media_type}]: {a.url}" for a in media_attachments
            )
            content = f"{content}\n\n{links}" if content else links

        url = f"{self.bluebubbles_url}/api/v1/message/text"
        params = {"password": self.password} if self.password else {}
        payload: dict[str, Any] = {
            "chatGuid": recipient_id,
            "tempGuid": f"temp-{datetime.utcnow().timestamp()}",
            "message": content,
            "method": "private-api",  # use Private API plugin for faster delivery if available
            **kwargs,
        }

        try:
            response = await self.client.post(url, params=params, json=payload)
            if response.status_code in (200, 201):
                data = response.json()
                # BlueBubbles returns { status: 200, data: { guid: "...", ... } }
                message_data = data.get("data", data)
                return {
                    "message_id": message_data.get("guid", ""),
                    "timestamp": message_data.get("dateCreated", datetime.utcnow().isoformat()),
                    "channel": "imessage",
                    "recipient_id": recipient_id,
                    "success": True,
                }
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get(
                        "message", f"HTTP {response.status_code}"
                    )
                except Exception:
                    error_msg = f"HTTP {response.status_code}"
                return {
                    "message_id": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "channel": "imessage",
                    "recipient_id": recipient_id,
                    "success": False,
                    "error": error_msg,
                }
        except httpx.RequestError as exc:
            return {
                "message_id": None,
                "timestamp": datetime.utcnow().isoformat(),
                "channel": "imessage",
                "recipient_id": recipient_id,
                "success": False,
                "error": str(exc),
            }

    @staticmethod
    def verify_signature(body: bytes, signature: str, secret: str) -> bool:
        """Verify an inbound HMAC-SHA256 signature from BlueBubbles.

        BlueBubbles can be configured to send an ``X-BB-Secret`` header
        containing an HMAC-SHA256 hex digest of the raw JSON body.

        Args:
            body: Raw request body bytes.
            signature: Value of the ``X-BB-Secret`` header (hex digest).
            secret: Shared webhook secret configured in BlueBubbles and .env.

        Returns:
            True if the signature is valid, or if secret is empty (dev mode).
            False on invalid signature or malformed inputs.
        """
        if not secret:
            return True  # Dev mode: no secret configured, allow all
        computed = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        try:
            return hmac.compare_digest(computed, signature)
        except (TypeError, ValueError):
            return False
