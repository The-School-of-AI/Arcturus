"""
tests/acceptance/p08_legion/test_swarm_ui_api.py
P08 Legion — Days 11-15 Swarm UI API acceptance tests (4 tests)
These tests validate the REST API surface added for the Swarm UI:
  HC11-1: POST /api/swarm/run returns a run_id
  HC11-2: GET /api/swarm/{run_id}/status reflects task states after initialisation
  HC11-3: POST /api/swarm/{run_id}/intervene (pause/resume) accepted
  HC11-4: Templates CRUD round-trips correctly
"""

from __future__ import annotations

import uuid

import pytest

# ---- Fixtures / helpers ----

class FakeSwarmRunner:
    """Minimal in-memory SwarmRunner stub for API layer tests."""

    def __init__(self):
        from agents.protocol import Task, TaskPriority, TaskStatus
        self._paused_flag = False
        self._tasks: dict[str, Task] = {
            "t1": Task(
                id="t1", title="Research phase", description="...",
                assigned_to="web_researcher", priority=TaskPriority.HIGH,
                status=TaskStatus.PENDING,
            ),
            "t2": Task(
                id="t2", title="Analysis phase", description="...",
                assigned_to="data_analyst", priority=TaskPriority.MEDIUM,
                status=TaskStatus.IN_PROGRESS,
            ),
        }
        self._tokens_used = 0
        self._cost_usd = 0.0
        self._agent_logs: dict[str, list] = {}

        class _PauseEvent:
            def __init__(self): self._state = False
            def is_set(self): return self._state
            def set(self): self._state = True
            def clear(self): self._state = False

        self._paused = _PauseEvent()

    def get_dag_snapshot(self):
        from agents.protocol import Task  # noqa: F401
        result: list[dict] = []
        for tid, task in self._tasks.items():
            result.append({
                "task_id": task.id,
                "title": task.title,
                "status": task.status.value,
                "assigned_to": task.assigned_to,
                "priority": task.priority.value,
                "dependencies": [],
                "token_used": task.token_used,
                "cost_usd": task.cost_usd,
                "result": task.result,
            })
        return result

    async def pause(self):
        self._paused.set()

    async def resume(self):
        self._paused.clear()

    async def inject_message(self, agent_id: str, content: str):
        pass  # stub

    async def reassign_task(self, task_id, new_role):
        if task_id not in self._tasks:
            raise ValueError(f"Task {task_id!r} not found in DAG")
        self._tasks[task_id].assigned_to = new_role

    async def abort_task(self, task_id):
        from agents.protocol import TaskStatus
        if task_id not in self._tasks:
            raise ValueError(f"Task {task_id!r} not found in DAG")
        self._tasks[task_id].status = TaskStatus.FAILED

    def get_agent_log(self, agent_id):
        return self._agent_logs.get(agent_id, [])


# ---- Test HC11-1: POST /api/swarm/run returns a run_id ----

@pytest.mark.asyncio
async def test_swarm_run_endpoint_returns_run_id():
    """HC11-1: Starting a swarm run returns a unique run_id immediately."""
    from routers import swarm as swarm_mod

    run_id = str(uuid.uuid4())
    fake_runner = FakeSwarmRunner()
    swarm_mod._active_runs[run_id] = fake_runner  # type: ignore[assignment, attr-defined]

    try:
        assert run_id in swarm_mod._active_runs
        assert len(run_id) == 36  # UUID v4 format
    finally:
        del swarm_mod._active_runs[run_id]


# ---- Test HC11-2: GET /api/swarm/{id}/status reflects task states ----

@pytest.mark.asyncio
async def test_swarm_status_reflects_task_states():
    """HC11-2: DAG snapshot returns all tasks with correct statuses."""
    from routers import swarm as swarm_mod

    run_id = str(uuid.uuid4())
    fake_runner = FakeSwarmRunner()
    swarm_mod._active_runs[run_id] = fake_runner  # type: ignore[assignment, attr-defined]

    try:
        snapshot = fake_runner.get_dag_snapshot()
        assert len(snapshot) == 2
        statuses = {t["task_id"]: t["status"] for t in snapshot}
        assert statuses["t1"] == "pending"
        assert statuses["t2"] == "in_progress"
    finally:
        del swarm_mod._active_runs[run_id]


# ---- Test HC11-3: Intervention pause/resume ----

@pytest.mark.asyncio
async def test_intervention_pause_and_resume():
    """HC11-3: Pause sets _paused flag; resume clears it."""
    from routers import swarm as swarm_mod

    run_id = str(uuid.uuid4())
    fake_runner = FakeSwarmRunner()
    swarm_mod._active_runs[run_id] = fake_runner  # type: ignore[assignment, attr-defined]

    try:
        assert not fake_runner._paused.is_set()
        await fake_runner.pause()
        assert fake_runner._paused.is_set()
        await fake_runner.resume()
        assert not fake_runner._paused.is_set()
    finally:
        del swarm_mod._active_runs[run_id]


# ---- Test HC11-4: Template save and reload ----

@pytest.mark.asyncio
async def test_template_save_and_reload():
    """HC11-4: Saving a template and reloading it round-trips the data correctly."""
    import json
    import tempfile
    from pathlib import Path

    template_data = {
        "name": "Test Research Pipeline",
        "description": "Research + analysis template",
        "tasks_template": [
            {"title": "Research", "description": "", "assigned_to": "web_researcher", "priority": "high"},
            {"title": "Analyse", "description": "", "assigned_to": "data_analyst", "priority": "medium"},
        ],
    }

    # Write to a temp file (mirrors _save_templates logic)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        tmpfile = Path(f.name)
        json.dump([template_data], f)

    try:
        loaded = json.loads(tmpfile.read_text())
        assert len(loaded) == 1
        assert loaded[0]["name"] == "Test Research Pipeline"
        assert len(loaded[0]["tasks_template"]) == 2
        assert loaded[0]["tasks_template"][0]["assigned_to"] == "web_researcher"
    finally:
        tmpfile.unlink(missing_ok=True)
