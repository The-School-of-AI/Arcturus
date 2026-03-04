from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder

from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import GatewayAgentRunRequest, GatewayAgentRunResponse
from gateway_api.idempotency import (
    begin_idempotent_request,
    finalize_idempotent_failure,
    finalize_idempotent_success,
)
from gateway_api.metering import record_request
from gateway_api.rate_limiter import enforce_rate_limit_and_usage_governance
from gateway_api.usage_governance import is_usage_quota_exception
from routers.runs import process_run

router = APIRouter(prefix="/agents", tags=["Gateway V1"])
IDEMPOTENCY_HEADER = "Idempotency-Key"


@router.post("/run", response_model=GatewayAgentRunResponse)
async def run_agent(
    request: Request,
    payload: GatewayAgentRunRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("agents:run")),
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayAgentRunResponse:
    start = time.perf_counter()
    status_code = 200
    usage_units = 3
    governance_denied = False
    billable_request = True
    idempotency_context = None

    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor=auth_context.key_id,
            idempotency_key=idempotency_key,
            payload=payload.model_dump(mode="json"),
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
            estimated_units=3,
        )
        usage_units = usage_decision.estimated_units

        run_id = f"gw_run_{uuid.uuid4().hex[:12]}"
        if payload.wait_for_completion:
            result = await process_run(run_id, payload.query)
            run_status = result.get("status", "completed")
            if run_status not in {"completed", "failed"}:
                run_status = "completed"
            response_payload = GatewayAgentRunResponse(
                run_id=run_id,
                status=run_status,
                query=payload.query,
                result=result,
            )
            if idempotency_context is not None:
                await finalize_idempotent_success(
                    idempotency_context,
                    status_code=200,
                    response_body=jsonable_encoder(response_payload),
                    response_headers={
                        "X-Idempotency-Status": "created",
                        "X-Idempotency-Key": idempotency_context.idempotency_key,
                    },
                )
            return response_payload

        background_tasks.add_task(process_run, run_id, payload.query)
        response_payload = GatewayAgentRunResponse(
            run_id=run_id,
            status="queued",
            query=payload.query,
            result=None,
        )
        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=jsonable_encoder(response_payload),
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": idempotency_context.idempotency_key,
                },
            )
        return response_payload

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
        status_code = 500
        detail = {"error": {"code": "agent_run_failed", "message": str(exc)}}
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=500,
                detail=detail,
            )
        raise HTTPException(status_code=500, detail=detail) from exc
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
