from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Request

from shared.state import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data" / "gateway"
METERING_EVENTS_FILE = DATA_DIR / "metering_events.jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _month_from_iso(timestamp: str) -> str:
    return timestamp[:7]


def _rollup_path(month: str) -> Path:
    return DATA_DIR / f"metering_rollup_{month}.json"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: Any) -> None:
    _ensure_parent(path)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


class GatewayMeteringStore:
    def __init__(self, events_file: Path = METERING_EVENTS_FILE, data_dir: Path = DATA_DIR):
        self.events_file = events_file
        self.data_dir = data_dir
        self._lock = asyncio.Lock()

    def _rollup_path(self, month: str) -> Path:
        return self.data_dir / f"metering_rollup_{month}.json"

    async def record(
        self,
        key_id: str,
        method: str,
        path: str,
        status_code: int,
        latency_ms: float,
        units: int = 1,
    ) -> None:
        timestamp = _utc_now_iso()
        event = {
            "timestamp": timestamp,
            "key_id": key_id,
            "method": method,
            "path": path,
            "status_code": status_code,
            "latency_ms": round(latency_ms, 3),
            "units": units,
        }

        month = _month_from_iso(timestamp)
        rollup_file = self._rollup_path(month)

        async with self._lock:
            _append_jsonl(self.events_file, event)

            rollup = _read_json(rollup_file, {"month": month, "by_key": {}})
            key_section = rollup.setdefault("by_key", {}).setdefault(
                key_id,
                {
                    "month": month,
                    "key_id": key_id,
                    "requests": 0,
                    "latency_ms_total": 0.0,
                    "latency_ms_avg": 0.0,
                    "status_counts": {},
                    "endpoints": {},
                    "units": 0,
                },
            )

            key_section["requests"] += 1
            key_section["latency_ms_total"] += float(latency_ms)
            key_section["latency_ms_avg"] = round(
                key_section["latency_ms_total"] / max(key_section["requests"], 1), 3
            )
            key_section["units"] += int(units)

            status_key = str(status_code)
            key_section.setdefault("status_counts", {})[status_key] = (
                key_section["status_counts"].get(status_key, 0) + 1
            )

            endpoint_key = f"{method.upper()} {path}"
            key_section.setdefault("endpoints", {})[endpoint_key] = (
                key_section["endpoints"].get(endpoint_key, 0) + 1
            )

            _write_json(rollup_file, rollup)

    async def get_usage_for_key(self, key_id: str, month: Optional[str] = None) -> Dict[str, Any]:
        target_month = month or datetime.now(timezone.utc).strftime("%Y-%m")
        rollup = _read_json(
            self._rollup_path(target_month), {"month": target_month, "by_key": {}}
        )
        key_data = rollup.get("by_key", {}).get(
            key_id,
            {
                "month": target_month,
                "key_id": key_id,
                "requests": 0,
                "latency_ms_total": 0.0,
                "latency_ms_avg": 0.0,
                "status_counts": {},
                "endpoints": {},
                "units": 0,
            },
        )
        return key_data

    async def get_usage_all(self, month: Optional[str] = None) -> Dict[str, Any]:
        target_month = month or datetime.now(timezone.utc).strftime("%Y-%m")
        rollup = _read_json(
            self._rollup_path(target_month), {"month": target_month, "by_key": {}}
        )
        return rollup


_metering_store: Optional[GatewayMeteringStore] = None


def get_metering_store() -> GatewayMeteringStore:
    global _metering_store
    if _metering_store is None:
        _metering_store = GatewayMeteringStore()
    return _metering_store


async def record_request(
    request: Request,
    key_id: str,
    status_code: int,
    started_at: float,
    units: int = 1,
) -> None:
    latency_ms = (time.perf_counter() - started_at) * 1000.0
    await get_metering_store().record(
        key_id=key_id,
        method=request.method,
        path=request.url.path,
        status_code=status_code,
        latency_ms=latency_ms,
        units=units,
    )
