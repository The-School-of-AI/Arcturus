from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from shared.state import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data" / "gateway"
INTEGRATION_EVENTS_FILE = DATA_DIR / "integration_events.jsonl"


_file_locks: dict[Path, asyncio.Lock] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_lock(path: Path) -> asyncio.Lock:
    lock = _file_locks.get(path)
    if lock is None:
        lock = asyncio.Lock()
        _file_locks[path] = lock
    return lock


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


class IntegrationTracer:
    def __init__(self, events_file: Path = INTEGRATION_EVENTS_FILE):
        self.events_file = events_file

    async def record(
        self,
        trace_id: str,
        flow: str,
        stage: str,
        status: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        event = {
            "trace_id": trace_id,
            "flow": flow,
            "stage": stage,
            "status": status,
            "timestamp": _utc_now_iso(),
            "context": context or {},
        }

        async with _get_lock(self.events_file):
            _append_jsonl(self.events_file, event)

        return event

    async def list_events(
        self,
        trace_id: str | None = None,
        flow: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not self.events_file.exists():
            return []

        rows: list[dict[str, Any]] = []
        for raw_line in self.events_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            if trace_id and item.get("trace_id") != trace_id:
                continue
            if flow and item.get("flow") != flow:
                continue
            rows.append(item)

        return rows[-max(1, limit) :]


_integration_tracer: IntegrationTracer | None = None


def get_integration_tracer() -> IntegrationTracer:
    global _integration_tracer
    if _integration_tracer is None:
        _integration_tracer = IntegrationTracer()
    return _integration_tracer


async def record_integration_event(
    trace_id: str,
    flow: str,
    stage: str,
    status: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return await get_integration_tracer().record(
        trace_id=trace_id,
        flow=flow,
        stage=stage,
        status=status,
        context=context,
    )
