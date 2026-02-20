from __future__ import annotations

import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from core.scheduler import JobDefinition, scheduler_service
from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import GatewayCronJobCreateRequest, GatewayCronJobOut
from gateway_api.metering import record_request
from gateway_api.rate_limiter import apply_rate_limit_headers, enforce_rate_limit

router = APIRouter(prefix="/cron", tags=["Gateway V1"])


def _to_gateway_job(job: JobDefinition) -> GatewayCronJobOut:
    return GatewayCronJobOut(
        id=job.id,
        name=job.name,
        cron_expression=job.cron_expression,
        agent_type=job.agent_type,
        query=job.query,
        enabled=job.enabled,
        status="scheduled" if job.enabled else "disabled",
        last_run=job.last_run,
        next_run=job.next_run,
        last_output=job.last_output,
    )


@router.get("/jobs", response_model=List[GatewayCronJobOut])
async def list_jobs(
    request: Request,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("cron:read")),
) -> List[GatewayCronJobOut]:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)
        jobs = scheduler_service.list_jobs()
        return [_to_gateway_job(job) for job in jobs]
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "cron_list_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.post("/jobs", response_model=GatewayCronJobOut)
async def create_job(
    request: Request,
    payload: GatewayCronJobCreateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("cron:write")),
) -> GatewayCronJobOut:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)
        job = scheduler_service.add_job(
            name=payload.name,
            cron_expression=payload.cron,
            agent_type=payload.agent_type,
            query=payload.query,
        )
        return _to_gateway_job(job)
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 400
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "cron_create_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.post("/jobs/{job_id}/trigger", response_model=dict)
async def trigger_job(
    job_id: str,
    request: Request,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("cron:write")),
) -> dict:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)
        scheduler_service.trigger_job(job_id)
        return {"status": "triggered", "id": job_id}
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 404
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "cron_job_not_found", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, auth_context.key_id, status_code, start)


@router.delete("/jobs/{job_id}", response_model=dict)
async def delete_job(
    job_id: str,
    request: Request,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("cron:write")),
) -> dict:
    start = time.perf_counter()
    status_code = 200
    try:
        decision = await enforce_rate_limit(auth_context)
        apply_rate_limit_headers(response, decision)
        scheduler_service.delete_job(job_id)
        return {"status": "deleted", "id": job_id}
    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "cron_delete_failed", "message": str(exc)}},
        ) from exc
    finally:
        await record_request(request, auth_context.key_id, status_code, start)
