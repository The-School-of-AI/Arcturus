"""
agents/worker.py — P08 Legion WorkerAgent

Architecture:
    SwarmRunner → WorkerAgent.process_task() [Ray Actor]
                      ↓
                  AgentRunner.run_agent()         ← full skill/tool/memory pipeline
                      ↓
                  ModelManager.generate_text()

The WorkerAgent is a thin Ray Actor shell. All execution intelligence lives in
AgentRunner (base_agent.py), which handles skill injection, MCP tool routing,
memory retrieval, and prompt construction.

Responsibilities:
  1. Accept a Task dict (from SwarmRunner) or an AgentMessage dict (from Manager).
  2. Map the task's role → registered AgentType → AgentRunner.run_agent().
  3. Manage a lazy, role-scoped MultiMCP instance (starts only the MCP servers
     the role's AgentType actually needs, per agent_config.yaml).
  4. Emit task_progress events at 0% / 50% / 100% (§8.2).
  5. Populate token_used and cost_usd from AgentRunner output (§8.3).
  6. Report result back to SwarmRunner via the updated Task dict.
"""

import logging
from typing import Any

import ray

from agents.base_agent import AgentRunner
from agents.protocol import AgentMessage, Task, TaskStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role → AgentType mapping
# Maps the department role names (Task.assigned_to) to agents registered
# in agent_config.yaml / AgentRegistry.
# ---------------------------------------------------------------------------
ROLE_AGENT_TYPE: dict[str, str] = {
    # Research department
    "researcher":           "RetrieverAgent",
    "web_researcher":       "RetrieverAgent",
    "academic_researcher":  "RetrieverAgent",
    "data_analyst":         "ThinkerAgent",
    # Engineering department
    "architect":            "PlannerAgent",
    "coder":                "CoderAgent",
    "reviewer":             "QAAgent",
    # Content department
    "writer":               "DistillerAgent",
    "editor":               "FormatterAgent",
    "designer":             "FormatterAgent",
    # Business department
    "strategist":           "PlannerAgent",
    "analyst":              "ThinkerAgent",
    "communicator":         "DistillerAgent",
}

# Fallback when a role has no explicit mapping
_DEFAULT_AGENT_TYPE = "ThinkerAgent"


# ---------------------------------------------------------------------------
# WorkerAgent Ray Actor
# ---------------------------------------------------------------------------

