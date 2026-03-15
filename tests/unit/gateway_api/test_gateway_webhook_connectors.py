import hashlib
import hmac
import json
import time

import pytest

from gateway_api.connectors import ConnectorNormalizationError, normalize_event
from gateway_api.idempotency import derive_inbound_idempotency_key
from gateway_api.webhooks import (
    InvalidWebhookSignature,
    WebhookService,
    WebhookSigningNotConfigured,
)


def _service(tmp_path):
    return WebhookService(
        subscriptions_file=tmp_path / "subs.json",
        deliveries_file=tmp_path / "deliveries.jsonl",
        dlq_file=tmp_path / "dlq.jsonl",
    )


def test_connector_normalization_github_jira_gmail():
    github = normalize_event(
        source="github",
        raw_payload={"ref": "refs/heads/main", "after": "abc"},
        headers={"x-github-event": "push", "x-github-delivery": "del-1"},
    )
    assert github.event_type == "memory.updated"
    assert github.external_event_id == "del-1"

    jira = normalize_event(
        source="jira",
        raw_payload={"webhookEvent": "jira:issue_created", "issue": {"id": "100", "key": "PROJ-1"}},
        headers={"x-atlassian-webhook-identifier": "jira-evt-1"},
    )
    assert jira.event_type == "task.complete"
    assert jira.external_event_id == "jira-evt-1"

    gmail = normalize_event(
        source="gmail",
        raw_payload={"emailAddress": "dev@example.com", "historyId": "42"},
        headers={"x-goog-message-number": "msg-42"},
    )
    assert gmail.event_type == "memory.updated"
    assert gmail.external_event_id == "msg-42"


def test_connector_normalization_rejects_malformed_payloads():
    with pytest.raises(ConnectorNormalizationError):
        normalize_event(
            source="github",
            raw_payload={},
            headers={"x-github-delivery": "del-1"},
        )

    with pytest.raises(ConnectorNormalizationError):
        normalize_event(
            source="jira",
            raw_payload={"issue": {"id": "1"}},
            headers={},
        )

    with pytest.raises(ConnectorNormalizationError):
        normalize_event(
            source="gmail",
            raw_payload={"emailAddress": "dev@example.com"},
            headers={},
        )


def test_idempotency_key_prefers_external_event_id_over_signature_and_body():
    key_a = derive_inbound_idempotency_key(
        source="github",
        signature_header="sig-1",
        timestamp_header="123",
        raw_body='{"a":1}',
        external_event_id="evt-123",
    )
    key_b = derive_inbound_idempotency_key(
        source="github",
        signature_header="sig-2",
        timestamp_header="999",
        raw_body='{"a":2}',
        external_event_id="evt-123",
    )
    key_c = derive_inbound_idempotency_key(
        source="github",
        signature_header="sig-2",
        timestamp_header="999",
        raw_body='{"a":2}',
        external_event_id="evt-456",
    )

    assert key_a == key_b
    assert key_a != key_c


def test_dual_mode_gateway_signature_auth_passes(monkeypatch, tmp_path):
    service = _service(tmp_path)
    monkeypatch.setenv("ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET", "gateway-secret")

    body = json.dumps({"event_type": "task.complete", "payload": {"run_id": "1"}})
    timestamp = str(int(time.time()))
    signature = "sha256=" + hmac.new(
        b"gateway-secret",
        f"{timestamp}.{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    auth_mode = service.validate_inbound_auth(
        source="github",
        headers={
            "x-gateway-signature": signature,
            "x-gateway-timestamp": timestamp,
        },
        raw_body=body,
    )
    assert auth_mode == "gateway_signature"


def test_dual_mode_connector_auth_passes_and_fail_closed(monkeypatch, tmp_path):
    service = _service(tmp_path)

    body = json.dumps({"ref": "refs/heads/main", "after": "abc"})
    monkeypatch.setenv("ARCTURUS_GATEWAY_GITHUB_WEBHOOK_SECRET", "gh-secret")
    signature = "sha256=" + hmac.new(
        b"gh-secret",
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    auth_mode = service.validate_inbound_auth(
        source="github",
        headers={
            "x-hub-signature-256": signature,
            "x-github-event": "push",
        },
        raw_body=body,
    )
    assert auth_mode == "github_signature"

    monkeypatch.delenv("ARCTURUS_GATEWAY_GITHUB_WEBHOOK_SECRET", raising=False)
    with pytest.raises(WebhookSigningNotConfigured):
        service.validate_inbound_auth(
            source="github",
            headers={"x-hub-signature-256": signature, "x-github-event": "push"},
            raw_body=body,
        )

    monkeypatch.setenv("ARCTURUS_GATEWAY_GITHUB_WEBHOOK_SECRET", "gh-secret")
    with pytest.raises(InvalidWebhookSignature):
        service.validate_inbound_auth(
            source="github",
            headers={"x-hub-signature-256": "sha256=bad", "x-github-event": "push"},
            raw_body=body,
        )
