from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request

from gateway_api.auth import AuthContext, require_admin, require_scope
from gateway_api.metering import get_metering_store, record_request

router = APIRouter(prefix="/usage", tags=["Gateway V1"])


@router.get("", response_model=dict)
async def get_my_usage(
    request: Request,
    month: str | None = None,
    auth_context: AuthContext = Depends(require_scope("usage:read")),
) -> dict:
    start = time.perf_counter()
    status_code = 200
    try:
        usage = await get_metering_store().get_usage_for_key(auth_context.key_id, month)
        return usage
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


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
