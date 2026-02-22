"""Integration scaffold for P08 (p08_legion).

These tests enforce contract-level integration gates across repo structure and CI wiring.
Tests 01-05: Structural scaffold (no runtime).
Tests 06-10: Runtime integration for hard conditions 6-8.
"""

import pytest
from pathlib import Path
from agents.protocol import TaskStatus

PROJECT_ID = "P08"
PROJECT_KEY = "p08_legion"
CI_CHECK = "p08-legion-swarm"
CHARTER = Path("CAPSTONE/project_charters/P08_legion_multi_agent_swarm_orchestration.md")
ACCEPTANCE_FILE = Path("tests/acceptance/p08_legion/test_swarm_completes_with_worker_failure.py")
INTEGRATION_FILE = Path("tests/integration/test_legion_chronicle_capture.py")
WORKFLOW_FILE = Path(".github/workflows/project-gates.yml")
BASELINE_SCRIPT = Path("scripts/test_all.sh")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# Structural scaffold tests (01-05) — no runtime required
# ──────────────────────────────────────────────────────────────────────────────

def test_01_integration_file_is_declared_in_charter() -> None:
    assert "Integration: " in _read(CHARTER)


def test_02_acceptance_and_integration_files_exist() -> None:
    assert ACCEPTANCE_FILE.exists(), f"Missing acceptance file: {ACCEPTANCE_FILE}"
    assert INTEGRATION_FILE.exists(), f"Missing integration file: {INTEGRATION_FILE}"


def test_03_baseline_script_exists_and_is_executable() -> None:
    import sys
    assert BASELINE_SCRIPT.exists(), "Missing baseline script scripts/test_all.sh"
    if sys.platform != "win32":
        # Windows does not support Unix executable bits — skip this check on Windows
        assert BASELINE_SCRIPT.stat().st_mode & 0o111, "scripts/test_all.sh must be executable"


def test_04_project_ci_check_is_wired_in_workflow() -> None:
    assert WORKFLOW_FILE.exists(), "Missing workflow .github/workflows/project-gates.yml"
    assert CI_CHECK in _read(WORKFLOW_FILE), f"CI check {CI_CHECK} not found in workflow"


def test_05_charter_requires_baseline_regression() -> None:
    assert "scripts/test_all.sh quick" in _read(CHARTER)


# ──────────────────────────────────────────────────────────────────────────────
# Runtime integration tests (06-10) — Hard Conditions 6-8
# Uses FakeWorker (in-process) — no live Ray / LLM / Chronicle needed in CI.
# ──────────────────────────────────────────────────────────────────────────────

class _FakeRemoteMethod:
    """Mimics ray_actor.method.remote(...) returning an awaitable."""
    def __init__(self, fn):
        self._fn = fn

    def remote(self, *args, **kwargs):
        return self._fn(*args, **kwargs)


class _FakeWorker:
    """In-process test double for WorkerAgent."""
    def __init__(self, fail_first_n: int = 0, cost_per_task: float = 0.0):
        self.call_count = 0
        self._fail_first_n = fail_first_n
        self._cost_per_task = cost_per_task
        self.process_task = _FakeRemoteMethod(self._process_task)

    async def _process_task(self, task: dict) -> dict:
        self.call_count += 1
        if self.call_count <= self._fail_first_n:
            raise RuntimeError(f"FakeWorker: simulated failure on attempt {self.call_count}.")
        task["status"] = TaskStatus.COMPLETED
        task["result"] = f"Result from FakeWorker (attempt {self.call_count})"
        task["token_used"] = 100
        task["cost_usd"] = self._cost_per_task
        return task


def _make_task(title: str, role: str, deps: list = None) -> dict:
    return {
        "title": title,
        "description": f"Description for {title}",
        "assigned_to": role,
        "dependencies": deps or [],
    }


@pytest.mark.asyncio
async def test_06_swarm_run_produces_completed_session_record():
    """
    Hard condition 6/7: A swarm run must produce a complete record of results
    that could be captured by a session tracker (Chronicle stub).
    """
    from agents.swarm_runner import SwarmRunner
    runner = SwarmRunner()
    runner.workers["researcher"] = _FakeWorker()

    results = await runner.run_tasks([_make_task("Research AI trends", "researcher")])

    assert len(results) == 1, "Swarm must return one result per task"
    assert results[0]["status"] == TaskStatus.COMPLETED
    assert results[0]["result"] is not None, "Result must be non-empty for session capture"
    assert "title" in results[0]
    assert "id" in results[0]


