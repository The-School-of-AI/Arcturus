from __future__ import annotations

import json
from typing import Any, Dict, List

from gateway_api.connectors.base import ConnectorNormalizationError, NormalizedWebhookEvent
from gateway_api.connectors.github import GitHubConnectorParser, SUPPORTED_EVENT_MAPPINGS as GITHUB_MAPPINGS
from gateway_api.connectors.gmail import GmailConnectorParser, SUPPORTED_EVENT_MAPPINGS as GMAIL_MAPPINGS
from gateway_api.connectors.jira import JiraConnectorParser, SUPPORTED_EVENT_MAPPINGS as JIRA_MAPPINGS


PARSER_REGISTRY = {
    "github": GitHubConnectorParser(),
    "jira": JiraConnectorParser(),
    "gmail": GmailConnectorParser(),
}

AUTH_MODES_BY_SOURCE = {
    "github": ["gateway_signature", "github_signature"],
    "jira": ["gateway_signature", "jira_token"],
    "gmail": ["gateway_signature", "gmail_token"],
}

EVENT_MAPPINGS_BY_SOURCE = {
    "github": GITHUB_MAPPINGS,
    "jira": JIRA_MAPPINGS,
    "gmail": GMAIL_MAPPINGS,
}


def normalize_connector_source(source: str) -> str:
    return source.strip().lower()


def parse_json_payload(raw_body: str) -> Dict[str, Any]:
    try:
        payload = json.loads(raw_body or "{}")
    except json.JSONDecodeError as exc:
        raise ConnectorNormalizationError("Webhook payload is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise ConnectorNormalizationError("Webhook payload must be a JSON object")

    return payload


def normalize_event(
    *,
    source: str,
    raw_payload: Dict[str, Any],
    headers: Dict[str, str],
) -> NormalizedWebhookEvent:
    source_key = normalize_connector_source(source)
    parser = PARSER_REGISTRY.get(source_key)
    if parser is None:
        raise ConnectorNormalizationError(f"Unsupported connector source: {source_key}")
    return parser.normalize(raw_payload=raw_payload, headers=headers)


def list_supported_connectors() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for source in sorted(PARSER_REGISTRY.keys()):
        items.append(
            {
                "source": source,
                "auth_modes": AUTH_MODES_BY_SOURCE.get(source, ["gateway_signature"]),
                "event_mappings": EVENT_MAPPINGS_BY_SOURCE.get(source, {}),
            }
        )
    return items
