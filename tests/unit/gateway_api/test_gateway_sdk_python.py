import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "api" / "sdks" / "python"))
from gateway_sdk.client import GatewayClient


def _response(status_code: int, body: dict, headers: dict | None = None) -> httpx.Response:
    request = httpx.Request("POST", "http://localhost")
    return httpx.Response(
        status_code=status_code,
        request=request,
        content=json.dumps(body).encode("utf-8"),
        headers=headers or {"content-type": "application/json"},
    )


def test_python_sdk_adds_idempotency_key_for_mutating_calls(monkeypatch):
    client = GatewayClient(base_url="http://example.com", api_key="api-key")
    captured = {}

    def _fake_request(method, url, headers=None, json=None, params=None):  # noqa: ANN001
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["json"] = json
        captured["params"] = params
        return _response(
            200,
            {"status": "ok"},
            headers={
                "content-type": "application/json",
                "X-Idempotency-Status": "created",
                "X-Idempotency-Key": headers.get("Idempotency-Key", ""),
                "X-Usage-Month": "2026-03",
                "X-RateLimit-Limit": "120",
            },
        )

    monkeypatch.setattr(client._client, "request", _fake_request)

    result = client.pages_generate("demo", template="overview")

    assert captured["headers"]["x-api-key"] == "api-key"
    assert captured["headers"].get("Idempotency-Key")
    assert result.metadata.idempotency_status == "created"
    assert result.metadata.usage_headers["x-usage-month"] == "2026-03"

    client.close()
