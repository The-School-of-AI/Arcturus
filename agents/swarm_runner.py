
import asyncio
import logging
from typing import Any

import networkx as nx
import ray

from agents.manager import ManagerAgent
from agents.protocol import Task, TaskPriority, TaskStatus
from agents.worker import WorkerAgent
from core.profile_loader import get_profile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SwarmRunner:
    def __init__(self):
        self.manager: ManagerAgent | None = None
        self.workers: dict[str, WorkerAgent] = {}
        self.graph: nx.DiGraph = nx.DiGraph()

        # Load swarm strategy settings from profiles.yaml
        # (same pattern as AgentLoop4 reading max_steps)
        profile = get_profile()
        self.max_task_retries: int = profile.get("strategy.max_task_retries", 2)
        self.swarm_token_budget: int = profile.get("strategy.swarm_token_budget", 50000)
        self.swarm_cost_budget_usd: float = profile.get("strategy.swarm_cost_budget_usd", 0.50)

        # Runtime accumulators (reset each run_tasks call)
        self._tokens_used: int = 0
        self._cost_usd: float = 0.0

    async def initialize(self):
        """Initializes Ray and the Manager Agent."""
        if not ray.is_initialized():
            ray.init(ignore_reinit_error=True)
            logger.info("Ray initialized.")

        self.manager = ManagerAgent.remote()  # type: ignore[attr-defined]
        logger.info("Manager Agent initialized.")

    async def run_request(self, user_request: str) -> list[dict[str, Any]]:
        """
        Main entry point:
        1. Decompose request into tasks (via LLM ManagerAgent).
        2. Build execution DAG.
        3. Execute tasks with retry on failure.
        """
        logger.info(f"SwarmRunner receiving request: {user_request}")

        # 1. Decompose
        task_dicts = await self.manager.decompose_task.remote(user_request)  # type: ignore[union-attr]
        logger.info(f"Decomposed into {len(task_dicts)} tasks.")

        return await self.run_tasks(task_dicts)

    async def run_tasks(self, task_dicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Builds the DAG from a list of task dicts and executes it.
        Can be called directly in tests to bypass the LLM decomposition step.
        """
        # Reset graph and budget accumulators for fresh run
        self.graph = nx.DiGraph()
        self._tokens_used = 0
        self._cost_usd = 0.0

        # Priority weights for budget allocation
        _priority_weight = {
            TaskPriority.CRITICAL: 4,
            TaskPriority.HIGH: 3,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 1,
        }

        # Build Graph & Instantiate Workers
        task_objs = [Task(**t_data) for t_data in task_dicts]
        total_weight = sum(_priority_weight.get(t.priority, 2) for t in task_objs)

        for task in task_objs:
            # Allocate proportional token budget
            weight = _priority_weight.get(task.priority, 2)
            task.token_budget = int(self.swarm_token_budget * weight / total_weight)

            self.graph.add_node(task.id, task=task, retries=0)

            role = task.assigned_to
            if role and role not in self.workers:
                self.workers[role] = WorkerAgent.remote(  # type: ignore[attr-defined]
                    agent_id=f"worker_{role}", role=role
                )

            for dep_id in task.dependencies:
                if dep_id in self.graph.nodes:
                    self.graph.add_edge(dep_id, task.id)

        results = await self._execute_dag()
        return results

    async def _execute_dag(self) -> list[dict[str, Any]]:
        """
        Executes the task DAG respecting dependencies.
        Implements per-task retry on failure (up to MAX_TASK_RETRIES).
        Returns all completed task dicts (failed tasks are included with FAILED status).
        """
        completed_tasks: dict[str, Task] = {}
        failed_tasks: dict[str, Task] = {}

        # Pre-populate from nodes that already carry a terminal status.
        # This supports resumed/injected graphs (e.g. test_10 injects a pre-failed node).
        for node_id in self.graph.nodes:
            node_task = self.graph.nodes[node_id]["task"]
            if node_task.status == TaskStatus.COMPLETED:
                completed_tasks[node_id] = node_task
            elif node_task.status in (TaskStatus.FAILED, TaskStatus.BLOCKED):
                failed_tasks[node_id] = node_task

        while len(completed_tasks) + len(failed_tasks) < len(self.graph.nodes):
            # Find ready nodes: not processed AND all predecessors completed
            ready_nodes = [
                node_id
                for node_id in self.graph.nodes
                if node_id not in completed_tasks
                and node_id not in failed_tasks
                and all(p in completed_tasks for p in self.graph.predecessors(node_id))
            ]

            if not ready_nodes:
                # Remaining nodes are blocked by failed dependencies — mark them failed
                blocked = [
                    node_id
                    for node_id in self.graph.nodes
                    if node_id not in completed_tasks and node_id not in failed_tasks
                ]
                for node_id in blocked:
                    task = self.graph.nodes[node_id]["task"]
                    task.status = TaskStatus.FAILED
                    task.result = "Blocked: upstream dependency failed."
                    failed_tasks[node_id] = task
                    logger.warning(f"Task {task.title} blocked by upstream failure.")
                break

            logger.info(f"Ready tasks to execute: {ready_nodes}")

            # Submit all ready tasks in parallel
            futures_map = {}  # future → node_id
            for node_id in ready_nodes:
                task = self.graph.nodes[node_id]["task"]
                worker = self.workers[task.assigned_to]
                future = worker.process_task.remote(task.model_dump())  # type: ignore[attr-defined]
                futures_map[future] = node_id

            # Await and handle results individually
            for future, node_id in futures_map.items():
                task = self.graph.nodes[node_id]["task"]
                retries = self.graph.nodes[node_id]["retries"]
                try:
                    res = await future
                    t_obj = Task(**res)
                    self.graph.nodes[node_id]["task"] = t_obj
                    completed_tasks[node_id] = t_obj

                    # Accumulate budget usage
                    self._tokens_used += t_obj.token_used
                    self._cost_usd += t_obj.cost_usd
                    logger.info(
                        f"Task '{t_obj.title}' completed. "
                        f"Cost so far: ${self._cost_usd:.4f} / ${self.swarm_cost_budget_usd:.2f}"
                    )

                    # Hard budget stop
                    if self._cost_usd >= self.swarm_cost_budget_usd:
                        logger.warning(
                            f"Budget exceeded: ${self._cost_usd:.4f} >= ${self.swarm_cost_budget_usd:.2f}. "
                            "Blocking remaining tasks."
                        )
                        remaining = [
                            nid for nid in self.graph.nodes
                            if nid not in completed_tasks and nid not in failed_tasks
                        ]
                        for nid in remaining:
                            t = self.graph.nodes[nid]["task"]
                            t.status = TaskStatus.BLOCKED
                            t.result = "Blocked: swarm cost budget exceeded."
                            failed_tasks[nid] = t
                        # Close any unawaited coroutine futures from this batch
                        # (no-op for real Ray ObjectRefs; prevents warning with in-process test doubles)
                        import asyncio as _asyncio
                        for f in futures_map:
                            if _asyncio.iscoroutine(f):
                                f.close()
                        break

                except Exception as e:
                    if retries < self.max_task_retries:
                        logger.warning(
                            f"Task '{task.title}' failed (attempt {retries + 1}/{self.max_task_retries}). Retrying... Error: {e}"
                        )
                        self.graph.nodes[node_id]["retries"] += 1
                        # Task stays in graph, will be picked up in next iteration
                    else:
                        logger.error(
                            f"Task '{task.title}' failed after {retries + 1} attempts. Marking FAILED."
                        )
                        task.status = TaskStatus.FAILED
                        task.result = f"Failed after {retries + 1} attempts: {e}"
                        failed_tasks[node_id] = task

        all_tasks = list(completed_tasks.values()) + list(failed_tasks.values())
        return [t.model_dump() for t in all_tasks]

    async def shutdown(self):
        ray.shutdown()


# CLI entry point for testing
if __name__ == "__main__":
    async def main():
        import json
        runner = SwarmRunner()
        await runner.initialize()
        results = await runner.run_request("Research quantum computing and write a summary.")
        print(json.dumps(results, indent=2, default=str))
        await runner.shutdown()

    asyncio.run(main())
