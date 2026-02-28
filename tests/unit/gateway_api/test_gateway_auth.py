import asyncio

import pytest
from fastapi import HTTPException

from gateway_api.auth import (
    AuthContext,
    _extract_api_key,
    ensure_scope,
    require_admin,
    require_api_key,
)


class _DummyStore:
    def __init__(self, record=None):
        self.record = record

    async def validate_api_key(self, plaintext: str):  # noqa: ARG002
        return self.record


def test_gateway_auth_parses_x_api_key_and_bearer(monkeypatch):
    record = {
        "key_id": "gwk_test",
        "scopes": ["search:read"],
        "rpm_limit": 100,
        "burst_limit": 50,
    }
    monkeypatch.setattr("gateway_api.auth.get_gateway_key_store", lambda: _DummyStore(record))

    assert _extract_api_key("abc", "Bearer ignored") == "abc"
    assert _extract_api_key(None, "Bearer mytoken") == "mytoken"

    context = asyncio.run(require_api_key(None, x_api_key="abc", authorization=None))
    assert context.key_id == "gwk_test"


def test_gateway_auth_rejects_missing_or_invalid_key(monkeypatch):
    monkeypatch.setattr("gateway_api.auth.get_gateway_key_store", lambda: _DummyStore(None))

    with pytest.raises(HTTPException) as missing_exc:
        asyncio.run(require_api_key(None, x_api_key=None, authorization=None))
    assert missing_exc.value.status_code == 401

    with pytest.raises(HTTPException) as invalid_exc:
        asyncio.run(require_api_key(None, x_api_key="bad", authorization=None))
    assert invalid_exc.value.status_code == 401


def test_gateway_scope_enforcement_returns_403_for_missing_scope():
    context = AuthContext(
        key_id="gwk_test",
        scopes=["search:read"],
        rpm_limit=100,
        burst_limit=50,
    )

    with pytest.raises(HTTPException) as exc:
        ensure_scope(context, "memory:write")

    assert exc.value.status_code == 403


def test_require_admin_fails_closed_when_admin_key_not_configured(monkeypatch):
    monkeypatch.delenv("ARCTURUS_GATEWAY_ADMIN_KEY", raising=False)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_admin(x_gateway_admin_key="anything"))

    assert exc.value.status_code == 503
    assert exc.value.detail["error"]["code"] == "admin_key_not_configured"