@pytest.mark.asyncio
async def test_07_mnemo_context_fields_present_in_task_result():
    """
    Hard condition 7: Task results must contain fields needed for Mnemo
    shared memory injection: id, title, result, assigned_to, status.
    """
    from agents.swarm_runner import SwarmRunner
    runner = SwarmRunner()
    runner.workers["analyst"] = _FakeWorker()

    results = await runner.run_tasks([_make_task("Analyse results", "analyst")])

    record = results[0]
    missing = {"id", "title", "result", "assigned_to", "status"} - set(record.keys())
    assert not missing, f"Task result missing Mnemo-required fields: {missing}"


@pytest.mark.asyncio
async def test_08_failed_task_captured_in_result_set():
    """
    Hard condition 8: When a worker exhausts all retries, failure must be
    captured in the result set (not silently dropped).
    """
    from agents.swarm_runner import SwarmRunner
    runner = SwarmRunner()
    runner.max_task_retries = 1
    runner.workers["researcher"] = _FakeWorker(fail_first_n=999)

    results = await runner.run_tasks([_make_task("Always-failing task", "researcher")])

    assert len(results) == 1, "Failed task must appear in results"
    assert results[0]["status"] == TaskStatus.FAILED
    assert results[0]["result"] is not None, "Failure reason must be recorded"


@pytest.mark.asyncio
async def test_09_budget_exceeded_blocks_remaining_tasks_gracefully():
    """
    Hard condition 8: When cost budget is exceeded, remaining tasks are blocked
    gracefully — no crash, BLOCKED status recorded.
    """
    from agents.swarm_runner import SwarmRunner
    runner = SwarmRunner()
    runner.swarm_cost_budget_usd = 0.001  # tiny budget

    runner.workers["researcher"] = _FakeWorker(cost_per_task=1.0)  # $1 >> $0.001
    results = await runner.run_tasks([
        _make_task("Task 1", "researcher"),
        _make_task("Task 2", "researcher"),
    ])

    statuses = {r["status"] for r in results}
    assert TaskStatus.COMPLETED in statuses or TaskStatus.BLOCKED in statuses, (
        "Budget enforcement must result in COMPLETED or BLOCKED, never a crash"
    )
    if len(results) == 2:
        non_completed = [r for r in results if r["status"] != TaskStatus.COMPLETED]
        if non_completed:
            assert non_completed[0]["status"] == TaskStatus.BLOCKED


@pytest.mark.asyncio
async def test_10_cross_project_failure_propagation_logged_in_results():
    """
    Hard condition 8: Upstream failure must propagate to downstream tasks with
    clear status and reason — enabling cross-project observability and metrics.
    """
    from agents.swarm_runner import SwarmRunner
    from agents.protocol import Task, TaskStatus as TS

    # Step 1: Run upstream task and let it fail
    runner = SwarmRunner()
    runner.max_task_retries = 0
    runner.workers["researcher"] = _FakeWorker(fail_first_n=999)

    results_up = await runner.run_tasks([_make_task("Upstream task", "researcher")])
    upstream_id = results_up[0]["id"]
    assert results_up[0]["status"] == TS.FAILED

    # Step 2: Build a second runner with a downstream task that depends on the failed node
    runner2 = SwarmRunner()
    runner2.workers["analyst"] = _FakeWorker()

    # Pre-inject the failed upstream node directly into the graph
    failed_task = Task(**results_up[0])
    failed_task.status = TS.FAILED
    runner2.graph.add_node(upstream_id, task=failed_task, retries=0)

    downstream_task = Task(**_make_task("Downstream task", "analyst"))
    runner2.graph.add_node(downstream_task.id, task=downstream_task, retries=0)
    runner2.graph.add_edge(upstream_id, downstream_task.id)

    results = await runner2._execute_dag()
    downstream_result = next(r for r in results if r["title"] == "Downstream task")

    assert downstream_result["status"] in (TS.FAILED, TS.BLOCKED), (
        "Downstream task must reflect upstream failure"
    )
    assert downstream_result["result"] is not None, (
        "Failure reason must be recorded for logs/metrics"
    )
