from __future__ import annotations

from typing import Any, Dict

from gateway_api.connectors.base import (
    BaseConnectorParser,
    ConnectorNormalizationError,
    NormalizedWebhookEvent,
    header_value,
)

_GITHUB_EVENT_MAP = {
    "push": "memory.updated",
    "pull_request": "task.complete",
    "issues": "task.error",
    "ping": "session.started",
    "release": "session.ended",
}


class GitHubConnectorParser(BaseConnectorParser):
    source = "github"

    def normalize(
        self,
        *,
        raw_payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> NormalizedWebhookEvent:
        if not isinstance(raw_payload, dict):
            raise ConnectorNormalizationError("GitHub payload must be a JSON object")

        github_event = (header_value(headers, "x-github-event") or "").strip().lower()
        if not github_event:
            raise ConnectorNormalizationError("Missing x-github-event header")

        event_type = _GITHUB_EVENT_MAP.get(github_event, "agent.response")
        event_id = (
            header_value(headers, "x-github-delivery")
            or raw_payload.get("delivery_id")
            or raw_payload.get("id")
        )
        if event_id is not None:
            event_id = str(event_id)

        payload = {
            "connector": "github",
            "github_event": github_event,
            "raw": raw_payload,
        }

        return NormalizedWebhookEvent(
            source=self.source,
            event_type=event_type,
            payload=payload,
            external_event_id=event_id,
            metadata={
                "connector": "github",
                "github_event": github_event,
            },
        )


SUPPORTED_EVENT_MAPPINGS: Dict[str, str] = _GITHUB_EVENT_MAP.copy()
