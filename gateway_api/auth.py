from __future__ import annotations

import os
from typing import Callable, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from gateway_api.key_store import get_gateway_key_store


class AuthContext(BaseModel):
    key_id: str
    scopes: list[str]
    rpm_limit: int
    burst_limit: int


def _error_payload(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _extract_api_key(x_api_key: str | None, authorization: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()

    if authorization:
        value = authorization.strip()
        if value.lower().startswith("bearer "):
            return value[7:].strip()

    return None


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
    authorization: str | None = Header(default=None),
) -> AuthContext:
    del request
    key = _extract_api_key(x_api_key, authorization)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_payload("missing_api_key", "Missing API key"),
        )

    record = await get_gateway_key_store().validate_api_key(key)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_payload("invalid_api_key", "Invalid API key"),
        )

    return AuthContext(
        key_id=record["key_id"],
        scopes=record.get("scopes", []),
        rpm_limit=record.get("rpm_limit", 120),
        burst_limit=record.get("burst_limit", 60),
    )


def ensure_scope(auth_context: AuthContext, required_scope: str) -> AuthContext:
    if required_scope not in auth_context.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_error_payload("missing_scope", f"Missing required scope: {required_scope}"),
        )
    return auth_context


def require_scope(required_scope: str) -> Callable[..., AuthContext]:
    async def _require_scope(
        auth_context: AuthContext = Depends(require_api_key),
    ) -> AuthContext:
        return ensure_scope(auth_context, required_scope)

    return _require_scope


ADMIN_HEADER_NAME = "x-gateway-admin-key"


def _expected_admin_key() -> str:
    return os.getenv("ARCTURUS_GATEWAY_ADMIN_KEY", "dev-admin-key-change-me")


async def require_admin(
    x_gateway_admin_key: Optional[str] = Header(default=None, alias=ADMIN_HEADER_NAME),
) -> None:
    expected = _expected_admin_key()
    if not x_gateway_admin_key or x_gateway_admin_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_payload("invalid_admin_key", "Invalid admin key"),
        )
