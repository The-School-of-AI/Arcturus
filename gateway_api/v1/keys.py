from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request

from gateway_api.auth import require_admin
from gateway_api.contracts import (
    GatewayAPIKeyCreateRequest,
    GatewayAPIKeyCreateResponse,
    GatewayAPIKeyOut,
    GatewayAPIKeyUpdateRequest,
)
from gateway_api.key_store import get_gateway_key_store
from gateway_api.metering import record_request

router = APIRouter(prefix="/keys", tags=["Gateway V1"])


def _to_public(record: dict) -> GatewayAPIKeyOut:
    return GatewayAPIKeyOut(
        key_id=record["key_id"],
        name=record["name"],
        scopes=record.get("scopes", []),
        rpm_limit=record.get("rpm_limit", 120),
        burst_limit=record.get("burst_limit", 60),
        status=record.get("status", "active"),
        secret_prefix=record.get("secret_prefix", ""),
        created_at=record.get("created_at", ""),
        updated_at=record.get("updated_at", ""),
    )


@router.get("", response_model=list[GatewayAPIKeyOut], dependencies=[Depends(require_admin)])
async def list_keys(
    request: Request,
    include_revoked: bool = False,
) -> list[GatewayAPIKeyOut]:
    start = time.perf_counter()
    status_code = 200
    try:
        keys = await get_gateway_key_store().list_keys(include_revoked=include_revoked)
        return [_to_public(item) for item in keys]
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        await record_request(request, "admin", status_code, start)


@router.post("", response_model=GatewayAPIKeyCreateResponse, dependencies=[Depends(require_admin)])
async def create_key(
    request: Request,
    payload: GatewayAPIKeyCreateRequest,
) -> GatewayAPIKeyCreateResponse:
    start = time.perf_counter()
    status_code = 200
    try:
        record, plaintext = await get_gateway_key_store().create_key(
            name=payload.name,
            scopes=payload.scopes,
            rpm_limit=payload.rpm_limit,
            burst_limit=payload.burst_limit,
        )
        return GatewayAPIKeyCreateResponse(api_key=plaintext, key=_to_public(record))
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        await record_request(request, "admin", status_code, start)


@router.patch("/{key_id}", response_model=GatewayAPIKeyOut, dependencies=[Depends(require_admin)])
async def update_key(
    key_id: str,
    request: Request,
    payload: GatewayAPIKeyUpdateRequest,
) -> GatewayAPIKeyOut:
    start = time.perf_counter()
    status_code = 200
    try:
        record = await get_gateway_key_store().update_key(
            key_id,
            name=payload.name,
            scopes=payload.scopes,
            rpm_limit=payload.rpm_limit,
            burst_limit=payload.burst_limit,
            status=payload.status,
        )
        if record is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "key_not_found", "message": "API key not found"}},
            )
        return _to_public(record)
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        await record_request(request, "admin", status_code, start)


@router.post("/{key_id}/rotate", response_model=GatewayAPIKeyCreateResponse, dependencies=[Depends(require_admin)])
async def rotate_key(
    key_id: str,
    request: Request,
) -> GatewayAPIKeyCreateResponse:
    start = time.perf_counter()
    status_code = 200
    try:
        record, plaintext = await get_gateway_key_store().rotate_key(key_id)
        if record is None or plaintext is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "key_not_found", "message": "API key not found"}},
            )
        return GatewayAPIKeyCreateResponse(api_key=plaintext, key=_to_public(record))
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        await record_request(request, "admin", status_code, start)


@router.delete("/{key_id}", response_model=GatewayAPIKeyOut, dependencies=[Depends(require_admin)])
async def revoke_key(
    key_id: str,
    request: Request,
) -> GatewayAPIKeyOut:
    start = time.perf_counter()
    status_code = 200
    try:
        record = await get_gateway_key_store().revoke_key(key_id)
        if record is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "key_not_found", "message": "API key not found"}},
            )
        return _to_public(record)
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    finally:
        await record_request(request, "admin", status_code, start)
