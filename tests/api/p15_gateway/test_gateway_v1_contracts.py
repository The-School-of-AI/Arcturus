import hashlib
import hmac
import json
import time


def test_post_search_requires_scope_and_returns_typed_citations(gateway_test_client):
    client, create_api_key, _, _ = gateway_test_client
    api_key = create_api_key(["search:read"])

    response = client.post(
        "/api/v1/search",
        json={"query": "latest ai news", "limit": 3},
        headers={"x-api-key": api_key},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["results"][0]["url"] == "https://example.com"
    assert payload["citations"] == ["https://example.com"]


def test_post_chat_completions_stream_true_returns_controlled_error(gateway_test_client):
    client, create_api_key, _, _ = gateway_test_client
    api_key = create_api_key(["chat:write"])

    response = client.post(
        "/api/v1/chat/completions",
        json={
            "model": "test-model",
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
        headers={"x-api-key": api_key},
    )

    assert response.status_code == 501
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "stream_not_supported"


def test_post_embeddings_returns_openai_like_shape(gateway_test_client):
    client, create_api_key, _, _ = gateway_test_client
    api_key = create_api_key(["embeddings:write"])

    response = client.post(
        "/api/v1/embeddings",
        json={"input": "hello embeddings"},
        headers={"x-api-key": api_key},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "list"
    assert payload["data"][0]["object"] == "embedding"
    assert isinstance(payload["data"][0]["embedding"], list)


def test_memory_scope_enforcement(gateway_test_client):
    client, create_api_key, _, _ = gateway_test_client
    api_key = create_api_key(["memory:read"])

    read_response = client.post(
        "/api/v1/memory/read",
        json={"limit": 5},
        headers={"x-api-key": api_key},
    )
    assert read_response.status_code == 200

    write_response = client.post(
        "/api/v1/memory/write",
        json={"text": "should fail", "source": "test", "category": "general"},
        headers={"x-api-key": api_key},
    )
    assert write_response.status_code == 403


def test_cron_jobs_create_list_delete_maps_to_scheduler(gateway_test_client):
    client, create_api_key, _, _ = gateway_test_client
    api_key = create_api_key(["cron:read", "cron:write"])

    create_response = client.post(
        "/api/v1/cron/jobs",
        json={
            "name": "Daily Summary",
            "cron": "0 9 * * *",
            "agent_type": "PlannerAgent",
            "query": "summarize updates",
        },
        headers={"x-api-key": api_key},
    )
    assert create_response.status_code == 200
    job_id = create_response.json()["id"]
    assert create_response.json()["cron_expression"] == "0 9 * * *"

    list_response = client.get("/api/v1/cron/jobs", headers={"x-api-key": api_key})
    assert list_response.status_code == 200
    assert any(job["id"] == job_id for job in list_response.json())

    delete_response = client.delete(f"/api/v1/cron/jobs/{job_id}", headers={"x-api-key": api_key})
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"


def test_pages_generate_returns_trace_and_citations(gateway_test_client):
    client, create_api_key, _, integration_events_file = gateway_test_client
    api_key = create_api_key(["pages:write"])

    response = client.post(
        "/api/v1/pages/generate",
        json={"query": "AI cloud trends", "template": "overview"},
        headers={"x-api-key": api_key},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["page_id"] == "page_test_1"
    assert payload["trace_id"].startswith("trc_")
    assert payload["citations"] == ["https://example.com"]

    trace_rows = integration_events_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(trace_rows) >= 2


def test_studio_generate_endpoints_return_typed_outline(gateway_test_client):
    client, create_api_key, _, _ = gateway_test_client
    api_key = create_api_key(["studio:write"])

    for endpoint, artifact_type in [
        ("/api/v1/studio/slides", "slides"),
        ("/api/v1/studio/docs", "document"),
        ("/api/v1/studio/sheets", "sheet"),
    ]:
        response = client.post(
            endpoint,
            json={"prompt": "Generate quarterly report outline"},
            headers={"x-api-key": api_key},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["artifact_id"] == "artifact_test_1"
        assert payload["artifact_type"] == artifact_type
        assert payload["trace_id"].startswith("trc_")
        assert payload["outline"]["title"] == "Generated Artifact"


def test_webhook_routes_exist_and_return_contract_shape(gateway_test_client):
    client, create_api_key, _, _ = gateway_test_client
    api_key = create_api_key(["webhooks:write", "webhooks:read"])

    create_response = client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://example.com/webhook",
            "event_types": ["task.complete"],
        },
        headers={"x-api-key": api_key},
    )
    assert create_response.status_code == 200
    sub_id = create_response.json()["id"]

    list_response = client.get("/api/v1/webhooks", headers={"x-api-key": api_key})
    assert list_response.status_code == 200
    assert any(item["id"] == sub_id for item in list_response.json())

    trigger_response = client.post(
        "/api/v1/webhooks/trigger",
        json={"event_type": "task.complete", "payload": {"run_id": "123"}},
        headers={"x-api-key": api_key},
    )
    assert trigger_response.status_code == 200
    assert trigger_response.json()["status"] == "queued"


def test_webhook_inbound_signature_and_dispatch_lifecycle(gateway_test_client, monkeypatch):
    client, create_api_key, webhook_service, _ = gateway_test_client
    api_key = create_api_key(["webhooks:write", "webhooks:read"])

    create_response = client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://example.com/receiver",
            "event_types": ["task.complete"],
        },
        headers={"x-api-key": api_key},
    )
    assert create_response.status_code == 200

    monkeypatch.setenv("ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET", "super-secret")
    inbound_payload = {"event_type": "task.complete", "payload": {"run_id": "abc"}}
    body = json.dumps(inbound_payload)
    timestamp = str(int(time.time()))
    signature = "sha256=" + hmac.new(
        b"super-secret",
        f"{timestamp}.{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    bad_sig = client.post(
        "/api/v1/webhooks/inbound/github",
        content=body,
        headers={
            "content-type": "application/json",
            "x-gateway-signature": "sha256=bad",
            "x-gateway-timestamp": timestamp,
        },
    )
    assert bad_sig.status_code == 401

    good_sig = client.post(
        "/api/v1/webhooks/inbound/github",
        content=body,
        headers={
            "content-type": "application/json",
            "x-gateway-signature": signature,
            "x-gateway-timestamp": timestamp,
        },
    )
    assert good_sig.status_code == 200
    assert good_sig.json()["status"] == "accepted"

    async def _deliver_success(delivery):
        del delivery
        return True, None

    monkeypatch.setattr(webhook_service, "_deliver_once", _deliver_success)

    dispatch = client.post(
        "/api/v1/webhooks/dispatch",
        json={"limit": 50, "max_attempts": 2, "base_backoff_seconds": 1},
        headers={"x-api-key": api_key},
    )
    assert dispatch.status_code == 200
    assert dispatch.json()["delivered"] >= 1

    deliveries = client.get(
        "/api/v1/webhooks/deliveries",
        headers={"x-api-key": api_key},
    )
    assert deliveries.status_code == 200
    assert any(item["status"] == "delivered" for item in deliveries.json())


def test_webhook_dispatch_dead_letter_and_replay(gateway_test_client, monkeypatch):
    client, create_api_key, webhook_service, _ = gateway_test_client
    api_key = create_api_key(["webhooks:write", "webhooks:read"])

    client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://example.com/receiver",
            "event_types": ["task.error"],
        },
        headers={"x-api-key": api_key},
    )

    trigger = client.post(
        "/api/v1/webhooks/trigger",
        json={"event_type": "task.error", "payload": {"run_id": "dead"}},
        headers={"x-api-key": api_key},
    )
    assert trigger.status_code == 200

    async def _deliver_fail(delivery):
        del delivery
        return False, "connection refused"

    monkeypatch.setattr(webhook_service, "_deliver_once", _deliver_fail)

    dispatch = client.post(
        "/api/v1/webhooks/dispatch",
        json={"limit": 10, "max_attempts": 1, "base_backoff_seconds": 1},
        headers={"x-api-key": api_key},
    )
    assert dispatch.status_code == 200
    assert dispatch.json()["dead_lettered"] >= 1

    deliveries = client.get(
        "/api/v1/webhooks/deliveries?status=dead_letter",
        headers={"x-api-key": api_key},
    )
    assert deliveries.status_code == 200
    dead_letter_id = deliveries.json()[0]["delivery_id"]

    replay = client.post(
        f"/api/v1/webhooks/dlq/{dead_letter_id}/replay",
        headers={"x-api-key": api_key},
    )
    assert replay.status_code == 200
    assert replay.json()["status"] == "requeued"


def test_admin_routes_fail_closed_when_admin_key_not_configured(gateway_test_client, monkeypatch):
    monkeypatch.delenv("ARCTURUS_GATEWAY_ADMIN_KEY", raising=False)
    client, _, _, _ = gateway_test_client

    response = client.get(
        "/api/v1/keys",
        headers={"x-gateway-admin-key": "dev-admin-key-change-me"},
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "admin_key_not_configured"
