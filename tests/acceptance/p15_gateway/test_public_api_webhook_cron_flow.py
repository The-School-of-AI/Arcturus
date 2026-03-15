import hashlib
import hmac
import json
import subprocess
import time
from pathlib import Path

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


def _auth_headers(api_key: str, idempotency_key: str | None = None) -> dict:
    headers = {"x-api-key": api_key}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def test_01_gateway_requires_api_key_for_protected_routes(runtime_ctx):
    client = runtime_ctx["client"]

    response = client.post(
        "/api/v1/pages/generate",
        json={"query": "test"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["error"]["code"] == "missing_api_key"


def test_02_mutating_route_requires_idempotency_key(runtime_ctx):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["pages:write"])

    response = client.post(
        "/api/v1/pages/generate",
        json={"query": "AI infra trends", "template": "overview"},
        headers=_auth_headers(api_key),
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "idempotency_key_required"


def test_03_pages_generate_is_idempotent_and_replays_without_duplicate_side_effects(runtime_ctx):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["pages:write"])

    first = client.post(
        "/api/v1/pages/generate",
        json={"query": "AI infra trends", "template": "overview"},
        headers=_auth_headers(api_key, "idem-pages-1"),
    )
    second = client.post(
        "/api/v1/pages/generate",
        json={"query": "AI infra trends", "template": "overview"},
        headers=_auth_headers(api_key, "idem-pages-1"),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.headers["X-Idempotency-Status"] == "created"
    assert second.headers["X-Idempotency-Status"] == "replayed"

    assert runtime_ctx["state"]["oracle_calls"] == 1
    assert runtime_ctx["state"]["spark_calls"] == 1


def test_04_studio_docs_happy_path_returns_outline(runtime_ctx):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["studio:write"])

    response = client.post(
        "/api/v1/studio/docs",
        json={"prompt": "Create architecture decision record"},
        headers=_auth_headers(api_key, "idem-studio-docs-1"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_type"] == "document"
    assert payload["outline"]["title"] == "Document Outline"


def test_05_webhook_inbound_rejects_invalid_signature(runtime_ctx, monkeypatch):
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


def test_06_webhook_inbound_dedupes_replayed_events(runtime_ctx, monkeypatch):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["webhooks:write", "webhooks:read"])

    client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://example.com/inbound",
            "event_types": ["task.complete"],
        },
        headers=_auth_headers(api_key, "idem-sub-create"),
    )

    monkeypatch.setenv("ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET", "phase2-secret")

    body = json.dumps({"event_type": "task.complete", "payload": {"run_id": "123"}})
    timestamp = str(int(time.time()))
    headers = _signed_headers("phase2-secret", body, timestamp)

    first = client.post("/api/v1/webhooks/inbound/github", content=body, headers=headers)
    second = client.post("/api/v1/webhooks/inbound/github", content=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert second.headers["X-Idempotency-Status"] == "replayed"

    deliveries = client.get(
        "/api/v1/webhooks/deliveries?status=queued",
        headers=_auth_headers(api_key),
    )
    assert deliveries.status_code == 200
    assert len(deliveries.json()) == 1


def test_07_webhook_dispatch_retries_then_dead_letters(runtime_ctx, monkeypatch):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["webhooks:write", "webhooks:read"])
    webhook_service = runtime_ctx["webhook_service"]

    client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://example.com/failing-target",
            "event_types": ["task.error"],
        },
        headers=_auth_headers(api_key, "idem-subscription-dlq"),
    )
    client.post(
        "/api/v1/webhooks/trigger",
        json={"event_type": "task.error", "payload": {"run_id": "xyz"}},
        headers=_auth_headers(api_key, "idem-trigger-dlq"),
    )

    async def _always_fail(delivery):
        del delivery
        return False, "simulated failure"

    monkeypatch.setattr(webhook_service, "_deliver_once", _always_fail)

    response = client.post(
        "/api/v1/webhooks/dispatch",
        json={"limit": 10, "max_attempts": 1, "base_backoff_seconds": 1},
        headers=_auth_headers(api_key, "idem-dispatch-dlq"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dead_lettered"] >= 1


def test_08_webhook_dlq_replay_requeues_delivery(runtime_ctx, monkeypatch):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["webhooks:write", "webhooks:read"])
    webhook_service = runtime_ctx["webhook_service"]

    client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://example.com/failing-target",
            "event_types": ["task.error"],
        },
        headers=_auth_headers(api_key, "idem-sub-dlq-replay"),
    )
    client.post(
        "/api/v1/webhooks/trigger",
        json={"event_type": "task.error", "payload": {"run_id": "dlq"}},
        headers=_auth_headers(api_key, "idem-trigger-dlq-replay"),
    )

    async def _always_fail(delivery):
        del delivery
        return False, "simulated failure"

    monkeypatch.setattr(webhook_service, "_deliver_once", _always_fail)

    client.post(
        "/api/v1/webhooks/dispatch",
        json={"limit": 10, "max_attempts": 1, "base_backoff_seconds": 1},
        headers=_auth_headers(api_key, "idem-dispatch-dlq-replay"),
    )

    dead_letter_list = client.get(
        "/api/v1/webhooks/deliveries?status=dead_letter",
        headers=_auth_headers(api_key),
    )
    delivery_id = dead_letter_list.json()[0]["delivery_id"]

    replay = client.post(
        f"/api/v1/webhooks/dlq/{delivery_id}/replay",
        headers=_auth_headers(api_key, "idem-replay-dead-letter"),
    )

    assert replay.status_code == 200
    assert replay.json()["status"] == "requeued"


