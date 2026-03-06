"""Slack channel adapter for Arcturus gateway.

Provides outbound messaging via the Slack Web API (chat.postMessage) and
inbound webhook signature verification for the Events API.
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


class SlackAdapter(ChannelAdapter):
    """Slack channel adapter.

    Integrates with the Slack Web API to send messages to channels and DMs.
    Supports inbound webhook signature verification for the Events API.

    Outbound:  POST https://slack.com/api/chat.postMessage
    Inbound:   handled by routers/nexus.py POST /nexus/slack/events
    Formatter: MessageFormatter._format_slack() → mrkdwn
    """

    SLACK_API_URL = "https://slack.com/api/chat.postMessage"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialise the Slack adapter.

        Args:
            config: Dict containing 'token' (Bot token, ``xoxb-…``) and
                    optionally 'signing_secret'.  If not provided, reads from
                    ``SLACK_BOT_TOKEN`` / ``SLACK_SIGNING_SECRET`` env vars.
        """
        super().__init__("slack", config)
        cfg = config or {}
        self.token = cfg.get("token") or os.getenv("SLACK_BOT_TOKEN", "")
        self.signing_secret = cfg.get("signing_secret") or os.getenv("SLACK_SIGNING_SECRET", "")
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Create the async HTTP client."""
        self.client = httpx.AsyncClient(timeout=30.0)

    async def shutdown(self) -> None:
        """Gracefully close the HTTP client."""
        if self.client:
            await self.client.aclose()

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> Dict[str, Any]:
        """Send a message to a Slack channel or DM.

        Args:
            recipient_id: Slack channel ID (``C…``) or user ID (``U…`` for DMs).
            content: Message text, pre-formatted as mrkdwn by MessageFormatter.
            **kwargs: Additional Slack API fields (``thread_ts``, ``blocks``, etc.)

        Returns:
            Dict with ``message_id`` (Slack ``ts``), ``timestamp``, ``channel``,
            ``recipient_id``, ``success``, and ``error`` on failure.
        """
        if not self.client:
            await self.initialize()

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        media_attachments = kwargs.pop("attachments", [])
        payload: Dict[str, Any] = {
            "channel": recipient_id,
            "text": content,
            **kwargs,
        }

        try:
            response = await self.client.post(self.SLACK_API_URL, json=payload, headers=headers)
            data = response.json()

            if data.get("ok"):
                ts = data.get("ts", "")
                # Slack ts is a Unix float string like "1234567890.123456"
                try:
                    ts_float = float(ts)
                    timestamp = datetime.fromtimestamp(ts_float).isoformat()
                except (ValueError, TypeError):
                    timestamp = datetime.utcnow().isoformat()
                result = {
                    "message_id": ts,
                    "timestamp": timestamp,
                    "channel": "slack",
                    "recipient_id": recipient_id,
                    "success": True,
                }
            else:
                return {
                    "message_id": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "channel": "slack",
                    "recipient_id": recipient_id,
                    "success": False,
                    "error": data.get("error", "Unknown Slack API error"),
                }
        except httpx.RequestError as exc:
            return {
                "message_id": None,
                "timestamp": datetime.utcnow().isoformat(),
                "channel": "slack",
                "recipient_id": recipient_id,
                "success": False,
                "error": str(exc),
            }

        # Send any media attachments after text
        for att in media_attachments:
            await self._send_attachment(recipient_id, att)

        return result

    async def _send_attachment(self, channel_id: str, att) -> None:
        """Send a single media attachment to Slack via Block Kit."""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        if att.media_type == "image":
            blocks = [{"type": "image", "image_url": att.url,
                        "alt_text": att.filename or "image"}]
            payload: Dict[str, Any] = {"channel": channel_id, "blocks": blocks}
        else:
            payload = {"channel": channel_id,
                       "text": f"<{att.url}|{att.filename or 'attachment'}>"}
        try:
            await self.client.post(self.SLACK_API_URL, json=payload, headers=headers)
        except Exception:
            pass  # best-effort media delivery

    @staticmethod
    def verify_signature(body: bytes, timestamp: str, signature: str, secret: str) -> bool:
        """Verify a Slack Events API webhook signature.

        Slack signs every inbound request with HMAC-SHA256 over
        ``v0:{timestamp}:{raw_body}`` using the app's signing secret.

        Args:
            body: Raw request body bytes.
            timestamp: Value of the ``X-Slack-Request-Timestamp`` header.
            signature: Value of the ``X-Slack-Signature`` header (``v0=…``).
            secret: App signing secret from Slack app settings.

        Returns:
            True if the signature is valid, False otherwise.
        """
        basestring = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
        computed = "v0=" + hmac.new(secret.encode("utf-8"), basestring, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, signature)
