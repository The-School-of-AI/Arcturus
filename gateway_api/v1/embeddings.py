from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from core.gateway_services.embeddings_service import create_embeddings
from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import GatewayEmbeddingsRequest, GatewayEmbeddingsResponse
from gateway_api.metering import record_request
from gateway_api.rate_limiter import enforce_rate_limit_and_usage_governance
from gateway_api.usage_governance import is_usage_quota_exception

router = APIRouter(prefix="/embeddings", tags=["Gateway V1"])


@router.post("", response_model=GatewayEmbeddingsResponse)
async def embeddings(
    request: Request,
    payload: GatewayEmbeddingsRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("embeddings:write")),
) -> GatewayEmbeddingsResponse:
    start = time.perf_counter()
    status_code = 200
    usage_units = 2
    governance_denied = False

    try:
        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
            estimated_units=2,
        )
        usage_units = usage_decision.estimated_units

        inputs = [payload.input] if isinstance(payload.input, str) else payload.input
        result = await create_embeddings(inputs, payload.model)
        return GatewayEmbeddingsResponse(**result)

    except HTTPException as exc:
        status_code = exc.status_code
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "embedding_failed", "message": str(exc)}},
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
