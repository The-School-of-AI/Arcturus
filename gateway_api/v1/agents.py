from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response

from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import GatewayAgentRunRequest, GatewayAgentRunResponse
from gateway_api.metering import record_request
from gateway_api.rate_limiter import apply_rate_limit_headers, enforce_rate_limit
from routers.runs import process_run

router = APIRouter(prefix="/agents", tags=["Gateway V1"])


@router.post("/run", response_model=GatewayAgentRunResponse)
async def run_agent(
    request: Request,
    payload: GatewayAgentRunRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("agents:run")),
) -> GatewayAgentRunResponse:
    start = time.perf_counter()
    status_code = 200

    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)

        run_id = f"gw_run_{uuid.uuid4().hex[:12]}"
        if payload.wait_for_completion:
            result = await process_run(run_id, payload.query)
            run_status = result.get("status", "completed")
            if run_status not in {"completed", "failed"}:
                run_status = "completed"
            return GatewayAgentRunResponse(
                run_id=run_id,
                status=run_status,
                query=payload.query,
                result=result,
            )

        background_tasks.add_task(process_run, run_id, payload.query)
        return GatewayAgentRunResponse(
            run_id=run_id,
            status="queued",
            query=payload.query,
            result=None,
        )

    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "agent_run_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, auth_context.key_id, status_code, start)