def test_09_rate_limit_returns_429_and_retry_after(runtime_ctx):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["search:read"], rpm_limit=1, burst_limit=1)

    first = client.post(
        "/api/v1/search",
        json={"query": "first"},
        headers=_auth_headers(api_key),
    )
    second = client.post(
        "/api/v1/search",
        json={"query": "second"},
        headers=_auth_headers(api_key),
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers.get("Retry-After") is not None
    assert second.json()["detail"]["error"]["code"] == "rate_limited"


def test_10_usage_governance_blocks_over_quota(runtime_ctx):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](
        ["search:read"],
        monthly_request_quota=1,
        monthly_unit_quota=100,
    )

    first = client.post(
        "/api/v1/search",
        json={"query": "quota first"},
        headers=_auth_headers(api_key),
    )
    second = client.post(
        "/api/v1/search",
        json={"query": "quota second"},
        headers=_auth_headers(api_key),
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"]["error"]["code"] == "usage_quota_exceeded"
    assert second.headers["X-Usage-Requests-Limit"] == "1"


def test_11_cron_timezone_and_history_are_exposed(runtime_ctx):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["cron:read", "cron:write"])

    created = client.post(
        "/api/v1/cron/jobs",
        json={
            "name": "Daily Summary",
            "cron": "0 9 * * *",
            "agent_type": "PlannerAgent",
            "query": "summarize updates",
            "timezone": "UTC",
        },
        headers=_auth_headers(api_key, "idem-cron-create"),
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["timezone"] == "UTC"

    job_id = payload["id"]
    triggered = client.post(
        f"/api/v1/cron/jobs/{job_id}/trigger",
        headers=_auth_headers(api_key, "idem-cron-trigger"),
    )
    assert triggered.status_code == 200

    history = client.get(
        f"/api/v1/cron/jobs/{job_id}/history?limit=5",
        headers=_auth_headers(api_key),
    )
    assert history.status_code == 200
    rows = history.json()
    assert rows[0]["job_id"] == job_id
    assert rows[0]["status"] in {"success", "failed"}


def test_12_connector_ingestion_supports_github_jira_gmail(runtime_ctx):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["webhooks:write", "webhooks:read"])
    connector_headers = runtime_ctx["connector_headers"]

    client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://example.com/inbound",
            "event_types": ["memory.updated", "task.complete", "task.error"],
        },
        headers=_auth_headers(api_key, "idem-connectors-sub"),
    )

    github_payload = {"ref": "refs/heads/main", "after": "sha"}
    github_response = client.post(
        "/api/v1/webhooks/inbound/github",
        content=json.dumps(github_payload),
        headers=connector_headers("github", github_payload, event_name="push"),
    )
    assert github_response.status_code == 200
    assert github_response.json()["auth_mode"] == "github_signature"
    assert github_response.json()["normalized_event_type"] == "memory.updated"

    jira_payload = {"webhookEvent": "jira:issue_created", "issue": {"id": "JIRA-1", "key": "JIRA-1"}}
    jira_response = client.post(
        "/api/v1/webhooks/inbound/jira",
        content=json.dumps(jira_payload),
        headers=connector_headers("jira", jira_payload),
    )
    assert jira_response.status_code == 200
    assert jira_response.json()["auth_mode"] == "jira_token"
    assert jira_response.json()["normalized_event_type"] == "task.complete"

    gmail_payload = {"emailAddress": "dev@example.com", "historyId": "100"}
    gmail_response = client.post(
        "/api/v1/webhooks/inbound/gmail",
        content=json.dumps(gmail_payload),
        headers=connector_headers("gmail", gmail_payload),
    )
    assert gmail_response.status_code == 200
    assert gmail_response.json()["auth_mode"] == "gmail_token"
    assert gmail_response.json()["normalized_event_type"] == "memory.updated"


