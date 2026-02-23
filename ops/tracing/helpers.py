"""
WATCHTOWER: Span enrichment helpers.
Functions to attach domain-specific data (plan_graph, etc.) to spans.
"""
import json
from typing import Tuple, Optional


def get_trace_id_for_run(session_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Look up trace_id and span_id for a run/session from MongoDB.
    Used when resuming a session that wasn't saved with trace context.
    Returns (trace_id_hex, span_id_hex) or (None, None) if not found.
    """
    if not session_id:
        return (None, None)
    try:
        from pymongo import MongoClient
        from config.settings_loader import load_settings
        watchtower = load_settings().get("watchtower", {})
        uri = watchtower.get("mongodb_uri", "mongodb://localhost:27017")
        client = MongoClient(uri)
        coll = client["watchtower"]["spans"]
        doc = coll.find_one(
            {"$or": [
                {"attributes.run_id": session_id},
                {"attributes.session_id": session_id},
            ]},
            sort=[("start_time", -1)],
            projection={"trace_id": 1, "span_id": 1},
        )
        if doc and doc.get("trace_id") and doc.get("span_id"):
            return (doc["trace_id"], doc["span_id"])
    except Exception:
        pass
    return (None, None)


def attach_plan_graph_to_span(span, plan_result: dict, max_json_chars: int = 8000) -> None:
    """
    Attach plan_graph from planner output to a span for trace visibility.
    Sets plan_graph_summary (human-readable) and plan_graph (JSON, truncated).
    """
    if not plan_result.get("success") or "plan_graph" not in plan_result.get("output", {}):
        return
    pg = plan_result["output"]["plan_graph"]
    nodes = pg.get("nodes", [])
    edges = pg.get("edges", [])
    summary = " | ".join(
        f"{n.get('id', '?')}({n.get('agent', '?')})" for n in nodes[:12]
    )
    if len(nodes) > 12:
        summary += f" ...+{len(nodes) - 12} more"
    span.set_attribute("plan_graph_summary", summary)
    pg_str = json.dumps({"nodes": nodes, "edges": edges}, default=str)
    if len(pg_str) > max_json_chars:
        pg_str = pg_str[:max_json_chars] + "...[truncated]"
    span.set_attribute("plan_graph", pg_str)
