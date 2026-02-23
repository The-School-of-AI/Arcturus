import json

from p15_gateway_runtime import build_gateway_runtime_context


def test_01_pages_generation_triggers_oracle_and_spark(monkeypatch, tmp_path):
    ctx = build_gateway_runtime_context(tmp_path, monkeypatch)
    client = ctx["client"]
    api_key = ctx["create_api_key"](["pages:write"])

    response = client.post(
        "/api/v1/pages/generate",
        json={"query": "Cloud cost optimization", "template": "analysis"},
        headers={"x-api-key": api_key},
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
        headers={"x-api-key": api_key},
    )

    assert response.status_code == 200
    assert ctx["state"]["oracle_calls"] == 1
    assert ctx["state"]["forge_calls"] == 1


def test_03_integration_traces_capture_oracle_spark_forge_lifecycle(monkeypatch, tmp_path):
    ctx = build_gateway_runtime_context(tmp_path, monkeypatch)
    client = ctx["client"]
    page_key = ctx["create_api_key"](["pages:write"])
    studio_key = ctx["create_api_key"](["studio:write"])

    client.post(
        "/api/v1/pages/generate",
        json={"query": "AI regulations"},
        headers={"x-api-key": page_key},
    )
    client.post(
        "/api/v1/studio/docs",
        json={"prompt": "Draft policy memo"},
        headers={"x-api-key": studio_key},
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


def test_04_oracle_failure_propagates_to_pages_with_controlled_error(monkeypatch, tmp_path):
    ctx = build_gateway_runtime_context(tmp_path, monkeypatch, oracle_fail=True)
    client = ctx["client"]
    api_key = ctx["create_api_key"](["pages:write"])

    response = client.post(
        "/api/v1/pages/generate",
        json={"query": "Failure case"},
        headers={"x-api-key": api_key},
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "upstream_integration_failed"


def test_05_forge_failure_propagates_with_traceable_failure_record(monkeypatch, tmp_path):
    ctx = build_gateway_runtime_context(tmp_path, monkeypatch, forge_fail=True)
    client = ctx["client"]
    api_key = ctx["create_api_key"](["studio:write"])

    response = client.post(
        "/api/v1/studio/docs",
        json={"prompt": "Failure in forge"},
        headers={"x-api-key": api_key},
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
