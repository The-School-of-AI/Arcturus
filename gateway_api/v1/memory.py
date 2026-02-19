from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response

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
from gateway_api.metering import record_request
from gateway_api.rate_limiter import apply_rate_limit_headers, enforce_rate_limit

router = APIRouter(prefix="/memory", tags=["Gateway V1"])


@router.post("/read", response_model=GatewayMemoryResponse)
async def read_memory(
    request: Request,
    payload: GatewayMemoryReadRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("memory:read")),
) -> GatewayMemoryResponse:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)

        result = await service_read_memories(payload.category, payload.limit)
        return GatewayMemoryResponse(**result)
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "memory_read_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.post("/write", response_model=dict)
async def write_memory(
    request: Request,
    payload: GatewayMemoryWriteRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("memory:write")),
) -> dict:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)
        return await service_write_memory(payload.text, payload.source, payload.category)
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "memory_write_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.post("/search", response_model=GatewayMemoryResponse)
async def search_memories(
    request: Request,
    payload: GatewayMemorySearchRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("memory:read")),
) -> GatewayMemoryResponse:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)

        result = await service_search_memories(payload.query, payload.limit)
        return GatewayMemoryResponse(**result)
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "memory_search_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, auth_context.key_id, status_code, start)