@ray.remote
class WorkerAgent:
    """
    Ray Actor — Worker Agent.

    Wraps AgentRunner so that each Ray subprocess has its own isolated
    MultiMCP + AgentRunner instance. MCP servers are started lazily on the
    first process_task() call for this actor.

    SwarmRunner interface:
        future = worker.process_task.remote(task.model_dump())
        result = await future   # → updated task dict

    Manager AgentMessage interface:
        future = worker.process_message.remote(agent_message.model_dump())
        reply  = await future   # → AgentMessage dict
    """

    def __init__(self, agent_id: str, role: str):
        self.agent_id = agent_id
        self.role = role
        self.agent_type = ROLE_AGENT_TYPE.get(role.lower(), _DEFAULT_AGENT_TYPE)

        # Lazy-initialised on first task — avoids Ray actor init delay
        self._runner: AgentRunner | None = None
        self._multi_mcp: Any = None  # MultiMCP — typed Any, deferred import

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------

    async def _ensure_runner(self) -> AgentRunner:
        """
        Initialise MultiMCP (starting only the servers this role needs)
        and wrap it in an AgentRunner. Called once per actor lifetime.
        """
        if self._runner is not None:
            return self._runner

        from core.bootstrap import bootstrap_agents
        from core.registry import AgentRegistry
        from mcp_servers.multi_mcp import MultiMCP

        # Ensure registry is loaded
        if not AgentRegistry.get(self.agent_type):
            bootstrap_agents()

        config = AgentRegistry.get(self.agent_type) or {}
        required_servers = config.get("mcp_servers", [])

        multi_mcp = MultiMCP()

        # Start only the MCP servers this role actually uses
        if required_servers:
            for server_name in required_servers:
                if server_name in multi_mcp.server_configs:
                    try:
                        await multi_mcp._start_server(
                            server_name,
                            multi_mcp.server_configs[server_name]
                        )
                    except Exception as exc:
                        logger.warning(
                            f"[Worker:{self.agent_id}] Could not start MCP server "
                            f"'{server_name}': {exc}"
                        )

        self._multi_mcp = multi_mcp
        self._runner = AgentRunner(multi_mcp=multi_mcp)

        logger.info(
            f"[Worker:{self.agent_id}] Initialised as {self.agent_type}. "
            f"MCP servers: {required_servers or 'none'}"
        )
        return self._runner

    # ------------------------------------------------------------------
    # Progress events (§8.2)
    # ------------------------------------------------------------------

    async def _emit_progress(self, task_id: str, title: str, pct: int,
                             result: str | None = None) -> None:
        """
        Publish a task_progress event on the actor-local event bus.
        Cross-process forwarding to the UI is a Days 11-15 concern.
        """
        try:
            from core.event_bus import event_bus
            payload: dict[str, Any] = {
                "task_id":        task_id,
                "title":          title,
                "assigned_to":    self.role,
                "completion_pct": pct,
            }
            if result is not None:
                payload["result"] = result
            await event_bus.publish("task_progress", self.agent_id, payload)
        except Exception as exc:
            logger.warning(f"[Worker:{self.agent_id}] Progress event failed: {exc}")

    # ------------------------------------------------------------------
    # Public interface — Task dict
    # ------------------------------------------------------------------

    async def process_task(self, task_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Main entry point called by SwarmRunner.

        Args:
            task_dict: Serialised Task (Task.model_dump()).

        Returns:
            Updated task dict:
              status     → COMPLETED or FAILED
              result     → AgentRunner text output or error message
              token_used → tokens consumed (from AgentRunner cost calc)
              cost_usd   → estimated USD cost
        """
        task    = Task(**task_dict)
        task_id = task.id
        title   = task.title

        # ── 0%: received ──────────────────────────────────────────────
        await self._emit_progress(task_id, title, pct=0)
        logger.info(
            f"[Worker:{self.agent_id}] ({self.role} → {self.agent_type}) "
            f"starting: '{title}'"
        )
        task.status = TaskStatus.IN_PROGRESS

        # ── Initialise AgentRunner (once per actor) ────────────────────
        try:
            runner = await self._ensure_runner()
        except Exception as exc:
            logger.error(f"[Worker:{self.agent_id}] Runner init failed: {exc}")
            task.status = TaskStatus.FAILED
            task.result = f"Worker initialisation failed: {exc}"
            task.token_used = 0
            task.cost_usd = 0.0
            await self._emit_progress(task_id, title, pct=100, result=task.result)
            return task.model_dump()

        # ── 50%: calling AgentRunner ───────────────────────────────────
        await self._emit_progress(task_id, title, pct=50)

        # Build the input_data dict that AgentRunner.run_agent() accepts
        input_data: dict[str, Any] = {
            "task":        task.description,
            "title":       task.title,
            "priority":    task.priority.value,
            "assigned_to": task.assigned_to,
        }
        if task.token_budget:
            input_data["token_budget"] = task.token_budget

        try:
            agent_output: dict[str, Any] = await runner.run_agent(
                agent_type=self.agent_type,
                input_data=input_data,
            )
        except Exception as exc:
            logger.error(f"[Worker:{self.agent_id}] AgentRunner failed: {exc}")
            task.status = TaskStatus.FAILED
            task.result = f"AgentRunner error: {exc}"
            task.token_used = 0
            task.cost_usd = 0.0
            await self._emit_progress(task_id, title, pct=100, result=task.result)
            return task.model_dump()

        # ── 100%: done ─────────────────────────────────────────────────
        # AgentRunner returns a dict; extract result text and usage
        result_text: str = (
            agent_output.get("result")
            or agent_output.get("output")
            or agent_output.get("response")
            or str(agent_output)
        )

        # Cost / token data — AgentRunner may include this via calculate_cost()
        cost_info: dict[str, Any] = agent_output.get("cost_info", {})
        task.token_used = int(cost_info.get("total_tokens", 0))
        task.cost_usd   = float(cost_info.get("cost", 0.0))

        task.status = TaskStatus.COMPLETED
        task.result = result_text.strip() if isinstance(result_text, str) else str(result_text)

        await self._emit_progress(task_id, title, pct=100, result=task.result)
        logger.info(
            f"[Worker:{self.agent_id}] completed '{title}'. "
            f"Tokens: {task.token_used}, Cost: ${task.cost_usd:.6f}"
        )
        return task.model_dump()

    # ------------------------------------------------------------------
    # Public interface — AgentMessage
    # ------------------------------------------------------------------

    async def process_message(self, message_dict: dict[str, Any]) -> dict[str, Any]:
        """
        AgentMessage interface (§8.2 — 'Accept AgentMessage').

        Accepts an AgentMessage from the ManagerAgent, extracts the Task
        payload, delegates to process_task(), and returns an AgentMessage
        reply so the Manager can correlate results.

        Args:
            message_dict: AgentMessage.model_dump() from ManagerAgent.

        Returns:
            AgentMessage.model_dump() with task result in metadata['task'].
        """
        msg = AgentMessage(**message_dict)
        logger.info(
            f"[Worker:{self.agent_id}] AgentMessage {msg.id} "
            f"from '{msg.from_agent}' task_id='{msg.task_id}'"
        )

        # Extract task payload from message metadata; fall back to message content
        task_payload: dict[str, Any] | None = msg.metadata.get("task")
        if not task_payload:
            task_payload = {
                "title":       f"Task from {msg.from_agent}",
                "description": msg.content,
                "assigned_to": self.role,
            }

        updated_task = await self.process_task(task_payload)

        status      = updated_task.get("status", TaskStatus.FAILED)
        result_text = updated_task.get("result", "")

        reply = AgentMessage(
            from_agent=self.agent_id,
            to_agent=msg.from_agent,
            task_id=msg.task_id,
            content=(
                f"Task '{updated_task.get('title', '')}' {status}. "
                f"Summary: {str(result_text)[:300]}"
            ),
            metadata={
                "task":       updated_task,
                "token_used": updated_task.get("token_used", 0),
                "cost_usd":   updated_task.get("cost_usd", 0.0),
            },
        )
        return reply.model_dump()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def ping(self) -> str:
        """Health-check. SwarmRunner can call this to verify the actor is alive."""
        return "pong"

    async def shutdown(self) -> None:
        """Cleanly stop all MCP server subprocesses for this actor."""
        if self._multi_mcp is not None:
            try:
                await self._multi_mcp.stop()
                logger.info(f"[Worker:{self.agent_id}] MCP servers stopped.")
            except Exception as exc:
                logger.warning(f"[Worker:{self.agent_id}] MCP stop failed: {exc}")
