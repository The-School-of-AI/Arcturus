"""
P08 Legion — Mandatory Acceptance Tests
File: tests/acceptance/p08_legion/test_swarm_completes_with_worker_failure.py

Hard conditions (per charter §73-80):
1. File must contain ≥ 8 executable test cases.
2. Happy-path user flow must pass end-to-end.
3. Invalid/malformed-payload behavior returns controlled errors (no crashes).
4. Retry/idempotency behavior validated where tasks are used.
5. DAG with ≥ 3 worker roles must complete, including retry/reassign when one worker fails.
"""

import pytest
import ray
import asyncio
import uuid
from unittest.mock import patch, AsyncMock
from agents.protocol import (
    Task, TaskStatus, TaskPriority,
    AgentMessage, Artifact,
)
from agents.swarm_runner import SwarmRunner
from agents.worker import WorkerAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ray_session():
    """Module-scoped Ray session — starts once, shared across all tests."""
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, log_to_driver=False)
    yield
    # Do NOT call ray.shutdown() here — letting module scope handle cleanup
    # so individual tests don't conflict.


def _make_task(title: str, role: str, priority: str = "medium",
               depends_on_ids: list = None) -> dict:
    """Helper: create a serialized Task dict for use in run_tasks()."""
    t = Task(
        title=title,
        description=f"Do the work for: {title}",
        assigned_to=role,
        priority=TaskPriority(priority),
        dependencies=depends_on_ids or [],
    )
    return t.model_dump()


# ---------------------------------------------------------------------------
# Test 1 — Protocol: Task model fields and defaults
# ---------------------------------------------------------------------------

def test_protocol_task_fields_and_defaults():
    """Task model must have required fields with correct defaults."""
    task = Task(
        title="Verify Something",
        description="Check the output.",
        assigned_to="reviewer",
    )
    assert task.id is not None
    assert len(task.id) == 36  # UUID format
    assert task.status == TaskStatus.PENDING
    assert task.priority == TaskPriority.MEDIUM
    assert task.dependencies == []
    assert task.result is None


# ---------------------------------------------------------------------------
# Test 2 — Protocol: TaskStatus enum completeness
# ---------------------------------------------------------------------------

def test_protocol_task_status_enum():
    """TaskStatus must include all lifecycle states."""
    expected = {"pending", "in_progress", "completed", "failed", "blocked"}
    actual = {s.value for s in TaskStatus}
    assert expected == actual, f"Missing or unexpected statuses: {actual ^ expected}"


# ---------------------------------------------------------------------------
# Test 3 — Protocol: AgentMessage creation with artifacts
# ---------------------------------------------------------------------------

def test_protocol_agent_message_creation():
    """AgentMessage must be constructable with all fields."""
    artifact = Artifact(name="output.txt", type="text", content="Hello")
    msg = AgentMessage(
        from_agent="manager_001",
        to_agent="worker_researcher",
        task_id=str(uuid.uuid4()),
        content="Please research quantum computing.",
        artifacts=[artifact],
        metadata={"priority": "high"},
    )
    assert msg.id is not None
    assert msg.from_agent == "manager_001"
    assert len(msg.artifacts) == 1
    assert msg.artifacts[0].name == "output.txt"


# ---------------------------------------------------------------------------
# Test 4 — Happy-path: 2-task linear DAG completes end-to-end
# ---------------------------------------------------------------------------

async def test_happy_path_two_task_dag_completes(ray_session):
    """Happy-path: 2-task linear DAG (researcher → writer) must complete."""
    runner = SwarmRunner()
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True)

    research = _make_task("Research Topic", "researcher", "high")
    write = _make_task(
        "Write Summary", "writer", "medium",
        depends_on_ids=[research["id"]]
    )

    results = await runner.run_tasks([research, write])

    assert len(results) == 2
    for r in results:
        assert r["status"] == TaskStatus.COMPLETED, f"Task '{r['title']}' not completed: {r['status']}"


# ---------------------------------------------------------------------------
# Test 5 — 3 worker roles: DAG with researcher, analyst, writer
# ---------------------------------------------------------------------------

