from datetime import datetime, timezone

import pytest

from core.scheduler import JobDefinition, SchedulerService


class _DummyApsJob:
    def __init__(self):
        self.next_run_time = datetime.now(timezone.utc)


class _DummyScheduler:
    def __init__(self):
        self._jobs = {}

    def add_job(self, _func, _trigger, id, name, replace_existing=True):  # noqa: A002
        del _func, _trigger, name, replace_existing
        self._jobs[id] = _DummyApsJob()

    def get_job(self, job_id):
        return self._jobs.get(job_id)


def test_scheduler_timezone_validation_accepts_valid_timezone(monkeypatch):
    service = SchedulerService()
    monkeypatch.setattr(service, "scheduler", _DummyScheduler())
    monkeypatch.setattr(service, "save_jobs", lambda: None)

    job = JobDefinition(
        id="job_valid",
        name="Valid TZ",
        cron_expression="0 9 * * *",
        agent_type="PlannerAgent",
        query="hello",
        timezone="UTC",
    )

    service._schedule_job(job)
    assert job.next_run is not None


def test_scheduler_timezone_validation_rejects_invalid_timezone(monkeypatch):
    service = SchedulerService()
    monkeypatch.setattr(service, "scheduler", _DummyScheduler())
    monkeypatch.setattr(service, "save_jobs", lambda: None)

    job = JobDefinition(
        id="job_invalid",
        name="Invalid TZ",
        cron_expression="0 9 * * *",
        agent_type="PlannerAgent",
        query="hello",
        timezone="Mars/Phobos",
    )

    with pytest.raises(ValueError, match="Invalid timezone"):
        service._schedule_job(job)