def test_13_full_public_api_demonstration_flow(runtime_ctx, monkeypatch):
    client = runtime_ctx["client"]
    connector_headers = runtime_ctx["connector_headers"]
    monkeypatch.setenv("ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET", "phase3-secret")
    api_key = runtime_ctx["create_api_key"](
        [
            "search:read",
            "chat:write",
            "embeddings:write",
            "memory:read",
            "memory:write",
            "agents:run",
            "pages:write",
            "studio:write",
            "cron:read",
            "cron:write",
            "webhooks:write",
            "webhooks:read",
            "usage:read",
        ],
        monthly_request_quota=200,
        monthly_unit_quota=1000,
    )

    assert client.post("/api/v1/search", json={"query": "gateway demo"}, headers=_auth_headers(api_key)).status_code == 200
    assert client.post(
        "/api/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "summarize gateway state"}]},
        headers=_auth_headers(api_key),
    ).status_code == 200
    assert client.post("/api/v1/embeddings", json={"input": "gateway vector"}, headers=_auth_headers(api_key)).status_code == 200
    assert client.post(
        "/api/v1/memory/write",
        json={"text": "gateway acceptance memory", "source": "acceptance", "category": "qa"},
        headers=_auth_headers(api_key, "idem-acceptance-memory-write"),
    ).status_code == 200
    assert client.post("/api/v1/memory/read", json={"limit": 5}, headers=_auth_headers(api_key)).status_code == 200
    assert client.post(
        "/api/v1/agents/run",
        json={"query": "demo run", "wait_for_completion": True},
        headers=_auth_headers(api_key, "idem-acceptance-agent"),
    ).status_code == 200
    assert client.post(
        "/api/v1/pages/generate",
        json={"query": "acceptance page"},
        headers=_auth_headers(api_key, "idem-acceptance-page"),
    ).status_code == 200
    assert client.post(
        "/api/v1/studio/slides",
        json={"prompt": "acceptance slides"},
        headers=_auth_headers(api_key, "idem-acceptance-slides"),
    ).status_code == 200

    cron_create = client.post(
        "/api/v1/cron/jobs",
        json={
            "name": "Acceptance Cron",
            "cron": "0 9 * * *",
            "agent_type": "PlannerAgent",
            "query": "acceptance cron query",
            "timezone": "UTC",
        },
        headers=_auth_headers(api_key, "idem-acceptance-cron-create"),
    )
    assert cron_create.status_code == 200
    cron_job_id = cron_create.json()["id"]
    assert client.post(
        f"/api/v1/cron/jobs/{cron_job_id}/trigger",
        headers=_auth_headers(api_key, "idem-acceptance-cron-trigger"),
    ).status_code == 200
    assert client.get(
        f"/api/v1/cron/jobs/{cron_job_id}/history?limit=5",
        headers=_auth_headers(api_key),
    ).status_code == 200

    assert client.get("/api/v1/webhooks/connectors", headers=_auth_headers(api_key)).status_code == 200
    assert client.post(
        "/api/v1/webhooks",
        json={"target_url": "https://example.com/inbound", "event_types": ["task.complete", "memory.updated"]},
        headers=_auth_headers(api_key, "idem-acceptance-webhook-sub"),
    ).status_code == 200
    assert client.post(
        "/api/v1/webhooks/trigger",
        json={"event_type": "task.complete", "payload": {"run_id": "acceptance"}},
        headers=_auth_headers(api_key, "idem-acceptance-webhook-trigger"),
    ).status_code == 200

    github_payload = {"ref": "refs/heads/main", "after": "abc"}
    assert client.post(
        "/api/v1/webhooks/inbound/github",
        content=json.dumps(github_payload),
        headers=connector_headers("github", github_payload, event_name="push"),
    ).status_code == 200

    assert client.post(
        "/api/v1/webhooks/dispatch",
        json={"limit": 10, "max_attempts": 1, "base_backoff_seconds": 1},
        headers=_auth_headers(api_key, "idem-acceptance-webhook-dispatch"),
    ).status_code == 200
    assert client.get("/api/v1/webhooks/deliveries", headers=_auth_headers(api_key)).status_code == 200
    assert client.get("/api/v1/usage", headers=_auth_headers(api_key)).status_code == 200


def test_14_demo_script_smoke_mode_executes():
    root = Path(__file__).resolve().parents[3]
    script = root / "scripts" / "demos" / "p15_gateway.sh"
    result = subprocess.run(
        ["bash", str(script), "--smoke"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "p15_gateway smoke passed" in result.stdout


def test_15_gateway_overhead_p95_under_300ms(runtime_ctx):
    client = runtime_ctx["client"]
    api_key = runtime_ctx["create_api_key"](["search:read"], monthly_request_quota=500, monthly_unit_quota=1000)

    latencies_ms = []
    for index in range(40):
        start = time.perf_counter()
        response = client.post(
            "/api/v1/search",
            json={"query": f"latency-check-{index}"},
            headers=_auth_headers(api_key),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        assert response.status_code == 200
        latencies_ms.append(elapsed_ms)

    latencies_ms.sort()
    p95_index = max(int(len(latencies_ms) * 0.95) - 1, 0)
    p95_ms = latencies_ms[p95_index]
    assert p95_ms < 300.0, f"p95={p95_ms:.2f}ms"
