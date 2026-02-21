"""
P08 Legion — ManagerAgent
A Ray Actor that loads its system prompt via the skill system
(identical pattern to AgentRunner / base_agent.py), then uses
ModelManager to decompose a user request into a DAG of Tasks.
"""

import ray
import logging
from typing import List, Dict, Any, Optional

from agents.protocol import Task, TaskPriority, TaskStatus
from core.model_manager import ModelManager
from core.json_parser import parse_llm_json
from core.bootstrap import bootstrap_agents
from core.registry import AgentRegistry

logger = logging.getLogger(__name__)

AGENT_TYPE = "ManagerAgent"

def _load_prompt() -> str:
    """
    Load the ManagerAgent system prompt via the skill registry —
    the same mechanism used by AgentRunner in base_agent.py.
    """
    # Ensure registry is populated
    config = AgentRegistry.get(AGENT_TYPE)
    if not config:
        bootstrap_agents()
        config = AgentRegistry.get(AGENT_TYPE)

    if not config:
        raise RuntimeError(f"'{AGENT_TYPE}' not found in AgentRegistry. Check agent_config.yaml.")

    prompt_parts = []

    # Load skill prompt additions (same logic as base_agent.py lines ~67-97)
    try:
        from shared.state import get_skill_manager
        skill_manager = get_skill_manager()
        for skill_name in config.get("skills", []):
            skill = skill_manager.get_skill(skill_name)
            if skill:
                addition = skill.get_system_prompt_additions()
                if addition:
                    prompt_parts.append(addition)
    except Exception as e:
        logger.warning(f"Skill injection failed, falling back to empty prompt: {e}")

    return "\n\n".join(prompt_parts) if prompt_parts else f"You are {AGENT_TYPE}."


@ray.remote
class ManagerAgent:
    """
    Ray Actor — Manager Agent.

    Loads its system prompt from the skill registry (same as AgentRunner),
    calls an LLM to decompose a user request into a task DAG,
    and returns a list of serialized Task dicts.
    """

    def __init__(self, agent_id: str = "manager_001", model_name: Optional[str] = None):
        self.agent_id = agent_id
        self.model_name = model_name  # None → uses default from profiles.yaml
        self._prompt: Optional[str] = None  # Lazy-loaded on first call

    def _get_prompt(self) -> str:
        if self._prompt is None:
            self._prompt = _load_prompt()
        return self._prompt

    async def decompose_task(self, user_request: str) -> List[Dict[str, Any]]:
        """
        Decomposes a high-level user request into a DAG of Task dicts.

        Returns:
            List of serialized Task dicts with IDs, statuses, and
            dependency IDs fully resolved.
        """
        logger.info(f"[Manager:{self.agent_id}] Decomposing: {user_request[:80]}...")

        # Build final prompt: system prompt + user request
        system_prompt = self._get_prompt()
        full_prompt = f"{system_prompt}\n\n---\nUser Request: {user_request}\n---\nRespond with ONLY the JSON object:"

        # Call LLM via ModelManager
        try:
            mm = ModelManager(model_name=self.model_name)
            raw_response = await mm.generate_text(full_prompt)
        except Exception as e:
            logger.error(f"[Manager:{self.agent_id}] LLM call failed: {e}")
            raise RuntimeError(f"ManagerAgent LLM decomposition failed: {e}")

        # Parse structured JSON from LLM response
        try:
            parsed = parse_llm_json(raw_response)
            raw_tasks = parsed.get("tasks", [])
            if not raw_tasks:
                raise ValueError("LLM returned no tasks in decomposition.")
        except Exception as e:
            logger.error(
                f"[Manager:{self.agent_id}] JSON parse failed: {e}\nRaw response:\n{raw_response}"
            )
            raise RuntimeError(f"ManagerAgent failed to parse LLM response: {e}")

        # Build Task objects — resolve title-based depends_on → UUIDs
        title_to_task: Dict[str, Task] = {}
        ordered_tasks: List[Task] = []

        for raw in raw_tasks:
            task = Task(
                title=raw.get("title", "Unnamed Task"),
                description=raw.get("description", ""),
                assigned_to=raw.get("assigned_to", "researcher"),
                priority=TaskPriority(raw.get("priority", "medium")),
                dependencies=[],  # resolved in second pass
            )
            title_to_task[task.title] = task
            ordered_tasks.append(task)

        # Second pass: resolve title → ID dependencies
        for raw, task in zip(raw_tasks, ordered_tasks):
            for dep_title in raw.get("depends_on", []):
                dep_task = title_to_task.get(dep_title)
                if dep_task:
                    task.dependencies.append(dep_task.id)
                else:
                    logger.warning(
                        f"[Manager:{self.agent_id}] Dependency '{dep_title}' "
                        f"not found for task '{task.title}'."
                    )

        result = [t.model_dump() for t in ordered_tasks]
        logger.info(
            f"[Manager:{self.agent_id}] Decomposed into {len(result)} tasks: "
            + ", ".join(t["title"] for t in result)
        )
        return result

    async def reevaluate_plan(
        self,
        original_request: str,
        completed_tasks: List[Dict[str, Any]],
        failed_tasks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Re-plans when tasks fail — retries failed tasks with PENDING status.
        (Phase 2: will call LLM for smarter re-planning.)
        """
        logger.warning(
            f"[Manager:{self.agent_id}] Re-evaluating plan. "
            f"Completed: {len(completed_tasks)}, Failed: {len(failed_tasks)}"
        )
        retry_tasks = []
        for t in failed_tasks:
            t["status"] = TaskStatus.PENDING
            t["result"] = None
            retry_tasks.append(t)
        return retry_tasks
