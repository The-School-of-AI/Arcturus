import asyncio

import pytest
from fastapi import HTTPException

import gateway_api.metering as metering_module
from gateway_api.auth import AuthContext
from gateway_api.metering import GatewayMeteringStore
from gateway_api.usage_governance import enforce_usage_governance


class _DummyURL:
    def __init__(self, path: str):
        self.path = path


class _DummyRequest:
    def __init__(self, method: str, path: str):
        self.method = method
        self.url = _DummyURL(path)


def test_usage_governance_allows_under_quota(monkeypatch, tmp_path):
    store = GatewayMeteringStore(events_file=tmp_path / "events.jsonl", data_dir=tmp_path)
    monkeypatch.setattr(metering_module, "_metering_store", store)

    auth_context = AuthContext(
        key_id="gwk_test",
        scopes=["search:read"],
        rpm_limit=120,
        burst_limit=60,
        monthly_request_quota=2,
        monthly_unit_quota=10,
    )

    decision = asyncio.run(
        enforce_usage_governance(_DummyRequest("POST", "/api/v1/search"), auth_context)
    )

    assert decision.request_limit == 2
    assert decision.request_remaining == 1
    assert decision.estimated_units == 1


def test_usage_governance_blocks_request_and_unit_quota(monkeypatch, tmp_path):
    store = GatewayMeteringStore(events_file=tmp_path / "events.jsonl", data_dir=tmp_path)
    monkeypatch.setattr(metering_module, "_metering_store", store)

    asyncio.run(
        store.record(
            key_id="gwk_test",
            method="POST",
            path="/api/v1/studio/docs",
            status_code=200,
            latency_ms=10.0,
            units=5,
        )
    )

    auth_context = AuthContext(
        key_id="gwk_test",
        scopes=["studio:write"],
        rpm_limit=120,
        burst_limit=60,
        monthly_request_quota=1,
        monthly_unit_quota=5,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            enforce_usage_governance(
                _DummyRequest("POST", "/api/v1/studio/docs"),
                auth_context,
            )
        )

    exc = exc_info.value
    assert exc.status_code == 429
    assert exc.detail["error"]["code"] == "usage_quota_exceeded"
    assert exc.headers["X-Usage-Requests-Limit"] == "1"
    assert exc.headers["X-Usage-Units-Limit"] == "5"
