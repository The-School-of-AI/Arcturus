"""Google Chat channel adapter for Arcturus gateway.

Provides outbound messaging via the Google Chat REST API (spaces.messages.create)
and inbound webhook verification for the Google Chat Events API.

Google Chat delivers events as HTTP POSTs to a configured webhook URL.
Outbound replies use the Chat API with a service-account bearer token (or the
simpler incoming-webhook URL for spaces that use that flow).

Two delivery modes are supported:
1. **Incoming webhook** (simple): POST to a webhook URL — no auth needed;
   only supports text/card messages to the space the webhook was created for.
2. **Service account** (full): POST to the Chat REST API with OAuth2 bearer token;
   supports any space the service account has been invited to.

This adapter auto-detects the mode based on which env vars are set:
- ``GOOGLE_CHAT_WEBHOOK_URL`` → incoming webhook mode (simplest, no GCP project needed)
- ``GOOGLE_CHAT_SERVICE_ACCOUNT_TOKEN`` → service account mode (full API access)
"""

import hashlib
import hmac
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

# Google Chat REST API base
_CHAT_API_BASE = "https://chat.googleapis.com/v1"


class GoogleChatAdapter(ChannelAdapter):
    """Google Chat channel adapter.

    Integrates with Google Chat to send messages to Spaces via either
    an incoming webhook URL or the Chat REST API with a service-account token.

    Outbound (webhook mode):  POST {GOOGLE_CHAT_WEBHOOK_URL}
    Outbound (API mode):      POST https://chat.googleapis.com/v1/spaces/{space}/messages
    Inbound:                  handled by routers/nexus.py POST /nexus/googlechat/events
    Formatter:                MessageFormatter._format_googlechat() → Google Chat card text

    Authentication:
        Webhook mode  — no auth (URL is secret by itself).
        API mode      — Bearer token in Authorization header.

    Verification:
        Google Chat sends a ``X-Goog-Signature`` HMAC-SHA256 header over
        the raw JSON body when a verification token is configured.
        Set ``GOOGLE_CHAT_VERIFICATION_TOKEN`` to enable verification.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialise the Google Chat adapter.

        Args:
            config: Dict with optional keys:
                - ``webhook_url``: Incoming webhook URL (space-scoped).
                - ``service_account_token``: OAuth2 bearer token.
                - ``verification_token``: HMAC verification token for inbound events.
                Falls back to env vars if not supplied.
        """
        super().__init__("googlechat", config)
        cfg = config or {}
        self.webhook_url: str = cfg.get("webhook_url") or os.getenv("GOOGLE_CHAT_WEBHOOK_URL", "")
        self.service_account_token: str = (
            cfg.get("service_account_token") or os.getenv("GOOGLE_CHAT_SERVICE_ACCOUNT_TOKEN", "")
        )
        self.verification_token: str = (
            cfg.get("verification_token") or os.getenv("GOOGLE_CHAT_VERIFICATION_TOKEN", "")
        )
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Create the async HTTP client."""
        self.client = httpx.AsyncClient(timeout=30.0)

    async def shutdown(self) -> None:
        """Gracefully close the HTTP client."""
        if self.client:
            await self.client.aclose()

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> Dict[str, Any]:
        """Send a message to a Google Chat Space.

        Args:
            recipient_id: Space resource name (``spaces/XXXXXXXXX``) when using
                          the Chat API, or ignored in webhook mode (the webhook
                          URL already encodes the destination space).
            content: Message text, pre-formatted by MessageFormatter.
            **kwargs: Additional Chat API fields (``thread``, ``cards``, etc.)

        Returns:
            Dict with ``message_id``, ``timestamp``, ``channel``,
            ``recipient_id``, ``success``, and ``error`` on failure.
        """
        if not self.client:
            await self.initialize()

        media_attachments = kwargs.pop("attachments", [])
        # Append attachment URLs as text links (Google Chat has no binary upload API)
        if media_attachments:
            links = "\n".join(
                f"[{a.filename or a.media_type}]: {a.url}" for a in media_attachments
            )
            content = f"{content}\n\n{links}" if content else links

        # Build the message payload — simple text message
        payload: Dict[str, Any] = {"text": content, **kwargs}

        try:
            if self.webhook_url:
                # Incoming webhook mode — no auth, POST to webhook URL directly
                response = await self.client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
            elif self.service_account_token:
                # Service account API mode — Bearer token auth
                url = f"{_CHAT_API_BASE}/{recipient_id}/messages"
                headers = {
                    "Authorization": f"Bearer {self.service_account_token}",
                    "Content-Type": "application/json",
                }
                response = await self.client.post(url, json=payload, headers=headers)
            else:
                # No credentials configured — return error without crashing
                return {
                    "message_id": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "channel": "googlechat",
                    "recipient_id": recipient_id,
                    "success": False,
                    "error": "No Google Chat credentials configured (GOOGLE_CHAT_WEBHOOK_URL or GOOGLE_CHAT_SERVICE_ACCOUNT_TOKEN)",
                }

            if response.status_code in (200, 201):
                data = response.json()
                return {
                    "message_id": data.get("name", ""),
                    "timestamp": data.get("createTime", datetime.utcnow().isoformat()),
                    "channel": "googlechat",
                    "recipient_id": recipient_id,
                    "success": True,
                }
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                except Exception:
                    error_msg = f"HTTP {response.status_code}"
                return {
                    "message_id": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "channel": "googlechat",
                    "recipient_id": recipient_id,
                    "success": False,
                    "error": error_msg,
                }

        except httpx.RequestError as exc:
            return {
                "message_id": None,
                "timestamp": datetime.utcnow().isoformat(),
                "channel": "googlechat",
                "recipient_id": recipient_id,
                "success": False,
                "error": str(exc),
            }

    @staticmethod
    def verify_signature(body: bytes, token_header: str, verification_token: str) -> bool:
        """Verify a Google Chat inbound event token.

        Google Chat sends a ``token`` field in the JSON body (or a
        ``X-Goog-Signature`` header for DomainWideDelegation setups).
        The simplest verification: compare the token in the payload body
        against the configured verification token (constant-time).

        For production webhook events Google also populates the ``token``
        field in the JSON body — this method supports both approaches:
        1. Direct token comparison (``token_header`` IS the token value).
        2. HMAC-SHA256 body signing if the token_header is a hex digest.

        Args:
            body: Raw request body bytes.
            token_header: Value of the token (from JSON body ``token`` field or header).
            verification_token: Expected token from env / config.

        Returns:
            True if the token matches, False otherwise.
        """
        if not verification_token:
            return True  # verification disabled (dev mode)
        # Constant-time comparison to prevent timing attacks
        if hmac.compare_digest(token_header.encode(), verification_token.encode()):
            return True
        # Also accept HMAC-SHA256 over body (alternative Google Chat signing)
        expected_hmac = hmac.new(
            verification_token.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(token_header, expected_hmac)
