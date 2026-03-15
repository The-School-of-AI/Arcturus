"""
Watchtower Admin API — Trace queries, metrics, and P14.4/P14.5 Admin Controls.

P14.1-14.3 (traces, cost, errors, health) endpoints are at the top.
P14.4 (feature flags, cache, config, diagnostics, sessions, throttle) in the middle.
P14.5 (audit log, GDPR data export/delete, admin auth) at the bottom.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from pymongo import MongoClient

from config.settings_loader import settings, load_settings, reload_settings, save_settings
from ops.admin.spans_repository import SpansRepository

# ---------------------------------------------------------------------------
# Admin API-key auth guard (P14.5)
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def _verify_admin_key(api_key: str | None = Security(_api_key_header)):
    """
    Lightweight auth guard for admin endpoints.

    - If ``watchtower.admin_api_key`` is set in settings: require matching header.
    - If not set: allow all requests (dev mode).
    """
    configured_key = settings.get("watchtower", {}).get("admin_api_key")
    if not configured_key:
        return  # Dev mode — no auth required
    if not api_key or api_key != configured_key:
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")


router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(_verify_admin_key)])


def _get_spans_collection():
    """Get MongoDB spans collection from watchtower config."""
    watchtower = settings.get("watchtower", {})
    uri = watchtower.get("mongodb_uri", "mongodb://localhost:27017")
    client = MongoClient(uri)
    return client["watchtower"]["spans"]


def _repo() -> SpansRepository:
    """Repository instance using current spans collection."""
    return SpansRepository(_get_spans_collection())


@router.get("/traces")
async def get_traces(
    run_id: str | None = Query(None, description="Filter by run_id"),
    limit: int = Query(50, ge=1, le=200),
    since: str | None = Query(None, description="ISO timestamp for time-range start; use for incremental fetch"),
):
    """Query traces from MongoDB. Returns distinct trace_ids with summary."""
    traces = _repo().get_traces(run_id=run_id, limit=limit, since=since)
    return {"traces": traces}


@router.get("/traces/view", response_class=HTMLResponse)
async def traces_view():
    """Simple HTML page to view traces (fallback when Jaeger not running)."""
    html = """