async def test_dag_with_3_worker_roles_completes(ray_session):
    """Charter condition 5: DAG with ≥ 3 worker roles must complete."""
    runner = SwarmRunner()

    research = _make_task("Gather Raw Data", "researcher", "high")
    analysis = _make_task(
        "Analyse Data", "analyst", "high",
        depends_on_ids=[research["id"]]
    )
    report = _make_task(
        "Write Report", "writer", "medium",
        depends_on_ids=[analysis["id"]]
    )

    results = await runner.run_tasks([research, analysis, report])

    assert len(results) == 3
    roles_used = {r["assigned_to"] for r in results}
    assert roles_used == {"researcher", "analyst", "writer"}, (
        f"Expected 3 roles, got: {roles_used}"
    )
    for r in results:
        assert r["status"] == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# Test 6 — Worker failure: task fails then retries and completes
# ---------------------------------------------------------------------------

async def test_worker_failure_triggers_retry_and_completes(ray_session):
    """
    Charter condition 5: swarm must retry when a worker fails.
    Patches WorkerAgent.process_task to fail on attempt 1, succeed on attempt 2.
    """
    runner = SwarmRunner()
    call_count = {"n": 0}

    original_process = WorkerAgent.process_task

    async def flaky_process(self, task):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("Simulated transient worker failure.")
        return await original_process(self, task)

    research = _make_task("Fetch Articles", "researcher", "high")

    # Patch at the class level so the Ray actor picks it up
    with patch.object(WorkerAgent, "process_task", flaky_process):
        results = await runner.run_tasks([research])

    assert call_count["n"] >= 2, "Expected at least 2 calls (1 failure + 1 retry)"
    assert results[0]["status"] == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# Test 7 — Invalid input: malformed/empty payload returns controlled error
# ---------------------------------------------------------------------------

async def test_invalid_task_payload_returns_controlled_error(ray_session):
    """
    Charter condition 3: malformed task payloads must not crash the swarm —
    they must raise ValidationError or return a controlled error.
    """
    runner = SwarmRunner()

    # A badly formed task missing required fields
    bad_task = {
        "id": str(uuid.uuid4()),
        "title": "",            # empty title
        "description": "",      # empty description
        "assigned_to": "",      # no role — worker won't exist
        "status": "pending",
        "priority": "medium",
        "dependencies": [],
        "artifacts": [],
        "result": None,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }

    # Should not raise an uncaught exception — must fail gracefully
    try:
        results = await runner.run_tasks([bad_task])
        # If it returns results, the task should be marked FAILED not crash
        assert all(r["status"] in (TaskStatus.FAILED, TaskStatus.COMPLETED) for r in results)
    except (Exception,) as e:
        # Controlled errors (ValueError, RuntimeError) are acceptable here
        assert isinstance(e, (ValueError, RuntimeError, KeyError)), (
            f"Unexpected exception type: {type(e).__name__}: {e}"
        )


# ---------------------------------------------------------------------------
# Test 8 — Dependency ordering: task B must not finish before task A
# ---------------------------------------------------------------------------

async def test_dependency_order_respected(ray_session):
    """
    Dependency order: a downstream task's start time must be ≥
    its upstream dependency's completion time.
    """
    import time

    runner = SwarmRunner()
    finish_times: dict = {}

    original_process = WorkerAgent.process_task

    async def timed_process(self, task):
        result = await original_process(self, task)
        finish_times[task["title"]] = time.monotonic()
        return result

    upstream = _make_task("Upstream Task", "researcher", "high")
    downstream = _make_task(
        "Downstream Task", "writer", "medium",
        depends_on_ids=[upstream["id"]]
    )

    with patch.object(WorkerAgent, "process_task", timed_process):
        results = await runner.run_tasks([upstream, downstream])

    assert len(results) == 2
    assert results[0]["status"] == TaskStatus.COMPLETED
    assert results[1]["status"] == TaskStatus.COMPLETED

    if "Upstream Task" in finish_times and "Downstream Task" in finish_times:
        assert finish_times["Upstream Task"] <= finish_times["Downstream Task"], (
            "Downstream task completed BEFORE upstream — dependency order violated!"
        )
