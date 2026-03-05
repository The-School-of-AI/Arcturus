from __future__ import annotations

import time
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder

from core.scheduler import JobDefinition, scheduler_service
from gateway_api.auth import AuthContext, require_scope
from gateway_api.contracts import (
    GatewayCronJobCreateRequest,
    GatewayCronJobHistoryOut,
    GatewayCronJobOut,
)
from gateway_api.idempotency import (
    begin_idempotent_request,
    finalize_idempotent_failure,
    finalize_idempotent_success,
)
from gateway_api.metering import record_request
from gateway_api.rate_limiter import enforce_rate_limit_and_usage_governance
from gateway_api.usage_governance import is_usage_quota_exception

router = APIRouter(prefix="/cron", tags=["Gateway V1"])
IDEMPOTENCY_HEADER = "Idempotency-Key"


def _to_gateway_job(job: JobDefinition) -> GatewayCronJobOut:
    return GatewayCronJobOut(
        id=job.id,
        name=job.name,
        cron_expression=job.cron_expression,
        agent_type=job.agent_type,
        query=job.query,
        timezone=job.timezone,
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
    usage_units = 1
    governance_denied = False
    try:
        _, usage_decision = await enforce_rate_limit_and_usage_governance(
            request=request,
            response=response,
            auth_context=auth_context,
        )
        usage_units = usage_decision.estimated_units

        jobs = scheduler_service.list_jobs()
        return [_to_gateway_job(job) for job in jobs]
    except HTTPException as exc:
        status_code = exc.status_code
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "cron_list_failed", "message": str(exc)}},
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


@router.get("/jobs/{job_id}/history", response_model=List[GatewayCronJobHistoryOut])
async def get_job_history(
    job_id: str,
    request: Request,
    response: Response,
    limit: int = 50,
    auth_context: AuthContext = Depends(require_scope("cron:read")),
) -> List[GatewayCronJobHistoryOut]:
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

        rows = scheduler_service.get_job_history(job_id, limit=max(1, limit))
        return [GatewayCronJobHistoryOut(**row) for row in rows]
    except HTTPException as exc:
        status_code = exc.status_code
        if is_usage_quota_exception(exc):
            governance_denied = True
        raise
    except Exception as exc:  # noqa: BLE001
        status_code = 500
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "cron_history_failed", "message": str(exc)}},
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


@router.post("/jobs", response_model=GatewayCronJobOut)
async def create_job(
    request: Request,
    payload: GatewayCronJobCreateRequest,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("cron:write")),
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> GatewayCronJobOut:
    start = time.perf_counter()
    status_code = 200
    usage_units = 2
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
            estimated_units=2,
        )
        usage_units = usage_decision.estimated_units

        job = scheduler_service.add_job(
            name=payload.name,
            cron_expression=payload.cron,
            agent_type=payload.agent_type,
            query=payload.query,
            timezone=payload.timezone,
        )
        result = _to_gateway_job(job)

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
        status_code = 400
        detail = {"error": {"code": "cron_create_failed", "message": str(exc)}}
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=status_code,
                detail=detail,
            )
        raise HTTPException(status_code=400, detail=detail) from exc
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


@router.post("/jobs/{job_id}/trigger", response_model=dict)
async def trigger_job(
    job_id: str,
    request: Request,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("cron:write")),
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> dict:
    start = time.perf_counter()
    status_code = 200
    usage_units = 2
    governance_denied = False
    billable_request = True
    idempotency_context = None
    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor=auth_context.key_id,
            idempotency_key=idempotency_key,
            payload={"job_id": job_id},
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
            estimated_units=2,
        )
        usage_units = usage_decision.estimated_units

        scheduler_service.trigger_job(job_id)
        result = {"status": "triggered", "id": job_id}

        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=result,
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": idempotency_context.idempotency_key,
                },
            )

        return result
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
        status_code = 404
        detail = {"error": {"code": "cron_job_not_found", "message": str(exc)}}
        if idempotency_context is not None:
            await finalize_idempotent_failure(
                idempotency_context,
                status_code=404,
                detail=detail,
            )
        raise HTTPException(status_code=404, detail=detail) from exc
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


@router.delete("/jobs/{job_id}", response_model=dict)
async def delete_job(
    job_id: str,
    request: Request,
    response: Response,
    auth_context: AuthContext = Depends(require_scope("cron:write")),
    idempotency_key: Optional[str] = Header(default=None, alias=IDEMPOTENCY_HEADER),
) -> dict:
    start = time.perf_counter()
    status_code = 200
    usage_units = 2
    governance_denied = False
    billable_request = True
    idempotency_context = None
    try:
        idempotency_context, replay = await begin_idempotent_request(
            request=request,
            actor=auth_context.key_id,
            idempotency_key=idempotency_key,
            payload={"job_id": job_id},
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
            estimated_units=2,
        )
        usage_units = usage_decision.estimated_units

        scheduler_service.delete_job(job_id)
        result = {"status": "deleted", "id": job_id}

        if idempotency_context is not None:
            await finalize_idempotent_success(
                idempotency_context,
                status_code=200,
                response_body=result,
                response_headers={
                    "X-Idempotency-Status": "created",
                    "X-Idempotency-Key": idempotency_context.idempotency_key,
                },
            )

        return result
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
        detail = {"error": {"code": "cron_delete_failed", "message": str(exc)}}
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
