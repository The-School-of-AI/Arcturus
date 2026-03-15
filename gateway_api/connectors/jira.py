from __future__ import annotations

from typing import Any, Dict

from gateway_api.connectors.base import (
    BaseConnectorParser,
    ConnectorNormalizationError,
    NormalizedWebhookEvent,
    header_value,
)

_JIRA_EVENT_MAP = {
    "jira:issue_created": "task.complete",
    "jira:issue_updated": "task.complete",
    "jira:issue_deleted": "task.error",
    "comment_created": "agent.response",
    "comment_updated": "agent.response",
}


class JiraConnectorParser(BaseConnectorParser):
    source = "jira"

    def normalize(
        self,
        *,
        raw_payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> NormalizedWebhookEvent:
        if not isinstance(raw_payload, dict):
            raise ConnectorNormalizationError("Jira payload must be a JSON object")

        jira_event = str(raw_payload.get("webhookEvent") or "").strip().lower()
        if not jira_event:
            raise ConnectorNormalizationError("Missing webhookEvent in Jira payload")

        event_type = _JIRA_EVENT_MAP.get(jira_event, "agent.response")

        issue = raw_payload.get("issue") if isinstance(raw_payload.get("issue"), dict) else {}
        event_id = (
            header_value(headers, "x-atlassian-webhook-identifier")
            or header_value(headers, "x-request-id")
            or issue.get("id")
            or raw_payload.get("timestamp")
        )
        if event_id is not None:
            event_id = str(event_id)

        payload = {
            "connector": "jira",
            "jira_event": jira_event,
            "issue_key": issue.get("key"),
            "raw": raw_payload,
        }

        return NormalizedWebhookEvent(
            source=self.source,
            event_type=event_type,
            payload=payload,
            external_event_id=event_id,
            metadata={
                "connector": "jira",
                "jira_event": jira_event,
                "issue_key": str(issue.get("key") or ""),
            },
        )


SUPPORTED_EVENT_MAPPINGS: Dict[str, str] = _JIRA_EVENT_MAP.copy()
