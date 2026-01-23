import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel
import uuid

# Setup logging
logger = logging.getLogger("scheduler")

# Path to persist jobs
JOBS_FILE = Path("data/system/jobs.json")

class JobDefinition(BaseModel):
    id: str
    name: str
    cron_expression: str
    agent_type: str
    query: str
    enabled: bool = True
    last_run: Optional[str] = None
    next_run: Optional[str] = None

class SchedulerService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SchedulerService, cls).__new__(cls)
            cls._instance.scheduler = AsyncIOScheduler()
            cls._instance.jobs: Dict[str, JobDefinition] = {}
            cls._instance.initialized = False
        return cls._instance

    def initialize(self):
        if self.initialized:
            return
        
        # Ensure data directory exists
        if not JOBS_FILE.parent.exists():
            JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
            
        self.load_jobs()
        self.scheduler.start()
        logger.info("✅ Scheduler Service Started")
        self.initialized = True

    def load_jobs(self):
        """Load jobs from JSON and schedule them."""
        if not JOBS_FILE.exists():
            return

        try:
            data = json.loads(JOBS_FILE.read_text())
            for job_data in data:
                job_def = JobDefinition(**job_data)
                self.jobs[job_def.id] = job_def
                if job_def.enabled:
                    self._schedule_job(job_def)
            logger.info(f"Loaded {len(self.jobs)} jobs from disk.")
        except Exception as e:
            logger.error(f"Failed to load jobs: {e}")

    def save_jobs(self):
        """Persist jobs to JSON."""
        data = [job.dict() for job in self.jobs.values()]
        JOBS_FILE.write_text(json.dumps(data, indent=2))

    def _schedule_job(self, job: JobDefinition):
        """Internal method to add job to APScheduler."""
        
        # Define the function wrapper
        async def job_wrapper():
            # Lazy import to avoid circular dependency
            from routers.runs import process_run
            
            run_id = f"auto_{job.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"⏰ Triggering Scheduled Job: {job.name} ({run_id})")
            
            # Update last run
            job.last_run = datetime.now().isoformat()
            self.save_jobs()
            
            try:
                # We reuse the process_run logic from routers/runs.py
                # But we might need to await it or fire-and-forget
                await process_run(run_id, job.query)
            except Exception as e:
                logger.error(f"❌ Job {job.name} failed: {e}")

        # Parse cron expression (simple space-separated 5 fields)
        try:
            self.scheduler.add_job(
                job_wrapper,
                CronTrigger.from_crontab(job.cron_expression),
                id=job.id,
                name=job.name,
                replace_existing=True
            )
            # Update next run time
            aps_job = self.scheduler.get_job(job.id)
            if aps_job and aps_job.next_run_time:
                job.next_run = aps_job.next_run_time.isoformat()
                self.save_jobs()
                
        except Exception as e:
            logger.error(f"Invalid cron expression for {job.name}: {e}")

    def add_job(self, name: str, cron_expression: str, agent_type: str, query: str) -> JobDefinition:
        """Add a new scheduled job."""
        job_id = str(uuid.uuid4())[:8]
        job = JobDefinition(
            id=job_id,
            name=name,
            cron_expression=cron_expression,
            agent_type=agent_type,
            query=query
        )
        self.jobs[job_id] = job
        self._schedule_job(job)
        self.save_jobs()
        return job

    def delete_job(self, job_id: str):
        """Remove a job."""
        if job_id in self.jobs:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            del self.jobs[job_id]
            self.save_jobs()

    def list_jobs(self) -> List[JobDefinition]:
        """List all jobs with updated next-run times."""
        # Update next_run times from scheduler
        for job_id, job in self.jobs.items():
            aps_job = self.scheduler.get_job(job_id)
            if aps_job and aps_job.next_run_time:
                job.next_run = aps_job.next_run_time.isoformat()
        
        return list(self.jobs.values())

# Global Instance
scheduler_service = SchedulerService()
