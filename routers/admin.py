"""
Watchtower Admin API - Trace queries and metrics.
No auth for Days 1-5; add in Days 11-15.
"""
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from pymongo import MongoClient

from config.settings_loader import settings
from ops.admin.spans_repository import SpansRepository

router = APIRouter(prefix="/admin", tags=["Admin"])


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
