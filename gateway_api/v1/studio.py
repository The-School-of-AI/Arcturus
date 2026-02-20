from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import GatewayStudioGenerateRequest, GatewayStudioGenerateResponse
from gateway_api.metering import record_request
from gateway_api.rate_limiter import apply_rate_limit_headers, enforce_rate_limit

router = APIRouter(prefix="/studio", tags=["Gateway V1"])


async def _not_implemented(
    request: Request,
    response: Response,
    auth_context: AuthContext,
) -> None:
    start = time.perf_counter()
    status_code = 501
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)
        raise HTTPException(
            status_code=501,
            detail={
                "error": {
                    "code": "not_implemented",
                    "message": "Studio API contract is defined but implementation is pending.",
                }
            },
        )
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.post("/slides", response_model=GatewayStudioGenerateResponse)
async def generate_slides(
    request: Request,
    payload: GatewayStudioGenerateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("studio:write")),
) -> GatewayStudioGenerateResponse:
    del payload
    await _not_implemented(request, response, auth_context)
    raise AssertionError("unreachable")


@router.post("/docs", response_model=GatewayStudioGenerateResponse)
async def generate_docs(
    request: Request,
    payload: GatewayStudioGenerateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("studio:write")),
) -> GatewayStudioGenerateResponse:
    del payload
    await _not_implemented(request, response, auth_context)
    raise AssertionError("unreachable")


@router.post("/sheets", response_model=GatewayStudioGenerateResponse)
async def generate_sheets(
    request: Request,
    payload: GatewayStudioGenerateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("studio:write")),
) -> GatewayStudioGenerateResponse:
    del payload
    await _not_implemented(request, response, auth_context)
    raise AssertionError("unreachable")
