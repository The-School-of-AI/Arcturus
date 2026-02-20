def test_post_search_requires_scope_and_returns_typed_citations(gateway_test_client):
    client, create_api_key = gateway_test_client
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
    client, create_api_key = gateway_test_client
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
    client, create_api_key = gateway_test_client
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
    client, create_api_key = gateway_test_client
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
    client, create_api_key = gateway_test_client
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


def test_webhook_routes_exist_and_return_contract_shape(gateway_test_client):
    client, create_api_key = gateway_test_client
    api_key = create_api_key(["webhooks:write"])

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


def test_admin_routes_fail_closed_when_admin_key_not_configured(gateway_test_client, monkeypatch):
    monkeypatch.delenv("ARCTURUS_GATEWAY_ADMIN_KEY", raising=False)
    client, _ = gateway_test_client

    response = client.get(
        "/api/v1/keys",
        headers={"x-gateway-admin-key": "dev-admin-key-change-me"},
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "admin_key_not_configured"
