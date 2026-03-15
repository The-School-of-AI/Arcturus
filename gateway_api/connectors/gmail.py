from __future__ import annotations

from typing import Dict

from gateway_api.connectors.base import (
    BaseConnectorParser,
    ConnectorNormalizationError,
    NormalizedWebhookEvent,
    header_value,
)

_GMAIL_EVENT_MAP = {
    "mailbox_update": "memory.updated",
}


class GmailConnectorParser(BaseConnectorParser):
    source = "gmail"

    def normalize(
        self,
        *,
        raw_payload: Dict[str, object],
        headers: Dict[str, str],
    ) -> NormalizedWebhookEvent:
        if not isinstance(raw_payload, dict):
            raise ConnectorNormalizationError("Gmail payload must be a JSON object")

        if not raw_payload.get("emailAddress") or not raw_payload.get("historyId"):
            raise ConnectorNormalizationError(
                "Gmail payload requires emailAddress and historyId"
            )

        event_name = str(raw_payload.get("event") or "mailbox_update").strip().lower()
        event_type = _GMAIL_EVENT_MAP.get(event_name, "memory.updated")

        event_id = (
            header_value(headers, "x-goog-message-number")
            or raw_payload.get("historyId")
        )
        if event_id is not None:
            event_id = str(event_id)

        payload = {
            "connector": "gmail",
            "gmail_event": event_name,
            "email_address": str(raw_payload.get("emailAddress")),
            "history_id": str(raw_payload.get("historyId")),
            "raw": raw_payload,
        }

        return NormalizedWebhookEvent(
            source=self.source,
            event_type=event_type,
            payload=payload,
            external_event_id=event_id,
            metadata={
                "connector": "gmail",
                "gmail_event": event_name,
                "email_address": str(raw_payload.get("emailAddress")),
            },
        )


SUPPORTED_EVENT_MAPPINGS: Dict[str, str] = _GMAIL_EVENT_MAP.copy()
