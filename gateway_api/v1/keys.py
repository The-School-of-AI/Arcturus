from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder

from gateway_api.auth import require_admin
from gateway_api.contracts import (
    GatewayAPIKeyCreateRequest,
    GatewayAPIKeyCreateResponse,
    GatewayAPIKeyOut,
    GatewayAPIKeyUpdateRequest,
)
from gateway_api.idempotency import (
    begin_idempotent_request,
    finalize_idempotent_failure,
    finalize_idempotent_success,
)
from gateway_api.key_store import get_gateway_key_store
from gateway_api.metering import record_request

router = APIRouter(prefix="/keys", tags=["Gateway V1"])
IDEMPOTENCY_HEADER = "Idempotency-Key"


def _to_public(record: dict) -> GatewayAPIKeyOut:
    return GatewayAPIKeyOut(
        key_id=record["key_id"],
        name=record["name"],
        scopes=record.get("scopes", []),
        rpm_limit=record.get("rpm_limit", 120),
        burst_limit=record.get("burst_limit", 60),
        monthly_request_quota=record.get("monthly_request_quota", 100_000),
        monthly_unit_quota=record.get("monthly_unit_quota", 500_000),
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
    response: Response,
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayAPIKeyCreateResponse:
    start = time.perf_counter()
    status_code = 200
    billable_request = True
    idempotency_context = None
    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor="admin",
            idempotency_key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            response=response,
        )
        if replay is not None:
            billable_request = False
            status_code = replay.status_code
            return replay

        record, plaintext = await get_gateway_key_store().create_key(
            name=payload.name,
            scopes=payload.scopes,
            rpm_limit=payload.rpm_limit,
            burst_limit=payload.burst_limit,
            monthly_request_quota=payload.monthly_request_quota,
            monthly_unit_quota=payload.monthly_unit_quota,
        )
        result = GatewayAPIKeyCreateResponse(api_key=plaintext, key=_to_public(record))

        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=jsonable_encoder(result),
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": idempotency_context.idempotency_key,
                },
            )

        return result
    except HTTPException as exc:
        status_code = exc.status_code
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=exc.status_code,
                detail=exc.detail,
            )
        raise
    finally:
        await record_request(
            request,
            "admin",
            status_code,
            start,
            units=2,
            billable=billable_request,
        )


@router.patch("/{key_id}", response_model=GatewayAPIKeyOut, dependencies=[Depends(require_admin)])
async def update_key(
    key_id: str,
    request: Request,
    payload: GatewayAPIKeyUpdateRequest,
    response: Response,
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayAPIKeyOut:
    start = time.perf_counter()
    status_code = 200
    billable_request = True
    idempotency_context = None
    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor="admin",
            idempotency_key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            response=response,
        )
        if replay is not None:
            billable_request = False
            status_code = replay.status_code
            return replay

        record = await get_gateway_key_store().update_key(
            key_id,
            name=payload.name,
            scopes=payload.scopes,
            rpm_limit=payload.rpm_limit,
            burst_limit=payload.burst_limit,
            monthly_request_quota=payload.monthly_request_quota,
            monthly_unit_quota=payload.monthly_unit_quota,
            status=payload.status,
        )
        if record is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "key_not_found", "message": "API key not found"}},
            )

        result = _to_public(record)
        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=jsonable_encoder(result),
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": idempotency_context.idempotency_key,
                },
            )
        return result
    except HTTPException as exc:
        status_code = exc.status_code
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=exc.status_code,
                detail=exc.detail,
            )
        raise
    finally:
        await record_request(
            request,
            "admin",
            status_code,
            start,
            units=2,
            billable=billable_request,
        )


@router.post("/{key_id}/rotate", response_model=GatewayAPIKeyCreateResponse, dependencies=[Depends(require_admin)])
async def rotate_key(
    key_id: str,
    request: Request,
    response: Response,
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayAPIKeyCreateResponse:
    start = time.perf_counter()
    status_code = 200
    billable_request = True
    idempotency_context = None
    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor="admin",
            idempotency_key=idempotency_key,
            payload={"key_id": key_id},
            response=response,
        )
        if replay is not None:
            billable_request = False
            status_code = replay.status_code
            return replay

        record, plaintext = await get_gateway_key_store().rotate_key(key_id)
        if record is None or plaintext is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "key_not_found", "message": "API key not found"}},
            )

        result = GatewayAPIKeyCreateResponse(api_key=plaintext, key=_to_public(record))
        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=jsonable_encoder(result),
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": idempotency_context.idempotency_key,
                },
            )
        return result
    except HTTPException as exc:
        status_code = exc.status_code
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=exc.status_code,
                detail=exc.detail,
            )
        raise
    finally:
        await record_request(
            request,
            "admin",
            status_code,
            start,
            units=2,
            billable=billable_request,
        )


@router.delete("/{key_id}", response_model=GatewayAPIKeyOut, dependencies=[Depends(require_admin)])
async def revoke_key(
    key_id: str,
    request: Request,
    response: Response,
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayAPIKeyOut:
    start = time.perf_counter()
    status_code = 200
    billable_request = True
    idempotency_context = None
    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor="admin",
            idempotency_key=idempotency_key,
            payload={"key_id": key_id},
            response=response,
        )
        if replay is not None:
            billable_request = False
            status_code = replay.status_code
            return replay

        record = await get_gateway_key_store().revoke_key(key_id)
        if record is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "key_not_found", "message": "API key not found"}},
            )

        result = _to_public(record)
        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=jsonable_encoder(result),
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": idempotency_context.idempotency_key,
                },
            )
        return result
    except HTTPException as exc:
        status_code = exc.status_code
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=exc.status_code,
                detail=exc.detail,
            )
        raise
    finally:
        await record_request(
            request,
            "admin",
            status_code,
            start,
            units=2,
            billable=billable_request,
        )
