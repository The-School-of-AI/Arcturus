
import ray
import asyncio
import networkx as nx
from typing import List, Dict, Any, Optional
from agents.manager import ManagerAgent
from agents.worker import WorkerAgent
from agents.protocol import Task, TaskStatus
from core.profile_loader import get_profile
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SwarmRunner:
    def __init__(self):
        self.manager: Optional[ManagerAgent] = None
        self.workers: Dict[str, WorkerAgent] = {}
        self.graph: nx.DiGraph = nx.DiGraph()

        # Load swarm strategy settings from profiles.yaml
        # (same pattern as AgentLoop4 reading max_steps)
        profile = get_profile()
        self.max_task_retries: int = profile.get("strategy.max_task_retries", 2)

    async def initialize(self):
        """Initializes Ray and the Manager Agent."""
        if not ray.is_initialized():
            ray.init(ignore_reinit_error=True)
            logger.info("Ray initialized.")

        self.manager = ManagerAgent.remote()
        logger.info("Manager Agent initialized.")

    async def run_request(self, user_request: str) -> List[Dict[str, Any]]:
        """
        Main entry point:
        1. Decompose request into tasks (via LLM ManagerAgent).
        2. Build execution DAG.
        3. Execute tasks with retry on failure.
        """
        logger.info(f"SwarmRunner receiving request: {user_request}")

        # 1. Decompose
        task_dicts = await self.manager.decompose_task.remote(user_request)
        logger.info(f"Decomposed into {len(task_dicts)} tasks.")

        return await self.run_tasks(task_dicts)

    async def run_tasks(self, task_dicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Builds the DAG from a list of task dicts and executes it.
        Can be called directly in tests to bypass the LLM decomposition step.
        """
        # Reset graph for fresh run
        self.graph = nx.DiGraph()

        # Build Graph & Instantiate Workers
        for t_data in task_dicts:
            task = Task(**t_data)
            self.graph.add_node(task.id, task=task, retries=0)

            role = task.assigned_to
            if role not in self.workers:
                self.workers[role] = WorkerAgent.remote(
                    agent_id=f"worker_{role}", role=role
                )

            for dep_id in task.dependencies:
                if dep_id in self.graph.nodes:
                    self.graph.add_edge(dep_id, task.id)

        results = await self._execute_dag()
        return results

    async def _execute_dag(self) -> List[Dict[str, Any]]:
        """
        Executes the task DAG respecting dependencies.
        Implements per-task retry on failure (up to MAX_TASK_RETRIES).
        Returns all completed task dicts (failed tasks are included with FAILED status).
        """
        completed_tasks: Dict[str, Task] = {}
        failed_tasks: Dict[str, Task] = {}

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
                future = worker.process_task.remote(task.model_dump())
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
                    logger.info(f"Task '{t_obj.title}' completed via {t_obj.assigned_to}.")
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
