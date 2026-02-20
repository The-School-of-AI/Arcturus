from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import GatewayPageGenerateRequest, GatewayPageGenerateResponse
from gateway_api.metering import record_request
from gateway_api.rate_limiter import apply_rate_limit_headers, enforce_rate_limit

router = APIRouter(prefix="/pages", tags=["Gateway V1"])


@router.post("/generate", response_model=GatewayPageGenerateResponse)
async def generate_page(
    request: Request,
    payload: GatewayPageGenerateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("pages:write")),
) -> GatewayPageGenerateResponse:
    del payload
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
                    "message": "Page generation API contract is defined but implementation is pending.",
                }
            },
        )
    finally:
        await record_request(request, auth_context.key_id, status_code, start)
