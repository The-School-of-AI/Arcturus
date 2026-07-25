from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional
from pydantic import BaseModel
from core.scheduler import scheduler_service, JobDefinition

router = APIRouter(prefix="/cron", tags=["Scheduler"])

class CreateJobRequest(BaseModel):
    name: str
    cron: str
    agent_type: str = "PlannerAgent"
    query: str

@router.get("/jobs", response_model=List[JobDefinition])
async def list_jobs():
    """List all scheduled jobs."""
    return scheduler_service.list_jobs()

@router.post("/jobs", response_model=JobDefinition)
async def create_job(request: CreateJobRequest):
    """Create a new scheduled task."""
    try:
        job = scheduler_service.add_job(
            name=request.name,
            cron_expression=request.cron,
            agent_type=request.agent_type,
            query=request.query
        )
        return job
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class UpdateJobRequest(BaseModel):
    name: Optional[str] = None
    cron: Optional[str] = None
    query: Optional[str] = None


@router.put("/jobs/{job_id}", response_model=JobDefinition)
async def update_job(job_id: str, request: UpdateJobRequest):
    """Update a scheduled task's name, cron, or query."""
    try:
        job = scheduler_service.update_job(
            job_id=job_id,
            name=request.name,
            cron_expression=request.cron,
            query=request.query,
        )
        return job
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/jobs/{job_id}/trigger")
async def trigger_job(job_id: str):
    """Force run a job immediately."""
    try:
        scheduler_service.trigger_job(job_id)
        return {"status": "triggered", "id": job_id}
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{job_id}/history")
async def get_job_history(job_id: str, limit: int = 50):
    """Get execution history for a job."""
    return scheduler_service.get_job_history(job_id, limit=limit)


@router.delete("/jobs/{job_id}/history/{run_id}")
async def delete_job_history_entry(job_id: str, run_id: str):
    """Delete a single execution history entry."""
    found = scheduler_service.delete_job_history_entry(job_id, run_id)
    if not found:
        raise HTTPException(status_code=404, detail="History entry not found")
    return {"status": "deleted", "job_id": job_id, "run_id": run_id}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a scheduled task."""
    scheduler_service.delete_job(job_id)
    return {"status": "deleted", "id": job_id}