<!DOCTYPE html>
<html>
<head><title>Watchtower Traces</title>
<style>
body{font-family:system-ui;margin:2rem;background:#1a1a2e;color:#eee;}
a{color:#6ee7b7;}
table{border-collapse:collapse;width:100%;}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #333;}
th{background:#16213e;}
tr:hover{background:#0f3460;}
</style>
</head>
<body>
<h1>Watchtower Traces</h1>
<p>View traces at <a href="http://localhost:16686">Jaeger UI</a> for full visualization.</p>
<p>Or use <a href="/api/admin/traces">/api/admin/traces</a> for JSON.</p>
</body>
</html>
"""
    return HTMLResponse(html)


@router.get("/traces/{trace_id}")
async def get_trace_detail(trace_id: str):
    """Get all spans for a trace, build tree."""
    spans = _repo().get_trace_detail(trace_id)
    return {"trace_id": trace_id, "spans": spans}


@router.get("/metrics/summary")
async def get_metrics_summary(
    hours: int = Query(24, ge=1, le=168),
):
    """Aggregate metrics from spans: total traces, avg duration, error rate."""
    return _repo().get_metrics_summary(hours)


@router.get("/cost/summary")
async def get_cost_summary(
    hours: int = Query(24, ge=1, le=168),
    group_by: str = Query("agent", description="Group by: agent | model | trace"),
):
    """Aggregate cost from llm.generate spans. Requires attributes.cost_usd."""
    return _repo().get_cost_summary(hours, group_by)


@router.get("/errors/summary")
async def get_errors_summary(
    hours: int = Query(24, ge=1, le=168),
):
    """Aggregate spans with status=error. Group by agent or span name."""
    return _repo().get_errors_summary(hours)


@router.get("/health")
async def get_health():
    """Current health status of MongoDB, Qdrant, Ollama, MCP gateway."""
    from ops.health import run_all_health_checks

    results = run_all_health_checks()
    return {"services": [r.to_dict() for r in results]}


def _get_health_repo():
    """Get HealthRepository for health_checks collection."""
    from ops.health.repository import HealthRepository

    watchtower = settings.get("watchtower", {})
    uri = watchtower.get("mongodb_uri", "mongodb://localhost:27017")
    client = MongoClient(uri)
    return HealthRepository(client["watchtower"]["health_checks"])


@router.get("/health/history")
async def get_health_history(
    hours: int = Query(24, ge=1, le=168),
    service: str | None = Query(None, description="Filter by service name"),
    limit: int = Query(500, ge=1, le=2000),
):
    """Historical health snapshots within a time window."""
    repo = _get_health_repo()
    snapshots = repo.get_history(hours=hours, service=service, limit=limit)
    return {"snapshots": snapshots, "hours": hours, "count": len(snapshots)}


@router.get("/health/uptime")
async def get_health_uptime(
    hours: int = Query(24, ge=1, le=720),
):
    """Per-service uptime percentages over a time window."""
    repo = _get_health_repo()
    uptimes = repo.compute_all_uptimes(hours=hours)
    return {"uptimes": uptimes, "hours": hours}


@router.get("/health/resources")
async def get_health_resources():
    """Latest system resource snapshot (CPU, memory, disk)."""
    from ops.health import collect_resources

    snapshot = collect_resources()
    return {"resources": snapshot.to_dict()}


# ===================================================================
# P14.4 — Admin Controls
# ===================================================================


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------


@router.get("/flags")
async def list_flags():
    """List all feature flags with their state and lifecycle type."""
    from ops.admin.feature_flags import flag_store

    return {"flags": flag_store.list_all()}


class FlagToggleRequest(BaseModel):
    enabled: bool


@router.put("/flags/{name}")
async def toggle_flag(name: str, body: FlagToggleRequest, request: Request):
    """
    Toggle a feature flag.

    Lifecycle-managed flags (voice_wake, health_scheduler) will also
    stop/start the corresponding background service.
    """
    from ops.admin.feature_flags import flag_store, LIFECYCLE_FLAGS

    old_value = flag_store.get(name)
    result = flag_store.set(name, body.enabled)

    # Audit log
    from ops.audit import audit_logger
    audit_logger.log_action("admin", "feature_toggle", f"flag:{name}", old_value, body.enabled)

    # Lifecycle hooks: actually stop/start background services
    if name in LIFECYCLE_FLAGS:
        try:
            if name == "voice_wake" and hasattr(request.app.state, "orchestrator"):
                orch = request.app.state.orchestrator
                if body.enabled:
                    if orch.wake and not getattr(orch.wake, "_running", False):
                        orch.wake.start()
                        result["lifecycle_action"] = "started"
                else:
                    if orch.wake:
                        orch.wake.stop()
                        result["lifecycle_action"] = "stopped"

            elif name == "health_scheduler" and hasattr(request.app.state, "health_scheduler"):
                scheduler = request.app.state.health_scheduler
                if body.enabled:
                    import asyncio
                    asyncio.create_task(scheduler.start())
                    result["lifecycle_action"] = "started"
                else:
                    import asyncio
                    asyncio.create_task(scheduler.stop())
                    result["lifecycle_action"] = "stopped"

        except Exception as e:
            result["lifecycle_error"] = str(e)

    return result


@router.delete("/flags/{name}")
async def delete_flag(name: str):
    """Delete a feature flag."""
    from ops.admin.feature_flags import flag_store

    existed = flag_store.delete(name)
    if not existed:
        raise HTTPException(status_code=404, detail=f"Flag '{name}' not found")

    # Audit log
    from ops.audit import audit_logger
    audit_logger.log_action("admin", "feature_delete", f"flag:{name}", True, None)

    return {"deleted": name}


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------


@router.get("/cache")
async def list_caches():
    """Enumerate known caches with basic stats."""
    import os
    from pathlib import Path

    caches = []

    # 1. Settings cache
    caches.append({
        "name": "settings",
        "description": "In-memory settings cache (config/settings.json)",
        "flushable": True,
    })

    # 2. FAISS index
    faiss_dir = Path("data/faiss_index")
    faiss_size = 0
    faiss_files = 0
    if faiss_dir.exists():
        for f in faiss_dir.rglob("*"):
            if f.is_file():
                faiss_files += 1
                faiss_size += f.stat().st_size
    caches.append({
        "name": "faiss",
        "description": "FAISS vector index (data/faiss_index/)",
        "files": faiss_files,
        "size_mb": round(faiss_size / (1024 * 1024), 2),
        "flushable": False,  # Destructive — not safe to flush without re-index
    })

    # 3. MCP sessions
    try:
        from shared.state import get_multi_mcp
        mcp = get_multi_mcp()
        session_count = len(getattr(mcp, "sessions", {}))
        caches.append({
            "name": "mcp_sessions",
            "description": "Active MCP server sessions",
            "sessions": session_count,
            "flushable": False,
        })
    except Exception:
        pass

    return {"caches": caches}


@router.post("/cache/{name}/flush")
async def flush_cache(name: str):
    """Flush a specific cache by name."""
    if name == "settings":
        reload_settings()

        # Audit log
        from ops.audit import audit_logger
        audit_logger.log_action("admin", "cache_flush", f"cache:{name}", None, "flushed")

        return {"flushed": "settings", "message": "Settings cache reloaded from disk"}

    raise HTTPException(
        status_code=400,
        detail=f"Cache '{name}' is not flushable or does not exist. Only 'settings' is safely flushable.",
    )


# ---------------------------------------------------------------------------
# Config Management (delegates to existing settings_loader)
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_config():
    """Return current live config (settings.json)."""
    current = reload_settings()
    return {"config": current}


@router.get("/config/diff")
async def get_config_diff():
    """Show differences between current settings and defaults."""
    import json
    from pathlib import Path

    defaults_path = Path("config/settings.defaults.json")
    if not defaults_path.exists():
        raise HTTPException(status_code=404, detail="settings.defaults.json not found")

    defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
    current = reload_settings()

    def _diff(d1: dict, d2: dict, prefix: str = "") -> list:
        changes = []
        all_keys = set(list(d1.keys()) + list(d2.keys()))
        for key in sorted(all_keys):
            path = f"{prefix}.{key}" if prefix else key
            v1 = d1.get(key)
            v2 = d2.get(key)
            if isinstance(v1, dict) and isinstance(v2, dict):
                changes.extend(_diff(v1, v2, path))
            elif v1 != v2:
                changes.append({
                    "path": path,
                    "default": v1,
                    "current": v2,
                })
        return changes

    differences = _diff(defaults, current)
    return {
        "total_changes": len(differences),
        "differences": differences,
    }


# ---------------------------------------------------------------------------
# Diagnostics (arcturus doctor)
# ---------------------------------------------------------------------------


@router.get("/diagnostics")
async def run_diagnostics_endpoint():
    """Run automated health check and system diagnostics."""
    from ops.admin.diagnostics import run_diagnostics

    return run_diagnostics()


# ---------------------------------------------------------------------------
# Sessions (simplified user management for single-user system)
# ---------------------------------------------------------------------------


@router.get("/sessions")
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    hours: int = Query(24, ge=1, le=720),
):
    """List recent sessions derived from trace data (spans grouped by session_id)."""
    from datetime import datetime, timedelta

    coll = _get_spans_collection()
    since = datetime.utcnow() - timedelta(hours=hours)

    pipeline = [
        {
            "$match": {
                "start_time": {"$gte": since},
                "attributes.session_id": {"$exists": True, "$ne": ""},
            }
        },
        {
            "$group": {
                "_id": "$attributes.session_id",
                "start_time": {"$min": "$start_time"},
                "end_time": {"$max": "$end_time"},
                "span_count": {"$sum": 1},
                "total_cost_usd": {
                    "$sum": {"$toDouble": {"$ifNull": ["$attributes.cost_usd", "0"]}}
                },
                "agents": {"$addToSet": "$attributes.agent"},
            }
        },
        {"$sort": {"start_time": -1}},
        {"$limit": limit},
    ]

    rows = list(coll.aggregate(pipeline))
    sessions = []
    for r in rows:
        sessions.append({
            "session_id": r["_id"],
            "start_time": r["start_time"].isoformat() if hasattr(r["start_time"], "isoformat") else str(r["start_time"]),
            "end_time": r["end_time"].isoformat() if hasattr(r["end_time"], "isoformat") else str(r["end_time"]),
            "span_count": r["span_count"],
            "total_cost_usd": round(float(r.get("total_cost_usd", 0)), 6),
            "agents": [a for a in r.get("agents", []) if a],
        })
    return {"sessions": sessions, "hours": hours, "count": len(sessions)}


# ---------------------------------------------------------------------------
# Throttle (global cost budget)
# ---------------------------------------------------------------------------


@router.get("/throttle")
async def get_throttle():
    """Get current cost usage vs hourly/daily budgets."""
    from ops.admin.throttle import ThrottlePolicy

    try:
        coll = _get_spans_collection()
    except Exception:
        coll = None
    policy = ThrottlePolicy(spans_collection=coll)
    return policy.get_usage_summary()


class ThrottleUpdateRequest(BaseModel):
    daily_budget_usd: float | None = None
    hourly_budget_usd: float | None = None


@router.put("/throttle")
async def update_throttle(body: ThrottleUpdateRequest):
    """Update global cost budget limits."""
    current = reload_settings()
    wt = current.setdefault("watchtower", {})
    throttle = wt.setdefault("throttle", {})
    old_throttle = throttle.copy()

    if body.daily_budget_usd is not None:
        throttle["daily_budget_usd"] = body.daily_budget_usd
    if body.hourly_budget_usd is not None:
        throttle["hourly_budget_usd"] = body.hourly_budget_usd

    save_settings()

    # Audit log
    from ops.audit import audit_logger
    audit_logger.log_action("admin", "throttle_update", "throttle", old_throttle, throttle.copy())

    return {"message": "Throttle updated", "throttle": throttle}


# ===================================================================
# P14.5 — Audit & Compliance
# ===================================================================


# ---------------------------------------------------------------------------
# Audit Log Query
# ---------------------------------------------------------------------------


@router.get("/audit")
async def query_audit_log(
    hours: int = Query(24, ge=1, le=720),
    action: str | None = Query(None, description="Filter by action type"),
    resource: str | None = Query(None, description="Filter by resource (substring match)"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Query the audit log. Returns recent admin actions."""
    from ops.audit import audit_logger

    entries = audit_logger.query(hours=hours, action=action, resource=resource, limit=limit)
    return {"entries": entries, "count": len(entries), "hours": hours}


# ---------------------------------------------------------------------------
# GDPR Data Export & Deletion
# ---------------------------------------------------------------------------


def _get_data_manager():
    """Create a SessionDataManager with current MongoDB collections."""
    from ops.audit.data_manager import SessionDataManager

    try:
        spans_coll = _get_spans_collection()
    except Exception:
        spans_coll = None

    try:
        watchtower = settings.get("watchtower", {})
        uri = watchtower.get("mongodb_uri", "mongodb://localhost:27017")
        client = MongoClient(uri)
        audit_coll = client["watchtower"]["audit_log"]
    except Exception:
        audit_coll = None

    return SessionDataManager(spans_collection=spans_coll, audit_collection=audit_coll)


@router.get("/data/{session_id}")
async def export_session_data(session_id: str):
    """GDPR data export: collect all data for a session across all stores."""
    manager = _get_data_manager()
    result = manager.export(session_id)

    from ops.audit import audit_logger
    audit_logger.log_action("admin", "data_export", f"session:{session_id}", None, "exported")

    return result


@router.delete("/data/{session_id}")
async def delete_session_data(session_id: str):
    """GDPR data erasure: purge all data for a session across all stores."""
    manager = _get_data_manager()
    result = manager.delete(session_id)

    from ops.audit import audit_logger
    audit_logger.log_action("admin", "data_delete", f"session:{session_id}", None, result["stores"])

    return result

