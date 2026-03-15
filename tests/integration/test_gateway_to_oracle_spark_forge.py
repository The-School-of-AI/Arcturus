import json

from p15_gateway_runtime import build_gateway_runtime_context


def _auth_headers(api_key: str, idempotency_key: str | None = None) -> dict:
    headers = {"x-api-key": api_key}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def test_01_pages_generation_triggers_oracle_and_spark(monkeypatch, tmp_path):
    ctx = build_gateway_runtime_context(tmp_path, monkeypatch)
    client = ctx["client"]
    api_key = ctx["create_api_key"](["pages:write"])

    response = client.post(
        "/api/v1/pages/generate",
        json={"query": "Cloud cost optimization", "template": "analysis"},
        headers=_auth_headers(api_key, "idem-pages-01"),
    )

    assert response.status_code == 200
    assert ctx["state"]["oracle_calls"] == 1
    assert ctx["state"]["spark_calls"] == 1


def test_02_studio_generation_triggers_oracle_and_forge(monkeypatch, tmp_path):
    ctx = build_gateway_runtime_context(tmp_path, monkeypatch)
    client = ctx["client"]
    api_key = ctx["create_api_key"](["studio:write"])

    response = client.post(
        "/api/v1/studio/slides",
        json={"prompt": "Create launch deck"},
        headers=_auth_headers(api_key, "idem-studio-02"),
    )

    assert response.status_code == 200
    assert ctx["state"]["oracle_calls"] == 1
    assert ctx["state"]["forge_calls"] == 1


def test_03_replayed_mutating_requests_do_not_duplicate_upstream_calls(monkeypatch, tmp_path):
    ctx = build_gateway_runtime_context(tmp_path, monkeypatch)
    client = ctx["client"]
    api_key = ctx["create_api_key"](["pages:write"])

    first = client.post(
        "/api/v1/pages/generate",
        json={"query": "AI regulations"},
        headers=_auth_headers(api_key, "idem-replay-03"),
    )
    second = client.post(
        "/api/v1/pages/generate",
        json={"query": "AI regulations"},
        headers=_auth_headers(api_key, "idem-replay-03"),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert second.headers["X-Idempotency-Status"] == "replayed"
    assert ctx["state"]["oracle_calls"] == 1
    assert ctx["state"]["spark_calls"] == 1


def test_04_integration_traces_capture_oracle_spark_forge_lifecycle(monkeypatch, tmp_path):
    ctx = build_gateway_runtime_context(tmp_path, monkeypatch)
    client = ctx["client"]
    page_key = ctx["create_api_key"](["pages:write"])
    studio_key = ctx["create_api_key"](["studio:write"])

    client.post(
        "/api/v1/pages/generate",
        json={"query": "AI regulations"},
        headers=_auth_headers(page_key, "idem-trace-page"),
    )
    client.post(
        "/api/v1/studio/docs",
        json={"prompt": "Draft policy memo"},
        headers=_auth_headers(studio_key, "idem-trace-studio"),
    )

    rows = [
        json.loads(line)
        for line in ctx["integration_events"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    flows = {item["flow"] for item in rows}
    assert "oracle_search" in flows
    assert "spark_page_generation" in flows
    assert "forge_outline_generation" in flows
    assert any(item["status"] == "success" for item in rows)


def test_05_oracle_failure_propagates_to_pages_with_controlled_error(monkeypatch, tmp_path):
    ctx = build_gateway_runtime_context(tmp_path, monkeypatch, oracle_fail=True)
    client = ctx["client"]
    api_key = ctx["create_api_key"](["pages:write"])

    response = client.post(
        "/api/v1/pages/generate",
        json={"query": "Failure case"},
        headers=_auth_headers(api_key, "idem-failure-05"),
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "upstream_integration_failed"


def test_06_forge_failure_propagates_with_traceable_failure_record(monkeypatch, tmp_path):
    ctx = build_gateway_runtime_context(tmp_path, monkeypatch, forge_fail=True)
    client = ctx["client"]
    api_key = ctx["create_api_key"](["studio:write"])

    response = client.post(
        "/api/v1/studio/docs",
        json={"prompt": "Failure in forge"},
        headers=_auth_headers(api_key, "idem-failure-06"),
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "upstream_integration_failed"

    rows = [
        json.loads(line)
        for line in ctx["integration_events"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        row["flow"] == "forge_outline_generation" and row["status"] == "failed"
        for row in rows
    )


def test_07_connector_replay_does_not_duplicate_oracle_spark_forge_side_effects(monkeypatch, tmp_path):
    ctx = build_gateway_runtime_context(tmp_path, monkeypatch)
    client = ctx["client"]
    api_key = ctx["create_api_key"](["webhooks:write", "webhooks:read"])
    connector_headers = ctx["connector_headers"]

    client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://example.com/inbound",
            "event_types": ["memory.updated"],
        },
        headers=_auth_headers(api_key, "idem-connector-sub"),
    )

    payload = {"ref": "refs/heads/main", "after": "abc123"}
    headers = connector_headers("github", payload, event_name="push")

    first = client.post("/api/v1/webhooks/inbound/github", content=json.dumps(payload), headers=headers)
    second = client.post("/api/v1/webhooks/inbound/github", content=json.dumps(payload), headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.headers["X-Idempotency-Status"] == "replayed"
    assert ctx["state"]["oracle_calls"] == 0
    assert ctx["state"]["spark_calls"] == 0
    assert ctx["state"]["forge_calls"] == 0


def test_08_connector_inbound_records_traceable_validation_lifecycle(monkeypatch, tmp_path):
    ctx = build_gateway_runtime_context(tmp_path, monkeypatch)
    client = ctx["client"]
    api_key = ctx["create_api_key"](["webhooks:write", "webhooks:read"])
    connector_headers = ctx["connector_headers"]

    client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://example.com/inbound",
            "event_types": ["task.complete"],
        },
        headers=_auth_headers(api_key, "idem-connector-trace-sub"),
    )

    jira_payload = {
        "webhookEvent": "jira:issue_created",
        "issue": {"id": "ISSUE-1", "key": "ISSUE-1"},
    }
    response = client.post(
        "/api/v1/webhooks/inbound/jira",
        content=json.dumps(jira_payload),
        headers=connector_headers("jira", jira_payload),
    )
    assert response.status_code == 200
    assert response.json()["normalized_event_type"] == "task.complete"

    rows = [
        json.loads(line)
        for line in ctx["integration_events"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        row["flow"] == "webhook_inbound_validation"
        and row["status"] == "success"
        and row.get("context", {}).get("auth_mode") == "jira_token"
        for row in rows
    )
