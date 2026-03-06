"""WhatsApp channel adapter for Arcturus gateway.

Provides outbound messaging via a local Baileys Node.js bridge (POST /send)
and inbound webhook signature verification (HMAC-SHA256) for messages the
bridge forwards to POST /api/nexus/whatsapp/inbound.

Architecture:
  Outbound:  WhatsAppAdapter.send_message() → POST http://localhost:3001/send
  Inbound:   bridge POSTs to FastAPI → routers/nexus.py → MessageEnvelope.from_whatsapp()
  Formatter: MessageFormatter._format_plain() (WhatsApp renders *bold*/_italic_ natively)

The bridge process (whatsapp_bridge/index.js) must be running separately.
See whatsapp_bridge/README.md for setup instructions.
"""

import hashlib
import hmac
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

from channels.base import ChannelAdapter

# Load .env file if it exists (mirrors Slack/Telegram pattern)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


class WhatsAppAdapter(ChannelAdapter):
    """WhatsApp channel adapter using the Baileys Node.js bridge.

    Communicates with a local Baileys bridge process to send and receive
    WhatsApp messages.  The bridge maintains the WhatsApp Web session.

    Outbound:  POST {bridge_url}/send
    Inbound:   handled by routers/nexus.py POST /nexus/whatsapp/inbound
    Formatter: plain text (WhatsApp renders *bold*/_italic_ natively)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialise the WhatsApp adapter.

        Args:
            config: Dict optionally containing 'bridge_url' and 'bridge_secret'.
                    Falls back to WHATSAPP_BRIDGE_URL / WHATSAPP_BRIDGE_SECRET
                    env vars, then defaults.
        """
        super().__init__("whatsapp", config)
        cfg = config or {}
        self.bridge_url = (
            cfg.get("bridge_url") or os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3001")
        ).rstrip("/")
        self.bridge_secret = cfg.get("bridge_secret") or os.getenv("WHATSAPP_BRIDGE_SECRET", "")
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Create the async HTTP client."""
        self.client = httpx.AsyncClient(timeout=30.0)

    async def shutdown(self) -> None:
        """Gracefully close the HTTP client."""
        if self.client:
            await self.client.aclose()

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> Dict[str, Any]:
        """Send a message to a WhatsApp number via the Baileys bridge.

        Args:
            recipient_id: WhatsApp phone number (digits only, e.g. "15551234567")
                          or full JID ("15551234567@s.whatsapp.net" or
                          "123456789@g.us" for groups).
            content: Message text (sent as plain text; bridge delivers as-is).
            **kwargs: Reserved for future media/button support.

        Returns:
            Dict with ``message_id``, ``timestamp``, ``channel``,
            ``recipient_id``, ``success``, and ``error`` on failure.
        """
        if not self.client:
            await self.initialize()

        media_attachments = kwargs.pop("attachments", [])
        # Append attachment URLs as text links (bridge doesn't support native media)
        if media_attachments:
            links = "\n".join(
                f"[{a.filename or a.media_type}]: {a.url}" for a in media_attachments
            )
            content = f"{content}\n\n{links}" if content else links

        url = f"{self.bridge_url}/send"
        payload: Dict[str, Any] = {"recipient_id": recipient_id, "text": content}

        # Compute HMAC-SHA256 signature over the JSON body if secret is configured
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.bridge_secret:
            body_bytes = json.dumps(payload).encode("utf-8")
            sig = hmac.new(
                self.bridge_secret.encode("utf-8"), body_bytes, hashlib.sha256
            ).hexdigest()
            headers["X-WA-Secret"] = sig

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            data = response.json()

            if response.status_code == 200 and data.get("ok"):
                return {
                    "message_id": data.get("message_id"),
                    "timestamp": data.get("timestamp", datetime.utcnow().isoformat()),
                    "channel": "whatsapp",
                    "recipient_id": recipient_id,
                    "success": True,
                }
            else:
                return {
                    "message_id": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "channel": "whatsapp",
                    "recipient_id": recipient_id,
                    "success": False,
                    "error": data.get("error", f"Bridge error HTTP {response.status_code}"),
                }
        except httpx.RequestError as exc:
            return {
                "message_id": None,
                "timestamp": datetime.utcnow().isoformat(),
                "channel": "whatsapp",
                "recipient_id": recipient_id,
                "success": False,
                "error": str(exc),
            }

    @staticmethod
    def verify_signature(body: bytes, signature: str, secret: str) -> bool:
        """Verify an inbound HMAC-SHA256 signature from the Baileys bridge.

        The bridge computes HMAC-SHA256 over the raw JSON body using the
        shared secret and sends the hex digest in the ``X-WA-Secret`` header.

        Args:
            body: Raw request body bytes.
            signature: Value of the ``X-WA-Secret`` header (hex digest).
            secret: Shared bridge secret.

        Returns:
            True if the signature is valid or if secret is empty (dev mode).
            False on invalid signature or malformed inputs.
        """
        if not secret:
            return True  # Dev mode: no secret configured, allow all
        computed = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        try:
            return hmac.compare_digest(computed, signature)
        except (TypeError, ValueError):
            return False
