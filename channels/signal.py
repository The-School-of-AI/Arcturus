"""Signal channel adapter for Arcturus gateway.

Provides outbound messaging via a local signal-cli bridge (POST /send) and
inbound webhook signature verification (HMAC-SHA256) for messages the
bridge forwards to POST /api/nexus/signal/inbound.

Architecture:
  Outbound:  SignalAdapter.send_message() → POST http://localhost:3002/send
  Inbound:   bridge POSTs to FastAPI → routers/nexus.py → MessageEnvelope.from_signal()
  Formatter: MessageFormatter._format_plain() (Signal renders plain text natively)

The bridge process (signal_bridge/app.py) must be running separately alongside
signal-cli in HTTP daemon mode.  See signal_bridge/README.md for setup.

Disappearing messages:
  Signal's disappearing message timer is a client-side setting per conversation.
  This adapter does NOT modify or override that timer — it honours whatever the
  user has configured in the Signal mobile app.  Messages sent by the bot will
  expire according to the existing conversation setting.

Environment variables:
  SIGNAL_BRIDGE_URL     Base URL of the signal bridge HTTP server (default: http://localhost:3002)
  SIGNAL_BRIDGE_SECRET  Shared HMAC-SHA256 secret for bridge ↔ FastAPI auth (optional)
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

# Load .env file if it exists
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


class SignalAdapter(ChannelAdapter):
    """Signal channel adapter using the signal-cli Python bridge.

    Communicates with a local signal-cli bridge process to send and receive
    Signal messages.  The bridge maintains the signal-cli session and
    polls signal-cli for inbound messages every 2 seconds.

    Outbound:  POST {bridge_url}/send
    Inbound:   handled by routers/nexus.py POST /nexus/signal/inbound
    Formatter: plain text (Signal renders plain text natively)

    Disappearing messages:
        Signal's disappearing message timer is honoured as-is — this adapter
        does not modify per-conversation expiry settings.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialise the Signal adapter.

        Args:
            config: Dict optionally containing 'bridge_url' and 'bridge_secret'.
                    Falls back to SIGNAL_BRIDGE_URL / SIGNAL_BRIDGE_SECRET
                    env vars, then defaults.
        """
        super().__init__("signal", config)
        cfg = config or {}
        self.bridge_url = (
            cfg.get("bridge_url") or os.getenv("SIGNAL_BRIDGE_URL", "http://localhost:3002")
        ).rstrip("/")
        self.bridge_secret = cfg.get("bridge_secret") or os.getenv("SIGNAL_BRIDGE_SECRET", "")
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Create the async HTTP client."""
        self.client = httpx.AsyncClient(timeout=30.0)

    async def shutdown(self) -> None:
        """Gracefully close the HTTP client."""
        if self.client:
            await self.client.aclose()

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> Dict[str, Any]:
        """Send a message to a Signal number or group via the bridge.

        Args:
            recipient_id: Signal phone number in E.164 format (``+15551234567``)
                          or a Signal group ID.
            content: Message text (sent as plain text; Signal renders as-is).
            **kwargs: Reserved for future attachment / expiration support.

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
            headers["X-Signal-Secret"] = sig

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            data = response.json()

            if response.status_code == 200 and data.get("ok"):
                return {
                    "message_id": data.get("message_id"),
                    "timestamp": data.get("timestamp", datetime.utcnow().isoformat()),
                    "channel": "signal",
                    "recipient_id": recipient_id,
                    "success": True,
                }
            else:
                return {
                    "message_id": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "channel": "signal",
                    "recipient_id": recipient_id,
                    "success": False,
                    "error": data.get("error", f"Bridge error HTTP {response.status_code}"),
                }
        except httpx.RequestError as exc:
            return {
                "message_id": None,
                "timestamp": datetime.utcnow().isoformat(),
                "channel": "signal",
                "recipient_id": recipient_id,
                "success": False,
                "error": str(exc),
            }

    @staticmethod
    def verify_signature(body: bytes, signature: str, secret: str) -> bool:
        """Verify an inbound HMAC-SHA256 signature from the signal-cli bridge.

        The bridge computes HMAC-SHA256 over the raw JSON body using the
        shared secret and sends the hex digest in the ``X-Signal-Secret`` header.

        Args:
            body: Raw request body bytes.
            signature: Value of the ``X-Signal-Secret`` header (hex digest).
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
