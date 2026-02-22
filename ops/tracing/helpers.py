"""
WATCHTOWER: Span enrichment helpers.
Functions to attach domain-specific data (plan_graph, etc.) to spans.
"""
import json


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
