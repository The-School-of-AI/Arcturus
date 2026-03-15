
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
    def __init__(
        self,
        swarm_token_budget: int | None = None,
        swarm_cost_budget_usd: float | None = None,
        max_task_retries: int | None = None,
        task_timeout_seconds: int | None = None,
    ):
        self.manager: ManagerAgent | None = None
        self.workers: dict[str, WorkerAgent] = {}
        self.graph: nx.DiGraph = nx.DiGraph()

        # Load swarm strategy settings from profiles.yaml
        # (same pattern as AgentLoop4 reading max_steps)
        profile = get_profile()
        self.max_task_retries: int = max_task_retries if max_task_retries is not None else profile.get("strategy.max_task_retries", 2)
        self.swarm_token_budget: int = swarm_token_budget if swarm_token_budget is not None else profile.get("strategy.swarm_token_budget", 50000)
        self.swarm_cost_budget_usd: float = swarm_cost_budget_usd if swarm_cost_budget_usd is not None else profile.get("strategy.swarm_cost_budget_usd", 0.50)
        self.task_timeout_seconds: int = task_timeout_seconds if task_timeout_seconds is not None else profile.get("strategy.task_timeout_seconds", 300)

        # Runtime accumulators (reset each run_tasks call)
        self._tokens_used: int = 0
        self._cost_usd: float = 0.0

        # Pause support for UI manual intervention
        self._paused: asyncio.Event = asyncio.Event()  # set = paused, clear = running
        self._agent_logs: dict[str, list[dict]] = {}   # agent_id → conversation log


    async def initialize(self):
        """Initializes Ray and the Manager Agent."""
        if not ray.is_initialized():
            ray.init(ignore_reinit_error=True)
            logger.info("Ray initialized.")

        self.manager = ManagerAgent.remote()  # type: ignore[attr-defined]
        logger.info("Manager Agent initialized.")

    async def run_request(self, user_request: str, session_id: str | None = None) -> list[dict[str, Any]]:
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

        return await self.run_tasks(task_dicts, session_id=session_id)

    async def build_pipeline_graph(self, tasks: list[dict[str, Any]], session_id: str | None = None) -> list[dict[str, Any]]:
        """
        Executes a set of tasks in a strict linear Pipeline topology.
        Automatically wires dependencies as A -> B -> C regardless of the input payload.
        """
        for i in range(1, len(tasks)):
            tasks[i]["dependencies"] = [tasks[i-1].get("id", f"task_{i-1}")]
        return await self.run_tasks(tasks, session_id=session_id)

    async def build_consensus_graph(self, parallel_tasks: list[dict[str, Any]], judge_task: dict[str, Any], session_id: str | None = None) -> list[dict[str, Any]]:
        """
        Executes a set of parallel tasks (e.g., multiple agents researching the same topic)
        and funnels all their outputs into a final Judge task for synthesis/consensus.
        """
        judge_task["dependencies"] = [t.get("id") for t in parallel_tasks]
        tasks = parallel_tasks + [judge_task]
        return await self.run_tasks(tasks, session_id=session_id)

    async def run_tasks(self, task_dicts: list[dict[str, Any]], session_id: str | None = None) -> list[dict[str, Any]]:
        """
        Builds the DAG from a list of task dicts and executes it.
        Can be called directly in tests to bypass the LLM decomposition step.
        """
        import uuid
        self.session_id = session_id or f"swarm_{uuid.uuid4().hex[:8]}"

        # Reset graph and budget accumulators for fresh run
        self.graph = nx.DiGraph()
        self.graph.graph["session_id"] = self.session_id
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

                # 📼 Chronicle: emit STEP_START
                try:
                    import asyncio

                    from session.capture import get_capture
                    from session.schema import EventType

                    _chronicle = get_capture()
                    _sid = self.session_id

                    asyncio.create_task(_chronicle.emit(
                        EventType.STEP_START,
                        {
                            "step_id": task.id,
                            "agent": task.assigned_to,
                            "task_title": task.title,
                        },
                        session_id=_sid,
                    ))
                except Exception as exc:
                    logger.debug(f"[SwarmRunner] Chronicle STEP_START emit failed: {exc}")

                worker = self.workers[task.assigned_to]
                future = worker.process_task.remote(task.model_dump())  # type: ignore[attr-defined]
                futures_map[future] = node_id

            # Await and handle results asynchronously to avoid head-of-line blocking
            async def _wait_and_catch(fut, nid, timeout):
                import asyncio
                try:
                    res = await asyncio.wait_for(fut, timeout=timeout)
                    return nid, res, None
                except Exception as e:
                    return nid, None, e

            import asyncio
            wait_tasks = [
                asyncio.create_task(_wait_and_catch(fut, nid, getattr(self, 'task_timeout_seconds', 300)))
                for fut, nid in futures_map.items()
            ]

            for completed_task in asyncio.as_completed(wait_tasks):
                node_id, res, err = await completed_task
                task = self.graph.nodes[node_id]["task"]
                retries = self.graph.nodes[node_id]["retries"]

                if err:
                    e = err
                    if retries < self.max_task_retries:
                        logger.warning(
                            f"Task '{task.title}' failed (attempt {retries + 1}/{self.max_task_retries}). Retrying... Error: {e}"
                        )
                        self.graph.nodes[node_id]["retries"] += 1
                        # Task stays in graph, will be picked up in next iteration
                    else:
                        logger.error(
                            f"Task '{task.title}' failed after {retries + 1} attempts."
                        )
                        task.status = TaskStatus.FAILED
                        task.result = f"Failed after {retries + 1} attempts: {type(e).__name__} - {e}"
                        failed_tasks[node_id] = task

                        # 📼 Chronicle: emit STEP_FAILED and checkpoint
                        try:
                            import asyncio

                            import networkx as nx

                            from session.capture import get_capture
                            from session.checkpoint import create_checkpoint
                            from session.schema import EventType

                            _chronicle = get_capture()
                            _sid = self.session_id

                            asyncio.create_task(_chronicle.emit(
                                EventType.STEP_FAILED,
                                {
                                    "step_id": task.id,
                                    "agent": task.assigned_to,
                                    "error": str(e),
                                },
                                session_id=_sid,
                            ))

                            create_checkpoint(_sid, "step_failed", self.graph, last_sequence=_chronicle.get_last_sequence(_sid))
                        except Exception as exc:
                            logger.debug(f"[SwarmRunner] Chronicle STEP_FAILED failed: {exc}")
                else:
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

                    # 📼 Chronicle: emit STEP_COMPLETE and checkpoint
                    try:
                        import asyncio

                        import networkx as nx

                        from session.capture import get_capture
                        from session.checkpoint import create_checkpoint
                        from session.schema import EventType

                        _chronicle = get_capture()
                        _sid = self.session_id

                        asyncio.create_task(_chronicle.emit(
                            EventType.STEP_COMPLETE,
                            {
                                "step_id": t_obj.id,
                                "agent": t_obj.assigned_to,
                                "cost": t_obj.cost_usd,
                                "input_tokens": t_obj.token_used,
                                "output_tokens": 0,
                                "status": "completed",
                            },
                            session_id=_sid,
                        ))

                        create_checkpoint(_sid, "step_complete", self.graph, last_sequence=_chronicle.get_last_sequence(_sid))
                    except Exception as exc:
                        logger.debug(f"[SwarmRunner] Chronicle STEP_COMPLETE failed: {exc}")

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
                        import asyncio as _asyncio
                        for f in futures_map:
                            if _asyncio.iscoroutine(f):
                                f.close()
                        break

        all_tasks = list(completed_tasks.values()) + list(failed_tasks.values())
        return [t.model_dump() for t in all_tasks]

    # ------------------------------------------------------------------
    # Swarm UI control methods
    # ------------------------------------------------------------------

    def get_dag_snapshot(self) -> list[dict]:
        """Return a JSON-serialisable snapshot of all tasks and their statuses."""
        snapshot = []
        for node_id, data in self.graph.nodes(data=True):
            task: Task | None = data.get("task")
            if task is None:
                continue
            snapshot.append({
                "task_id": task.id,
                "title": task.title,
                "status": task.status.value,
                "assigned_to": task.assigned_to,
                "priority": task.priority.value,
                "dependencies": list(self.graph.predecessors(node_id)),
                "token_used": task.token_used,
                "cost_usd": task.cost_usd,
                "result": task.result,
            })
        return snapshot

    async def pause(self) -> None:
        """Pause DAG execution between task dispatches."""
        self._paused.set()
        logger.info("[SwarmRunner] Paused by user intervention.")

    async def resume(self) -> None:
        """Resume a paused swarm."""
        self._paused.clear()
        logger.info("[SwarmRunner] Resumed by user intervention.")

    async def inject_message(self, agent_id: str, content: str) -> None:
        """Route an AgentMessage to a specific worker actor."""
        from agents.protocol import AgentMessage
        worker = self.workers.get(agent_id)
        if worker is None:
            raise ValueError(f"Worker {agent_id!r} not found")
        msg = AgentMessage(
            from_agent="user",
            to_agent=agent_id,
            task_id="intervention",
            content=content,
        )
        await worker.process_message.remote(msg.model_dump())  # type: ignore[attr-defined]
        logger.info(f"[SwarmRunner] Injected message to {agent_id!r}.")

    async def reassign_task(self, task_id: str, new_role: str) -> None:
        """Reassign a task to a different worker role (spawning one if needed)."""
        for node_id, data in self.graph.nodes(data=True):
            task: Task | None = data.get("task")
            if task and task.id == task_id:
                task.assigned_to = new_role
                task.status = TaskStatus.PENDING
                if new_role not in self.workers:
                    self.workers[new_role] = WorkerAgent.remote(  # type: ignore[attr-defined]
                        agent_id=f"worker_{new_role}", role=new_role
                    )
                logger.info(f"[SwarmRunner] Task {task_id!r} reassigned to {new_role!r}.")
                return
        raise ValueError(f"Task {task_id!r} not found in DAG")

    async def abort_task(self, task_id: str) -> None:
        """Immediately mark a task as FAILED."""
        for node_id, data in self.graph.nodes(data=True):
            task: Task | None = data.get("task")
            if task and task.id == task_id:
                task.status = TaskStatus.FAILED
                task.result = "Aborted by user intervention."
                logger.info(f"[SwarmRunner] Task {task_id!r} aborted.")
                return
        raise ValueError(f"Task {task_id!r} not found in DAG")

    def get_agent_log(self, agent_id: str) -> list[dict]:
        """Return the conversation log recorded for agent_id (or empty list)."""
        return self._agent_logs.get(agent_id, [])

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
