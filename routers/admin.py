"""
Watchtower Admin API - Trace queries and metrics.
No auth for Days 1-5; add in Days 11-15.
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from pymongo import MongoClient
from config.settings_loader import settings

router = APIRouter(prefix="/admin", tags=["Admin"])


def _get_spans_collection():
    """Get MongoDB spans collection from watchtower config."""
    watchtower = settings.get("watchtower", {})
    uri = watchtower.get("mongodb_uri", "mongodb://localhost:27017")
    client = MongoClient(uri)
    return client["watchtower"]["spans"]


@router.get("/traces")
async def get_traces(
    run_id: str | None = Query(None, description="Filter by run_id"),
    limit: int = Query(50, ge=1, le=200),
    since: str | None = Query(None, description="ISO timestamp for time-range start"),
):
    """Query traces from MongoDB. Returns distinct trace_ids with summary."""
    coll = _get_spans_collection()
    match = {}
    if run_id:
        match["attributes.run_id"] = run_id
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            match["start_time"] = {"$gte": since_dt}
        except ValueError:
            pass

    pipeline = [
        {"$match": match} if match else {"$match": {}},
        {"$sort": {"start_time": -1}},
        {"$limit": limit * 10},
        {
            "$group": {
                "_id": "$trace_id",
                "spans": {"$push": "$$ROOT"},
                "start_time": {"$min": "$start_time"},
                "duration_ms": {"$sum": "$duration_ms"},
                "status": {"$max": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}},
            }
        },
        {"$sort": {"start_time": -1}},
        {"$limit": limit},
        {
            "$project": {
                "trace_id": "$_id",
                "start_time": 1,
                "duration_ms": 1,
                "has_error": {"$eq": ["$status", 1]},
                "span_count": {"$size": "$spans"},
            }
        },
    ]
    cursor = coll.aggregate(pipeline)
    traces = list(cursor)
    for t in traces:
        if "start_time" in t:
            t["start_time"] = t["start_time"].isoformat()
    return {"traces": traces}


@router.get("/traces/{trace_id}")
async def get_trace_detail(trace_id: str):
    """Get all spans for a trace, build tree."""
    coll = _get_spans_collection()
    spans = list(coll.find({"trace_id": trace_id}).sort("start_time", 1))
    for s in spans:
        if "start_time" in s:
            s["start_time"] = s["start_time"].isoformat()
        if "end_time" in s:
            s["end_time"] = s["end_time"].isoformat()
        if "_id" in s:
            del s["_id"]
    return {"trace_id": trace_id, "spans": spans}


@router.get("/metrics/summary")
async def get_metrics_summary(
    hours: int = Query(24, ge=1, le=168),
):
    """Aggregate metrics from spans: total traces, avg duration, error rate."""
    coll = _get_spans_collection()
    since = datetime.utcnow() - timedelta(hours=hours)
    pipeline = [
        {"$match": {"start_time": {"$gte": since}}},
        {
            "$group": {
                "_id": "$trace_id",
                "duration_ms": {"$sum": "$duration_ms"},
                "has_error": {"$max": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}},
            }
        },
        {
            "$group": {
                "_id": None,
                "total_traces": {"$sum": 1},
                "avg_duration_ms": {"$avg": "$duration_ms"},
                "error_count": {"$sum": "$has_error"},
            }
        },
    ]
    cursor = coll.aggregate(pipeline)
    row = next(cursor, None)
    if not row:
        return {"total_traces": 0, "avg_duration_ms": 0, "error_count": 0, "hours": hours}
    return {
        "total_traces": row.get("total_traces", 0),
        "avg_duration_ms": round(row.get("avg_duration_ms", 0), 2),
        "error_count": row.get("error_count", 0),
        "hours": hours,
    }


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
