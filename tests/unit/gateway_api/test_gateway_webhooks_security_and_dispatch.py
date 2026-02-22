import asyncio
import hashlib
import hmac
import json
import time

import pytest

from gateway_api.webhooks import (
    InvalidWebhookSignature,
    WebhookService,
    WebhookSigningNotConfigured,
)


def test_inbound_webhook_signature_validates_hmac_and_timestamp(monkeypatch, tmp_path):
    service = WebhookService(
        subscriptions_file=tmp_path / "subs.json",
        deliveries_file=tmp_path / "deliveries.jsonl",
        dlq_file=tmp_path / "dlq.jsonl",
    )

    monkeypatch.setenv("ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET", "secret-123")
    body = json.dumps({"event_type": "task.complete", "payload": {"run_id": "1"}})
    timestamp = str(int(time.time()))
    signature = "sha256=" + hmac.new(
        b"secret-123",
        f"{timestamp}.{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    service.validate_inbound_signature(signature, timestamp, body)

    with pytest.raises(InvalidWebhookSignature):
        service.validate_inbound_signature("sha256=bad", timestamp, body)


def test_inbound_webhook_fails_closed_when_signing_secret_missing(monkeypatch, tmp_path):
    service = WebhookService(
        subscriptions_file=tmp_path / "subs.json",
        deliveries_file=tmp_path / "deliveries.jsonl",
        dlq_file=tmp_path / "dlq.jsonl",
    )

    monkeypatch.delenv("ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET", raising=False)

    with pytest.raises(WebhookSigningNotConfigured):
        service.validate_inbound_signature("sha256=anything", str(int(time.time())), "{}")


def test_webhook_dispatch_retries_then_moves_to_dlq(tmp_path):
    service = WebhookService(
        subscriptions_file=tmp_path / "subs.json",
        deliveries_file=tmp_path / "deliveries.jsonl",
        dlq_file=tmp_path / "dlq.jsonl",
    )

    asyncio.run(
        service.create_subscription(
            target_url="https://example.com/webhook",
            event_types=["task.complete"],
            secret="delivery-secret",
            active=True,
        )
    )

    queued = asyncio.run(
        service.trigger_event(
            event_type="task.complete",
            payload={"run_id": "retry-case"},
            source="unit_test",
            trace_id="trc_retry",
        )
    )
    assert queued["queued_deliveries"] == 1

    async def _always_fail(delivery):
        del delivery
        return False, "boom"

    service._deliver_once = _always_fail  # type: ignore[method-assign]

    first = asyncio.run(
        service.dispatch_pending(limit=10, max_attempts=2, base_backoff_seconds=0)
    )
    assert first["scanned"] == 1
    assert first["retried"] == 1
    assert first["dead_lettered"] == 0

    second = asyncio.run(
        service.dispatch_pending(limit=10, max_attempts=2, base_backoff_seconds=0)
    )
    assert second["scanned"] == 1
    assert second["dead_lettered"] == 1

    dead_letter_rows = asyncio.run(service.list_deliveries(status="dead_letter", limit=10))
    assert len(dead_letter_rows) == 1
    assert dead_letter_rows[0]["status"] == "dead_letter"
    assert (tmp_path / "dlq.jsonl").exists()
