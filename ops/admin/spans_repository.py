"""
Spans repository: MongoDB queries for traces, metrics, cost, and errors.

Query patterns:
- Use `since` param for incremental fetch: frontend can poll with since=last_trace_start_time
  to get only new traces instead of full list.
- Indexes on trace_id, start_time, attributes.run_id (see ops.tracing.core) ensure fast queries.
- For real-time updates, MongoDB Change Streams require a replica set (not standalone).
"""
from datetime import datetime, timedelta
from typing import Any

# Type for MongoDB collection (avoids pymongo import in type hints)
Collection = Any


def _since_datetime(hours: int) -> datetime:
    """Time cutoff for time-range queries."""
    return datetime.utcnow() - timedelta(hours=hours)


def _parse_since(since: str | None) -> datetime | None:
    """Parse ISO timestamp for time-range start. Returns None if invalid."""
    if not since:
        return None
    try:
        return datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError:
        return None


def _traces_match_stage(run_id: str | None, since: str | None) -> dict:
    """Build $match stage for traces query."""
    match: dict[str, Any] = {}
    if run_id:
        match["attributes.run_id"] = run_id
    since_dt = _parse_since(since)
    if since_dt is not None:
        match["start_time"] = {"$gte": since_dt}
    return {"$match": match} if match else {"$match": {}}


def _traces_group_stage() -> dict:
    """Group spans by trace_id, compute duration and error flag."""
    return {
        "$group": {
            "_id": "$trace_id",
            "spans": {"$push": "$$ROOT"},
            "start_time": {"$min": "$start_time"},
            "duration_ms": {"$sum": "$duration_ms"},
            "status": {"$max": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}},
        }
    }


def _traces_add_fields_stage() -> dict:
    """Aggregate session_id, cost, tokens from spans. First non-empty session_id wins."""
    return {
        "$addFields": {
            "session_id": {
                "$arrayElemAt": [
                    {
                        "$map": {
                            "input": {
                                "$filter": {
                                    "input": "$spans",
                                    "as": "s",
                                    "cond": {"$ne": [{"$ifNull": ["$$s.attributes.session_id", ""]}, ""]},
                                }
                            },
                            "as": "s",
                            "in": "$$s.attributes.session_id",
                        }
                    },
                    0,
                ]
            },
            "cost_usd": {
                "$reduce": {
                    "input": "$spans",
                    "initialValue": 0,
                    "in": {"$add": ["$$value", {"$toDouble": {"$ifNull": ["$$this.attributes.cost_usd", "0"]}}]},
                }
            },
            "input_tokens": {
                "$reduce": {
                    "input": "$spans",
                    "initialValue": 0,
                    "in": {"$add": ["$$value", {"$toInt": {"$ifNull": ["$$this.attributes.input_tokens", "0"]}}]},
                }
            },
            "output_tokens": {
                "$reduce": {
                    "input": "$spans",
                    "initialValue": 0,
                    "in": {"$add": ["$$value", {"$toInt": {"$ifNull": ["$$this.attributes.output_tokens", "0"]}}]},
                }
            },
        }
    }


def _traces_project_stage() -> dict:
    """Shape final trace document for API response."""
    return {
        "$project": {
            "trace_id": "$_id",
            "start_time": 1,
            "duration_ms": 1,
            "has_error": {"$eq": ["$status", 1]},
            "span_count": {"$size": "$spans"},
            "session_id": 1,
            "cost_usd": 1,
            "input_tokens": 1,
            "output_tokens": 1,
        }
    }


def _serialize_trace(t: dict) -> dict:
    """Convert MongoDB trace doc to API format (ISO timestamps, rounded cost)."""
    if "start_time" in t:
        t["start_time"] = t["start_time"].isoformat()
    if "cost_usd" in t:
        t["cost_usd"] = round(float(t.get("cost_usd", 0)), 6)
    return t


def _serialize_span(s: dict) -> dict:
    """Convert MongoDB span doc to API format (ISO timestamps, no _id)."""
    if "start_time" in s:
        s["start_time"] = s["start_time"].isoformat()
    if "end_time" in s:
        s["end_time"] = s["end_time"].isoformat()
    s.pop("_id", None)
    return s


def _sum_by_key(items: list[dict], key: str) -> dict[str, float]:
    """Sum cost by key (agent or model). Returns {key: rounded_cost}."""
    out: dict[str, float] = {}
    for x in items:
        k = x.get(key) or "unknown"
        c = float(x.get("cost", 0))
        out[k] = out.get(k, 0) + c
    return {k: round(v, 6) for k, v in out.items()}


