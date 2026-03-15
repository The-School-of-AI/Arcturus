from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


class ConnectorNormalizationError(ValueError):
    """Raised when a connector payload cannot be normalized."""


@dataclass
class NormalizedWebhookEvent:
    source: str
    event_type: str
    payload: Dict[str, Any]
    external_event_id: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseConnectorParser:
    source: str = ""

    def normalize(
        self,
        *,
        raw_payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> NormalizedWebhookEvent:
        raise NotImplementedError


def header_value(headers: Dict[str, str], name: str) -> str | None:
    return headers.get(name.lower()) or headers.get(name) or None
