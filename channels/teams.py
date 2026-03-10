"""Microsoft Teams channel adapter for Arcturus gateway.

Provides outbound messaging via the Microsoft Bot Framework REST API and
inbound webhook handling for Bot Framework Activity events posted to
POST /api/nexus/teams/events.

Architecture:
  Outbound:  TeamsAdapter.send_message() →
             POST {service_url}/v3/conversations/{conversation_id}/activities
  Inbound:   Teams/Bot Framework POSTs Activity JSON →
             routers/nexus.py → MessageEnvelope.from_teams()
  Formatter: Markdown with heading → **bold** conversion (_format_teams)

The adapter uses the Microsoft Bot Framework v3 REST API.
A registered Azure Bot Service app (App ID + password) is required for
production use. In dev/test mode, leave TEAMS_APP_PASSWORD empty to skip
token verification.

Setup:
  1. Register a bot at https://dev.botframework.com or Azure Portal → Bot Services.
  2. Note the App ID and App Password from the registration.
  3. Set the messaging endpoint to:
       http://<your-host>:8000/api/nexus/teams/events
  4. Set TEAMS_APP_ID and TEAMS_APP_PASSWORD in .env.

Environment variables:
  TEAMS_APP_ID        Azure Bot Service app registration ID
  TEAMS_APP_PASSWORD  Azure Bot Service app password (shared secret)
  TEAMS_SERVICE_URL   Bot Framework service URL
                      (default: https://smba.trafficmanager.net/apis)
"""

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

_BOT_FRAMEWORK_API = "/v3/conversations/{conversation_id}/activities"


class TeamsAdapter(ChannelAdapter):
    """Microsoft Teams channel adapter using the Bot Framework REST API.

    Communicates with the Microsoft Bot Framework service to send messages
    to Teams channels and DMs.  The Bot Framework service acts as an
    intermediary between this adapter and the Teams client.

    Outbound:  POST {service_url}/v3/conversations/{conversation_id}/activities
    Inbound:   handled by routers/nexus.py POST /nexus/teams/events
    Formatter: Markdown with heading → **bold** conversion
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialise the Teams adapter.

        Args:
            config: Dict optionally containing:
                - ``app_id``: Azure Bot Service app ID.
                - ``app_password``: Azure Bot Service app password.
                - ``service_url``: Bot Framework service base URL.
                Falls back to env vars if not supplied.
        """
        super().__init__("teams", config)
        cfg = config or {}
        self.app_id = cfg.get("app_id") or os.getenv("TEAMS_APP_ID", "")
        self.app_password = cfg.get("app_password") or os.getenv("TEAMS_APP_PASSWORD", "")
        self.service_url = (
            cfg.get("service_url")
            or os.getenv("TEAMS_SERVICE_URL", "https://smba.trafficmanager.net/apis")
        ).rstrip("/")
        self.client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Create the async HTTP client."""
        self.client = httpx.AsyncClient(timeout=30.0)

    async def shutdown(self) -> None:
        """Gracefully close the HTTP client."""
        if self.client:
            await self.client.aclose()

    async def send_typing_indicator(self, recipient_id: str, **kwargs) -> None:
        """Send a typing activity to a Teams conversation."""
        if not self.client:
            return
        url = self.service_url + _BOT_FRAMEWORK_API.format(conversation_id=recipient_id)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.app_password:
            headers["Authorization"] = f"Bearer {self.app_password}"
        try:
            await self.client.post(url, json={"type": "typing"}, headers=headers)
        except Exception:
            pass  # typing is cosmetic — never fail the pipeline

    async def send_message(self, recipient_id: str, content: str, **kwargs) -> dict[str, Any]:
        """Send a message to a Teams conversation via the Bot Framework API.

        Args:
            recipient_id: The Bot Framework conversation ID (from the inbound
                Activity ``conversation.id`` field).  This is the opaque ID
                that the Bot Framework service assigned to the conversation.
            content: Message text (Markdown supported).
            **kwargs: Reserved for future Adaptive Card / attachment support.

        Returns:
            Dict with ``message_id``, ``timestamp``, ``channel``,
            ``recipient_id``, ``success``, and ``error`` on failure.
        """
        if not self.client:
            await self.initialize()

        url = self.service_url + _BOT_FRAMEWORK_API.format(conversation_id=recipient_id)
        media_attachments = kwargs.pop("attachments", [])
        payload: dict[str, Any] = {
            "type": "message",
            "text": content,
            "textFormat": "markdown",
            **kwargs,
        }
        if media_attachments:
            payload["attachments"] = [
                {"contentType": a.mime_type or "application/octet-stream",
                 "contentUrl": a.url,
                 "name": a.filename or "attachment"}
                for a in media_attachments
            ]

        # Add Authorization header if app credentials are configured
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.app_password:
            headers["Authorization"] = f"Bearer {self.app_password}"

        try:
            response = await self.client.post(url, json=payload, headers=headers)
            if response.status_code in (200, 201):
                data = response.json()
                return {
                    "message_id": data.get("id", ""),
                    "timestamp": datetime.utcnow().isoformat(),
                    "channel": "teams",
                    "recipient_id": recipient_id,
                    "success": True,
                }
            else:
                try:
                    error_data = response.json()
                    error_msg = (
                        error_data.get("error", {}).get("message")
                        or error_data.get("message")
                        or f"HTTP {response.status_code}"
                    )
                except Exception:
                    error_msg = f"HTTP {response.status_code}"
                return {
                    "message_id": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "channel": "teams",
                    "recipient_id": recipient_id,
                    "success": False,
                    "error": error_msg,
                }
        except httpx.RequestError as exc:
            return {
                "message_id": None,
                "timestamp": datetime.utcnow().isoformat(),
                "channel": "teams",
                "recipient_id": recipient_id,
                "success": False,
                "error": str(exc),
            }

    @staticmethod
    def verify_token(token: str, expected_password: str) -> bool:
        """Verify an inbound Bearer token from the Bot Framework.

        In production, the Bot Framework sends a signed JWT that should be
        validated against Microsoft's OpenID Connect endpoints.  For P01
        simplicity, we compare the raw Bearer token against the configured
        ``TEAMS_APP_PASSWORD`` shared secret.

        Args:
            token: Value extracted from ``Authorization: Bearer {token}``.
            expected_password: The configured ``TEAMS_APP_PASSWORD``.

        Returns:
            True if the token matches, or if expected_password is empty
            (dev mode — no verification).
            False on mismatch.
        """
        if not expected_password:
            return True  # Dev mode: skip verification
        try:
            return hmac.compare_digest(token.encode("utf-8"), expected_password.encode("utf-8"))
        except (TypeError, ValueError):
            return False