class SpansRepository:
    """MongoDB access for watchtower spans. All methods expect a collection instance."""

    def __init__(self, collection: Collection):
        self._coll = collection

    def get_traces(
        self,
        run_id: str | None = None,
        limit: int = 50,
        since: str | None = None,
    ) -> list[dict]:
        """Return distinct traces with summary. Use since for incremental fetch."""
        pipeline = [
            _traces_match_stage(run_id, since),
            {"$sort": {"start_time": -1}},
            {"$limit": limit * 10},
            _traces_group_stage(),
            {"$sort": {"start_time": -1}},
            {"$limit": limit},
            _traces_add_fields_stage(),
            _traces_project_stage(),
        ]
        cursor = self._coll.aggregate(pipeline)
        return [_serialize_trace(t) for t in cursor]

    def get_trace_detail(self, trace_id: str) -> list[dict]:
        """Return all spans for a trace, sorted by start_time."""
        spans = list(self._coll.find({"trace_id": trace_id}).sort("start_time", 1))
        return [_serialize_span(dict(s)) for s in spans]

    def get_metrics_summary(self, hours: int) -> dict:
        """Aggregate total traces, avg duration, error count."""
        since = _since_datetime(hours)
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
        row = next(self._coll.aggregate(pipeline), None)
        if not row:
            return {"total_traces": 0, "avg_duration_ms": 0, "error_count": 0, "hours": hours}
        return {
            "total_traces": row.get("total_traces", 0),
            "avg_duration_ms": round(row.get("avg_duration_ms", 0), 2),
            "error_count": row.get("error_count", 0),
            "hours": hours,
        }

    def get_cost_summary(self, hours: int, group_by: str = "agent") -> dict:
        """Aggregate cost from llm.generate spans. group_by: agent | model | trace."""
        since = _since_datetime(hours)
        match = {
            "start_time": {"$gte": since},
            "name": "llm.generate",
            "attributes.cost_usd": {"$exists": True},
        }
        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": None,
                    "total_cost_usd": {"$sum": {"$toDouble": "$attributes.cost_usd"}},
                    "trace_ids": {"$addToSet": "$trace_id"},
                    "by_agent": {"$push": {"agent": "$attributes.agent", "cost": "$attributes.cost_usd"}},
                    "by_model": {"$push": {"model": "$attributes.model", "cost": "$attributes.cost_usd"}},
                }
            },
        ]
        row = next(self._coll.aggregate(pipeline), None)
        if not row:
            return {"total_cost_usd": 0.0, "trace_count": 0, "by_agent": {}, "by_model": {}, "hours": hours}

        total = float(row.get("total_cost_usd", 0))
        trace_ids = list(row.get("trace_ids", []))
        by_agent = _sum_by_key(row.get("by_agent", []), "agent")
        by_model = _sum_by_key(row.get("by_model", []), "model")

        result = {
            "total_cost_usd": round(total, 6),
            "trace_count": len(trace_ids),
            "by_agent": by_agent,
            "by_model": by_model,
            "hours": hours,
        }
        if group_by == "trace":
            trace_pipeline = [
                {"$match": match},
                {"$group": {"_id": "$trace_id", "cost": {"$sum": {"$toDouble": "$attributes.cost_usd"}}}},
                {"$sort": {"cost": -1}},
                {"$limit": 100},
            ]
            trace_cursor = self._coll.aggregate(trace_pipeline)
            result["by_trace"] = [
                {"trace_id": r["_id"], "cost_usd": round(float(r["cost"]), 6)} for r in trace_cursor
            ]
        return result

    def get_errors_summary(self, hours: int) -> dict:
        """Aggregate spans with status=error, grouped by agent or span name."""
        since = _since_datetime(hours)
        match = {"start_time": {"$gte": since}, "status": "error"}
        pipeline = [
            {"$match": match},
            {
                "$group": {
                    "_id": {"$ifNull": ["$attributes.agent", "$name"]},
                    "count": {"$sum": 1},
                    "trace_ids": {"$addToSet": "$trace_id"},
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 50},
        ]
        rows = list(self._coll.aggregate(pipeline))
        error_count = sum(r["count"] for r in rows)
        by_agent = {r["_id"]: {"count": r["count"], "sample_trace_ids": list(r["trace_ids"])[:5]} for r in rows}
        return {"error_count": error_count, "by_agent": by_agent, "hours": hours}
