from __future__ import annotations

import time
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder

from core.gateway_services.exceptions import IntegrationDependencyUnavailable, UpstreamIntegrationError
from core.gateway_services.forge_adapter import get_forge_adapter
from core.gateway_services.oracle_adapter import get_oracle_adapter
from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import GatewayStudioGenerateRequest, GatewayStudioGenerateResponse
from gateway_api.idempotency import (
    begin_idempotent_request,
    finalize_idempotent_failure,
    finalize_idempotent_success,
)
from gateway_api.integration_tracing import record_integration_event
from gateway_api.metering import record_request
from gateway_api.rate_limiter import enforce_rate_limit_and_usage_governance
from gateway_api.usage_governance import is_usage_quota_exception

router = APIRouter(prefix="/studio", tags=["Gateway V1"])
IDEMPOTENCY_HEADER = "Idempotency-Key"


async def _generate_studio_artifact(
    artifact_type: Literal["slides", "document", "sheet"],
    request: Request,
    payload: GatewayStudioGenerateRequest,
    response: Response,
    auth_context: AuthContext,
    idempotency_key: Optional[str],
) -> GatewayStudioGenerateResponse:
    start = time.perf_counter()
    status_code = 200
    usage_units = 5
    governance_denied = False
    billable_request = True
    idempotency_context = None
    trace_id = f"trc_{uuid.uuid4().hex[:14]}"

    await record_integration_event(
        trace_id=trace_id,
        flow="forge_outline_generation",
        stage="request_received",
        status="started",
        context={"artifact_type": artifact_type},
    )

    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor=auth_context.key_id,
            idempotency_key=idempotency_key,
            payload={**payload.model_dump(mode="json"), "artifact_type": artifact_type},
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
            estimated_units=5,
        )
        usage_units = usage_decision.estimated_units

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

        result = GatewayStudioGenerateResponse(
            trace_id=trace_id,
            artifact_id=generated.get("artifact_id", ""),
            artifact_type=artifact_type,
            title=generated.get("title", ""),
            outline=generated.get("outline", {}),
            citations=generated.get("citations", []),
        )

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
    except IntegrationDependencyUnavailable as exc:
        status_code = 503
        await record_integration_event(
            trace_id=trace_id,
            flow="forge_outline_generation",
            stage="generate_outline",
            status="failed",
            context={"reason": str(exc)},
        )
        detail = {
            "error": {
                "code": "integration_dependency_unavailable",
                "message": str(exc),
            }
        }
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=503,
                detail=detail,
            )
        raise HTTPException(status_code=503, detail=detail) from exc
    except UpstreamIntegrationError as exc:
        status_code = 502
        await record_integration_event(
            trace_id=trace_id,
            flow="forge_outline_generation",
            stage="generate_outline",
            status="failed",
            context={"reason": str(exc)},
        )
        detail = {"error": {"code": "upstream_integration_failed", "message": str(exc)}}
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=502,
                detail=detail,
            )
        raise HTTPException(status_code=502, detail=detail) from exc
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
        status_code = 502
        await record_integration_event(
            trace_id=trace_id,
            flow="forge_outline_generation",
            stage="generate_outline",
            status="failed",
            context={"reason": str(exc)},
        )
        detail = {"error": {"code": "upstream_integration_failed", "message": str(exc)}}
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=502,
                detail=detail,
            )
        raise HTTPException(status_code=502, detail=detail) from exc
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
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayStudioGenerateResponse:
    return await _generate_studio_artifact(
        "slides", request, payload, response, auth_context, idempotency_key
    )


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
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayStudioGenerateResponse:
    return await _generate_studio_artifact(
        "document", request, payload, response, auth_context, idempotency_key
    )


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
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayStudioGenerateResponse:
    return await _generate_studio_artifact(
        "sheet", request, payload, response, auth_context, idempotency_key
    )
