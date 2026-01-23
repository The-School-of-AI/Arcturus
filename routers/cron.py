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

@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a scheduled task."""
    scheduler_service.delete_job(job_id)
    return {"status": "deleted", "id": job_id}
