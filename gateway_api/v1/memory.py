from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder

from core.gateway_services.memory_service import (
    read_memories as service_read_memories,
    search_memories as service_search_memories,
    write_memory as service_write_memory,
)
from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import (
    GatewayMemoryReadRequest,
    GatewayMemoryResponse,
    GatewayMemorySearchRequest,
    GatewayMemoryWriteRequest,
)
from gateway_api.idempotency import (
    begin_idempotent_request,
    finalize_idempotent_failure,
    finalize_idempotent_success,
)
from gateway_api.metering import record_request
from gateway_api.rate_limiter import enforce_rate_limit_and_usage_governance
from gateway_api.usage_governance import is_usage_quota_exception

router = APIRouter(prefix="/memory", tags=["Gateway V1"])
IDEMPOTENCY_HEADER = "Idempotency-Key"


@router.post("/read", response_model=GatewayMemoryResponse)
async def read_memory(
    request: Request,
    payload: GatewayMemoryReadRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("memory:read")),
) -> GatewayMemoryResponse:
    start = time.perf_counter()
    status_code = 200
    usage_units = 1
    governance_denied = False
    try:
        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
        )
        usage_units = usage_decision.estimated_units

        result = await service_read_memories(payload.category, payload.limit)
        return GatewayMemoryResponse(**result)
    except HTTPException as exc:
        status_code = exc.status_code
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "memory_read_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(
            request,
            auth_context.key_id,
            status_code,
            start,
            units=usage_units,
            governance_denied=governance_denied,
            billable=not governance_denied,
        )


@router.post("/write", response_model=dict)
async def write_memory(
    request: Request,
    payload: GatewayMemoryWriteRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("memory:write")),
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> dict:
    start = time.perf_counter()
    status_code = 200
    usage_units = 2
    governance_denied = False
    billable_request = True
    idempotency_context = None
    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor=auth_context.key_id,
            idempotency_key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            response=response,
        )
        if replay is not None:
            status_code = replay.status_code
            billable_request = False
            return replay

        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
            estimated_units=2,
        )
        usage_units = usage_decision.estimated_units

        result = await service_write_memory(payload.text, payload.source, payload.category)
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
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        detail = {"error": {"code": "memory_write_failed", "message": str(exc)}}
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=500,
                detail=detail,
            )
        raise HTTPException(status_code=500, detail=detail) from exc
    finally:
        await record_request(
            request,
            auth_context.key_id,
            status_code,
            start,
            units=usage_units,
            governance_denied=governance_denied,
            billable=billable_request and not governance_denied,
        )


@router.post("/search", response_model=GatewayMemoryResponse)
async def search_memories(
    request: Request,
    payload: GatewayMemorySearchRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("memory:read")),
) -> GatewayMemoryResponse:
    start = time.perf_counter()
    status_code = 200
    usage_units = 1
    governance_denied = False
    try:
        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
        )
        usage_units = usage_decision.estimated_units

        result = await service_search_memories(payload.query, payload.limit)
        return GatewayMemoryResponse(**result)
    except HTTPException as exc:
        status_code = exc.status_code
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "memory_search_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(
            request,
            auth_context.key_id,
            status_code,
            start,
            units=usage_units,
            governance_denied=governance_denied,
            billable=not governance_denied,
        )
