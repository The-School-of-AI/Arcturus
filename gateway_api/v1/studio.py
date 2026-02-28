from __future__ import annotations

import time
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from core.gateway_services.exceptions import IntegrationDependencyUnavailable, UpstreamIntegrationError
from core.gateway_services.forge_adapter import get_forge_adapter
from core.gateway_services.oracle_adapter import get_oracle_adapter
from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import GatewayStudioGenerateRequest, GatewayStudioGenerateResponse
from gateway_api.integration_tracing import record_integration_event
from gateway_api.metering import record_request
from gateway_api.rate_limiter import apply_rate_limit_headers, enforce_rate_limit

router = APIRouter(prefix="/studio", tags=["Gateway V1"])


async def _generate_studio_artifact(
    artifact_type: Literal["slides", "document", "sheet"],
    request: Request,
    payload: GatewayStudioGenerateRequest,
    response: Response,
    auth_context: AuthContext,
) -> GatewayStudioGenerateResponse:
    start = time.perf_counter()
    status_code = 200
    trace_id = f"trc_{uuid.uuid4().hex[:14]}"

    await record_integration_event(
        trace_id=trace_id,
        flow="forge_outline_generation",
        stage="request_received",
        status="started",
        context={"artifact_type": artifact_type},
    )

    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)

        oracle_result = await get_oracle_adapter().search(payload.prompt, payload.oracle_limit)
        await record_integration_event(
            trace_id=trace_id,
            flow="oracle_search",
            stage="search",
            status="success",
            context={"results": len(oracle_result.get("results", []))},
        )

        generated = await get_forge_adapter().generate_outline(
            prompt=payload.prompt,
            artifact_type=artifact_type,
            template=payload.template,
            oracle_context=oracle_result,
        )
        await record_integration_event(
            trace_id=trace_id,
            flow="forge_outline_generation",
            stage="generate_outline",
            status="success",
            context={"artifact_id": generated.get("artifact_id", "")},
        )

        return GatewayStudioGenerateResponse(
            trace_id=trace_id,
            artifact_id=generated.get("artifact_id", ""),
            artifact_type=artifact_type,
            title=generated.get("title", ""),
            outline=generated.get("outline", {}),
            citations=generated.get("citations", []),
        )
    except IntegrationDependencyUnavailable as exc:
        status_code = 503
        await record_integration_event(
            trace_id=trace_id,
            flow="forge_outline_generation",
            stage="generate_outline",
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
            flow="forge_outline_generation",
            stage="generate_outline",
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
            flow="forge_outline_generation",
            stage="generate_outline",
            status="failed",
            context={"reason": str(exc)},
        )
        raise HTTPException(
            status_code=502,
            detail={"error": {"code": "upstream_integration_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.post(
    "/slides",
    response_model=GatewayStudioGenerateResponse,
    responses={502: {"description": "upstream integration failed"}, 503: {"description": "integration dependency unavailable"}},
)
async def generate_slides(
    request: Request,
    payload: GatewayStudioGenerateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("studio:write")),
) -> GatewayStudioGenerateResponse:
    return await _generate_studio_artifact("slides", request, payload, response, auth_context)


@router.post(
    "/docs",
    response_model=GatewayStudioGenerateResponse,
    responses={502: {"description": "upstream integration failed"}, 503: {"description": "integration dependency unavailable"}},
)
async def generate_docs(
    request: Request,
    payload: GatewayStudioGenerateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("studio:write")),
) -> GatewayStudioGenerateResponse:
    return await _generate_studio_artifact("document", request, payload, response, auth_context)


@router.post(
    "/sheets",
    response_model=GatewayStudioGenerateResponse,
    responses={502: {"description": "upstream integration failed"}, 503: {"description": "integration dependency unavailable"}},
)
async def generate_sheets(
    request: Request,
    payload: GatewayStudioGenerateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("studio:write")),
) -> GatewayStudioGenerateResponse:
    return await _generate_studio_artifact("sheet", request, payload, response, auth_context)
