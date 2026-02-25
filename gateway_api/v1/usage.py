from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from gateway_api.auth import AuthContext, require_admin, require_scope
from gateway_api.metering import get_metering_store, record_request
from gateway_api.rate_limiter import enforce_rate_limit_and_usage_governance
from gateway_api.usage_governance import is_usage_quota_exception

router = APIRouter(prefix="/usage", tags=["Gateway V1"])


@router.get("", response_model=dict)
async def get_my_usage(
    request: Request,
    response: Response,
    month: str | None = None,
    auth_context: AuthContext = Depends(require_scope("usage:read")),
) -> dict:
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

        usage = await get_metering_store().get_usage_for_key(auth_context.key_id, month)
        return usage
    except HTTPException as exc:
        status_code = exc.status_code
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
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


@router.get("/all", response_model=dict, dependencies=[Depends(require_admin)])
async def get_all_usage(
    request: Request,
    month: str | None = None,
) -> dict:
    start = time.perf_counter()
    status_code = 200
    try:
        return await get_metering_store().get_usage_all(month)
    finally:
        await record_request(request, "admin", status_code, start)
