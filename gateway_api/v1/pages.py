from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from core.gateway_services.exceptions import IntegrationDependencyUnavailable, UpstreamIntegrationError
from core.gateway_services.oracle_adapter import get_oracle_adapter
from core.gateway_services.spark_adapter import get_spark_adapter
from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import GatewayPageGenerateRequest, GatewayPageGenerateResponse
from gateway_api.integration_tracing import record_integration_event
from gateway_api.metering import record_request
from gateway_api.rate_limiter import apply_rate_limit_headers, enforce_rate_limit

router = APIRouter(prefix="/pages", tags=["Gateway V1"])


@router.post(
    "/generate",
    response_model=GatewayPageGenerateResponse,
    responses={
        502: {"description": "upstream integration failed"},
        503: {"description": "integration dependency unavailable"},
    },
)
async def generate_page(
    request: Request,
    payload: GatewayPageGenerateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("pages:write")),
) -> GatewayPageGenerateResponse:
    start = time.perf_counter()
    status_code = 200
    trace_id = f"trc_{uuid.uuid4().hex[:14]}"

    await record_integration_event(
        trace_id=trace_id,
        flow="spark_page_generation",
        stage="request_received",
        status="started",
        context={"query": payload.query, "template": payload.template},
    )

    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)

        oracle_result = await get_oracle_adapter().search(payload.query, payload.oracle_limit)
        await record_integration_event(
            trace_id=trace_id,
            flow="oracle_search",
            stage="search",
            status="success",
            context={"results": len(oracle_result.get("results", []))},
        )

        page_result = await get_spark_adapter().generate_page(
            query=payload.query,
            template=payload.template,
            oracle_context=oracle_result,
        )
        await record_integration_event(
            trace_id=trace_id,
            flow="spark_page_generation",
            stage="generate",
            status="success",
            context={"page_id": page_result.get("page_id", "")},
        )

        return GatewayPageGenerateResponse(
            trace_id=trace_id,
            page_id=page_result.get("page_id", ""),
            query=payload.query,
            template=payload.template,
            title=page_result.get("title", "Generated Page"),
            summary=page_result.get("summary", ""),
            citations=page_result.get("citations", []),
            artifact=page_result.get("artifact", {}),
        )
    except IntegrationDependencyUnavailable as exc:
        status_code = 503
        await record_integration_event(
            trace_id=trace_id,
            flow="spark_page_generation",
            stage="generate",
            status="failed",
            context={"reason": str(exc)},
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "integration_dependency_unavailable",
                    "message": str(exc),
                }
            },
        ) from exc
    except UpstreamIntegrationError as exc:
        status_code = 502
        await record_integration_event(
            trace_id=trace_id,
            flow="spark_page_generation",
            stage="generate",
            status="failed",
            context={"reason": str(exc)},
        )
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "upstream_integration_failed", "message": str(exc)}},
        ) from exc
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 502
        await record_integration_event(
            trace_id=trace_id,
            flow="spark_page_generation",
            stage="generate",
            status="failed",
            context={"reason": str(exc)},
        )
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "upstream_integration_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, auth_context.key_id, status_code, start)
