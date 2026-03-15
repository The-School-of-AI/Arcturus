"""
routers/swarm.py — P08 Legion Swarm UI API
Endpoints:
  POST /api/swarm/run                   — start a new swarm run
  GET  /api/swarm/{run_id}/status       — DAG snapshot (task statuses)
  GET  /api/swarm/{run_id}/events       — SSE real-time event stream
  GET  /api/swarm/{run_id}/peek/{agent} — agent conversation log
  POST /api/swarm/{run_id}/intervene    — inject message / pause / reassign / abort
  GET  /api/swarm/templates             — list saved templates
  POST /api/swarm/templates             — save a template
  DELETE /api/swarm/templates/{name}    — delete a template
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agents.swarm_runner import SwarmRunner
from core.event_bus import event_bus

logger = logging.getLogger("routers.swarm")
router = APIRouter(tags=["Swarm"])

# ---------------------------------------------------------------------------
# In-memory registry of active SwarmRunner instances
# ---------------------------------------------------------------------------
_active_runs: dict[str, SwarmRunner] = {}

TEMPLATES_FILE = Path("storage/swarm_templates.json")
TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
if not TEMPLATES_FILE.exists():
    TEMPLATES_FILE.write_text("[]")


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class StartSwarmRequest(BaseModel):
    query: str
    token_budget: int = 8000
    cost_budget_usd: float = 0.10


class InterventionRequest(BaseModel):
    action: str          # "message" | "pause" | "resume" | "reassign" | "abort"
    agent_id: str | None = None
    content: str | None = None
    task_id: str | None = None
    new_role: str | None = None


class SaveTemplateRequest(BaseModel):
    name: str
    description: str = ""
    tasks_template: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_templates() -> list[dict]:
    try:
        return json.loads(TEMPLATES_FILE.read_text())
    except Exception:
        return []


def _save_templates(templates: list[dict]) -> None:
    TEMPLATES_FILE.write_text(json.dumps(templates, indent=2))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/run")
async def start_swarm_run(body: StartSwarmRequest, background_tasks: BackgroundTasks):
    """Start a new swarm run. Returns a run_id immediately; execution is async."""
    run_id = str(uuid.uuid4())
    runner = SwarmRunner(
        swarm_token_budget=body.token_budget,
        swarm_cost_budget_usd=body.cost_budget_usd,
    )
    _active_runs[run_id] = runner

    async def _run():
        try:
            await runner.initialize()
            await runner.run_request(body.query)
        except Exception as exc:
            logger.error(f"[Swarm:{run_id}] run failed: {exc}")

    background_tasks.add_task(_run)
    logger.info(f"[Swarm] Started run {run_id} for query: {body.query!r}")
    return {"run_id": run_id, "status": "started"}


@router.get("/templates")
async def list_templates():
    return _load_templates()


@router.post("/templates")
async def save_template(body: SaveTemplateRequest):
    templates = _load_templates()
    templates = [t for t in templates if t.get("name") != body.name]  # upsert
    templates.append(body.model_dump())
    _save_templates(templates)
    return {"saved": body.name}


@router.delete("/templates/{name}")
async def delete_template(name: str):
    templates = [t for t in _load_templates() if t.get("name") != name]
    _save_templates(templates)
    return {"deleted": name}


@router.get("/{run_id}/status")
async def get_run_status(run_id: str):
    """Return a snapshot of all tasks and their current statuses."""
    runner = _active_runs.get(run_id)
    if runner is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
    return {
        "run_id": run_id,
        "tasks": runner.get_dag_snapshot(),
        "tokens_used": runner._tokens_used,
        "cost_usd": runner._cost_usd,
        "paused": runner._paused.is_set() if hasattr(runner, "_paused") else False,
    }


@router.get("/{run_id}/events")
async def swarm_event_stream(run_id: str, request: Request):
    """
    SSE stream scoped to a single swarm run.
    Events: task_progress, task_done, swarm_done, intervention_ack
    """
    if run_id not in _active_runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")

    queue = await event_bus.subscribe()

    async def generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except TimeoutError:
                    # heartbeat to keep connection alive
                    yield {"event": "heartbeat", "data": "{}"}
                    continue

                # Filter: only forward events tagged with this run_id or untagged swarm events
                data = event.get("data", {})
                if data.get("run_id") in (run_id, None):
                    yield {
                        "event": event.get("type", "message"),
                        "data": json.dumps(event),
                    }
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(queue)

    return EventSourceResponse(generator())


@router.get("/{run_id}/peek/{agent_id}")
async def peek_agent(run_id: str, agent_id: str):
    """Return the latest conversation log for a single agent."""
    runner = _active_runs.get(run_id)
    if runner is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
    log = runner.get_agent_log(agent_id)
    return {"run_id": run_id, "agent_id": agent_id, "log": log}


@router.post("/{run_id}/intervene")
async def intervene(run_id: str, body: InterventionRequest):
    """Manual intervention: pause, resume, send message, reassign, or abort."""
    runner = _active_runs.get(run_id)
    if runner is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")

    action = body.action.lower()

    if action == "pause":
        await runner.pause()
        return {"action": "pause", "status": "ok"}

    elif action == "resume":
        await runner.resume()
        return {"action": "resume", "status": "ok"}

    elif action == "message":
        if not body.agent_id or not body.content:
            raise HTTPException(status_code=422, detail="agent_id and content required for 'message' action")
        await runner.inject_message(body.agent_id, body.content)
        return {"action": "message", "agent_id": body.agent_id, "status": "sent"}

    elif action == "reassign":
        if not body.task_id or not body.new_role:
            raise HTTPException(status_code=422, detail="task_id and new_role required for 'reassign' action")
        await runner.reassign_task(body.task_id, body.new_role)
        return {"action": "reassign", "task_id": body.task_id, "new_role": body.new_role, "status": "ok"}

    elif action == "abort":
        if not body.task_id:
            raise HTTPException(status_code=422, detail="task_id required for 'abort' action")
        await runner.abort_task(body.task_id)
        return {"action": "abort", "task_id": body.task_id, "status": "ok"}

    else:
        raise HTTPException(status_code=422, detail=f"Unknown action: {action!r}")
