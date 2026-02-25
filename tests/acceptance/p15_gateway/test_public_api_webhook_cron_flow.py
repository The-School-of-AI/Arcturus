import hashlib
import hmac
import json
import time

import pytest

from p15_gateway_runtime import build_gateway_runtime_context


@pytest.fixture()
def runtime_ctx(tmp_path, monkeypatch):
    return build_gateway_runtime_context(tmp_path, monkeypatch)


def _signed_headers(secret: str, body: str, timestamp: str):
    signature = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "content-type": "application/json",
        "x-gateway-signature": signature,
        "x-gateway-timestamp": timestamp,
    }


def test_01_gateway_requires_api_key_for_protected_routes(runtime_ctx):
    client = runtime_ctx["client"]

    response = client.post(
        "/api/v1/pages/generate",
        json={"query": "test"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["error"]["code"] == "missing_api_key"


def test_02_pages_generate_happy_path_returns_trace_and_citations(runtime_ctx):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["pages:write"])

    response = client.post(
        "/api/v1/pages/generate",
        json={"query": "AI infra trends", "template": "overview"},
        headers={"x-api-key": api_key},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["trace_id"].startswith("trc_")
    assert payload["citations"] == ["https://oracle.example.com"]


def test_03_studio_docs_happy_path_returns_outline(runtime_ctx):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["studio:write"])

    response = client.post(
        "/api/v1/studio/docs",
        json={"prompt": "Create architecture decision record"},
        headers={"x-api-key": api_key},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_type"] == "document"
    assert payload["outline"]["title"] == "Document Outline"


def test_04_webhook_inbound_rejects_invalid_signature(runtime_ctx, monkeypatch):
    client = runtime_ctx["client"]
    monkeypatch.setenv("ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET", "phase2-secret")

    body = json.dumps({"event_type": "task.complete", "payload": {"run_id": "123"}})
    timestamp = str(int(time.time()))

    response = client.post(
        "/api/v1/webhooks/inbound/github",
        content=body,
        headers={
            "content-type": "application/json",
            "x-gateway-signature": "sha256=bad",
            "x-gateway-timestamp": timestamp,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["error"]["code"] == "invalid_webhook_signature"


def test_05_webhook_inbound_accepts_valid_signature_and_queues(runtime_ctx, monkeypatch):
    client = runtime_ctx["client"]
    create_api_key = runtime_ctx["create_api_key"]
    api_key = create_api_key(["webhooks:write"])

    client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://example.com/inbound",
            "event_types": ["task.complete"],
        },
        headers={"x-api-key": api_key},
    )

    monkeypatch.setenv("ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET", "phase2-secret")

    body = json.dumps({"event_type": "task.complete", "payload": {"run_id": "123"}})
    timestamp = str(int(time.time()))

    response = client.post(
        "/api/v1/webhooks/inbound/github",
        content=body,
        headers=_signed_headers("phase2-secret", body, timestamp),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["queued_deliveries"] >= 1


def test_06_webhook_dispatch_retries_then_dead_letters(runtime_ctx, monkeypatch):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["webhooks:write", "webhooks:read"])
    webhook_service = runtime_ctx["webhook_service"]

    client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://example.com/failing-target",
            "event_types": ["task.error"],
        },
        headers={"x-api-key": api_key},
    )
    client.post(
        "/api/v1/webhooks/trigger",
        json={"event_type": "task.error", "payload": {"run_id": "xyz"}},
        headers={"x-api-key": api_key},
    )

    async def _always_fail(delivery):
        del delivery
        return False, "simulated failure"

    monkeypatch.setattr(webhook_service, "_deliver_once", _always_fail)

    response = client.post(
        "/api/v1/webhooks/dispatch",
        json={"limit": 10, "max_attempts": 1, "base_backoff_seconds": 1},
        headers={"x-api-key": api_key},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dead_lettered"] >= 1


def test_07_webhook_dlq_replay_requeues_delivery(runtime_ctx, monkeypatch):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["webhooks:write", "webhooks:read"])
    webhook_service = runtime_ctx["webhook_service"]

    client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://example.com/failing-target",
            "event_types": ["task.error"],
        },
        headers={"x-api-key": api_key},
    )
    client.post(
        "/api/v1/webhooks/trigger",
        json={"event_type": "task.error", "payload": {"run_id": "dlq"}},
        headers={"x-api-key": api_key},
    )

    async def _always_fail(delivery):
        del delivery
        return False, "simulated failure"

    monkeypatch.setattr(webhook_service, "_deliver_once", _always_fail)

    client.post(
        "/api/v1/webhooks/dispatch",
        json={"limit": 10, "max_attempts": 1, "base_backoff_seconds": 1},
        headers={"x-api-key": api_key},
    )

    dead_letter_list = client.get(
        "/api/v1/webhooks/deliveries?status=dead_letter",
        headers={"x-api-key": api_key},
    )
    delivery_id = dead_letter_list.json()[0]["delivery_id"]

    replay = client.post(
        f"/api/v1/webhooks/dlq/{delivery_id}/replay",
        headers={"x-api-key": api_key},
    )

    assert replay.status_code == 200
    assert replay.json()["status"] == "requeued"


def test_08_rate_limit_returns_429_and_retry_after(runtime_ctx):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["search:read"], rpm_limit=1, burst_limit=1)

    first = client.post(
        "/api/v1/search",
        json={"query": "first"},
        headers={"x-api-key": api_key},
    )
    second = client.post(
        "/api/v1/search",
        json={"query": "second"},
        headers={"x-api-key": api_key},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers.get("Retry-After") is not None
    assert second.json()["detail"]["error"]["code"] == "rate_limited"
