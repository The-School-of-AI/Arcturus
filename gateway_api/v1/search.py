from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from core.gateway_services.search_service import web_search
from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import GatewaySearchRequest, GatewaySearchResponse, GatewaySearchResult
from gateway_api.metering import record_request
from gateway_api.rate_limiter import enforce_rate_limit_and_usage_governance
from gateway_api.usage_governance import is_usage_quota_exception

router = APIRouter(prefix="/search", tags=["Gateway V1"])


@router.post("", response_model=GatewaySearchResponse)
async def search(
    request: Request,
    payload: GatewaySearchRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("search:read")),
) -> GatewaySearchResponse:
    start = time.perf_counter()
    status_code = 200
    usage_units = 1
    governance_denied = False

    try:
        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
            estimated_units=1,
        )
        usage_units = usage_decision.estimated_units

        internal_result = await web_search(payload.query, payload.limit)
        internal_items = internal_result.get("results", [])

        serialized = []
        for item in internal_items:
            content = item.get("content", "")
            serialized.append(
                GatewaySearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=content[:280],
                    content=content,
                    rank=item.get("rank", 0),
                )
            )

        return GatewaySearchResponse(
            query=payload.query,
            results=serialized,
            citations=[item.url for item in serialized if item.url],
        )

    except HTTPException as exc:
        status_code = exc.status_code
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "search_failed", "message": str(exc)}},
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
