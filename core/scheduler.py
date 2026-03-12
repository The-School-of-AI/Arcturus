import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel
from shared.state import PROJECT_ROOT

# Setup logging
logger = logging.getLogger("scheduler")

# Path to persist jobs
JOBS_FILE = PROJECT_ROOT / "data" / "system" / "jobs.json"
JOB_HISTORY_FILE = PROJECT_ROOT / "data" / "system" / "job_history.jsonl"


def _corrupt_path(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = f"{path.suffix}.corrupt.{stamp}" if path.suffix else f".corrupt.{stamp}"
    return path.with_suffix(suffix)


def _preserve_corrupt_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        path.replace(_corrupt_path(path))
    except OSError:
        logger.warning(f"Failed to preserve corrupt scheduler file: {path}")


def _read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        _preserve_corrupt_file(path)
        return default


def _write_json_atomic(path: Path, payload: Any) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(path)


class JobDefinition(BaseModel):
    id: str
    name: str
    cron_expression: str
    agent_type: str
    query: str
    timezone: str = "UTC"
    skill_id: Optional[str] = None  # Link to a specific skill
    enabled: bool = True
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    last_output: Optional[str] = None


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

        if not JOBS_FILE.parent.exists():
            JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)

        if not JOB_HISTORY_FILE.parent.exists():
            JOB_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

        self.scheduler.start()
        self.load_jobs()
        logger.info("✅ Scheduler Service Started")
        self.initialized = True

    def load_jobs(self):
        """Load jobs from JSON and schedule them."""
        if not JOBS_FILE.exists():
            return

        try:
            data = _read_json_file(JOBS_FILE, [])
            if not isinstance(data, list):
                data = []
            for job_data in data:
                job_def = JobDefinition(**job_data)
                self.jobs[job_def.id] = job_def
                if job_def.enabled:
                    try:
                        self._schedule_job(job_def)
                    except Exception as exc:  # noqa: BLE001
                        logger.error(f"Failed to schedule loaded job {job_def.id}: {exc}")
            logger.info(f"Loaded {len(self.jobs)} jobs from disk.")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to load jobs: {e}")

    def save_jobs(self):
        """Persist jobs to JSON."""
        data = [job.model_dump() for job in self.jobs.values()]
        _write_json_atomic(JOBS_FILE, data)

    def _append_job_history(self, entry: Dict[str, Any]) -> None:
        if not JOB_HISTORY_FILE.parent.exists():
            JOB_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with JOB_HISTORY_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def _record_job_history(
        self,
        *,
        job_id: str,
        run_id: str,
        status: str,
        started_at: str,
        finished_at: str,
        error: Optional[str] = None,
        output_summary: Optional[str] = None,
    ) -> None:
        self._append_job_history(
            {
                "job_id": job_id,
                "run_id": run_id,
                "status": status,
                "started_at": started_at,
                "finished_at": finished_at,
                "error": error,
                "output_summary": output_summary,
            }
        )

    def get_job_history(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        if not JOB_HISTORY_FILE.exists():
            return []

        rows: List[Dict[str, Any]] = []
        try:
            lines = JOB_HISTORY_FILE.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            _preserve_corrupt_file(JOB_HISTORY_FILE)
            return []

        has_corruption = False
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                has_corruption = True
                continue

            if payload.get("job_id") != job_id:
                continue
            rows.append(payload)

        if has_corruption:
            logger.warning("Detected corrupt scheduler history lines; invalid rows were ignored.")

        rows = rows[-max(1, limit) :]
        rows.reverse()
        return rows

    def _schedule_job(self, job: JobDefinition):
        """Internal method to add job to APScheduler."""

        try:
            timezone_obj = ZoneInfo(job.timezone)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid timezone: {job.timezone}") from exc

        async def job_wrapper():
            # Lazy import to avoid circular dependency
            from core.event_bus import event_bus
            from routers.inbox import send_to_inbox
            from routers.runs import process_run

            from .skills.manager import skill_manager

            run_id = f"auto_{job.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            started_at = datetime.now().isoformat()

            # Emit Start Event
            log_msg = f"⏰ Triggering Scheduled Job: {job.name} ({run_id})"
            logger.info(log_msg)
            await event_bus.publish(
                "log",
                "scheduler",
                {
                    "message": log_msg,
                    "metadata": {"job_id": job.id, "run_id": run_id},
                },
            )

            # Update last run
            job.last_run = datetime.now().isoformat()
            self.save_jobs()

            try:
                skill = None
                effective_query = job.query

                if job.skill_id:
                    skill = skill_manager.get_skill(job.skill_id)
                    if skill:
                        skill.context.run_id = run_id
                        skill.context.agent_id = job.agent_type
                        skill.context.config = {"query": job.query}

                        effective_query = await skill.on_run_start(job.query)

                        msg = f"🧠 Skill '{job.skill_id}' modified prompt: {effective_query[:50]}..."
                        logger.info(msg)
                        await event_bus.publish("log", "scheduler", {"message": msg})

                result = await process_run(run_id, effective_query)

                skill_result = None
                if skill and result:
                    skill_result = await skill.on_run_success(
                        result if isinstance(result, dict) else {"output": str(result)}
                    )
                # 3. Execution (The standard run, now skill-aware)
                result = await process_run(run_id, job.query, skill_id=job.skill_id)
                
                # Update job output using skill summary if available
                skill_summary = result.get("skill_summary") if result else None
                skill_file_path = result.get("skill_file_path") if result else None

                success_msg = f"✅ Job '{job.name}' completed successfully."
                await event_bus.publish(
                    "success",
                    "scheduler",
                    {
                        "message": success_msg,
                        "metadata": {"job_id": job.id, "run_id": run_id},
                    },
                )

                job.last_output = (
                    skill_result.get("summary")
                    if skill_result
                    else (result.get("summary") if result else "Success")
                )
                
                # Update job with result
                job.last_output = skill_summary if skill_summary else (result.get("summary") if result else "Success")
                self.save_jobs()

                notif_body = f"Job '{job.name}' finished.\n\n"
                if skill_summary:
                    notif_body += f"**Summary**: {skill_summary}\n\n"
                elif result and result.get("summary"):
                    notif_body += f"**Summary**: {result['summary'][:200]}...\n\n"

                notif_body += f"*Run ID: {run_id}*"

                send_to_inbox(
                    source="Scheduler",
                    title=f"Completed: {job.name}",
                    body=notif_body,
                    priority=1,
                    metadata={
                        "job_id": job.id,
                        "run_id": run_id,
                        "file_path": skill_file_path
                    }
                )

                finished_at = datetime.now().isoformat()
                self._record_job_history(
                    job_id=job.id,
                    run_id=run_id,
                    status="success",
                    started_at=started_at,
                    finished_at=finished_at,
                    output_summary=job.last_output,
                )
            except Exception as e:  # noqa: BLE001
                error_msg = f"❌ Job {job.name} failed: {e}"
                logger.error(error_msg)

                await event_bus.publish(
                    "error",
                    "scheduler",
                    {
                        "message": error_msg,
                    },
                )

                send_to_inbox(
                    source="Scheduler",
                    title=f"Job Failed: {job.name}",
                    body=f"Error: {str(e)}",
                    priority=2,
                )

                if skill:
                    await skill.on_run_failure(str(e))

                finished_at = datetime.now().isoformat()
                self._record_job_history(
                    job_id=job.id,
                    run_id=run_id,
                    status="failed",
                    started_at=started_at,
                    finished_at=finished_at,
                    error=str(e),
                )

        # Parse cron expression (simple space-separated 5 fields)
        try:
            self.scheduler.add_job(
                job_wrapper,
                CronTrigger.from_crontab(job.cron_expression, timezone=timezone_obj),
                id=job.id,
                name=job.name,
                replace_existing=True,
            )

            aps_job = self.scheduler.get_job(job.id)
            if aps_job and aps_job.next_run_time:
                job.next_run = aps_job.next_run_time.isoformat()
                self.save_jobs()
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"Invalid cron expression for {job.name}: {e}") from e

    def add_job(
        self,
        name: str,
        cron_expression: str,
        agent_type: str,
        query: str,
        timezone: str = "UTC",
    ) -> JobDefinition:
        """Add a new scheduled job."""
        from .skills.manager import skill_manager

        if not skill_manager.skill_classes:
            skill_manager.initialize()

        skill_id = skill_manager.match_intent(query)
        if skill_id:
            logger.info(f"🧠 Smart Scheduler: Matched query '{query}' to Skill '{skill_id}'")

        job_id = str(uuid.uuid4())[:8]
        job = JobDefinition(
            id=job_id,
            name=name,
            cron_expression=cron_expression,
            agent_type=agent_type,
            query=query,
            timezone=timezone,
            skill_id=skill_id,
        )
        self.jobs[job_id] = job
        try:
            self._schedule_job(job)
        except Exception:
            self.jobs.pop(job_id, None)
            raise
        self.save_jobs()
        return job

    def trigger_job(self, job_id: str):
        """Force a job to run immediately."""
        if job_id not in self.jobs:
            logger.warning(f"Trigger failed: Job {job_id} not found in registry")
            raise KeyError(job_id)

        if self.scheduler.get_job(job_id):
            self.scheduler.modify_job(job_id, next_run_time=datetime.now())
            logger.info(f"👉 Setup immediate execution for {job_id}")
        else:
            self._schedule_job(self.jobs[job_id])
            self.scheduler.modify_job(job_id, next_run_time=datetime.now())

    def delete_job(self, job_id: str):
        """Remove a job."""
        if job_id in self.jobs:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            del self.jobs[job_id]
            self.save_jobs()

    def list_jobs(self) -> List[JobDefinition]:
        """List all jobs with updated next-run times."""
        for job_id, job in self.jobs.items():
            aps_job = self.scheduler.get_job(job_id)
            if aps_job and aps_job.next_run_time:
                job.next_run = aps_job.next_run_time.isoformat()

        return list(self.jobs.values())


# Global Instance
scheduler_service = SchedulerService()
