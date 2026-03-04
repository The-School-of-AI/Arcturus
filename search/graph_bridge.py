"""
search/graph_bridge.py
======================
Writes and updates a networkx-compatible session JSON file for a deep-research
run so that the existing `GET /runs/{run_id}` polling endpoint can serve node
data to the canvas — giving users the same Planner -> Search -> Synthesizer graph
view they see for standard agent runs.

No new dependencies: uses networkx (already installed) and stdlib only.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import networkx as nx

_SESSIONS_BASE: Path | None = None


def _sessions_dir() -> Path:
    global _SESSIONS_BASE
    if _SESSIONS_BASE is None:
        _SESSIONS_BASE = Path(__file__).parent.parent / "memory" / "session_summaries_index"
    return _SESSIONS_BASE


def _session_path(run_id: str) -> Path:
    """Return the session JSON path for *run_id*, mirroring context.py _save_session."""
    today = datetime.now()
    date_dir = _sessions_dir() / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"
    date_dir.mkdir(parents=True, exist_ok=True)
    return date_dir / f"session_{run_id}.json"


def _node_defaults(node_id: str, **overrides) -> dict:
    """Sensible default attributes for a graph node."""
    d: dict[str, Any] = {
        "id": node_id,
        "agent": "",
        "agent_prompt": "",
        "status": "idle",
        "output": None,
        "reads": [],
        "writes": [],
    }
    d.update(overrides)
    return d


def _save(G: nx.DiGraph, run_id: str) -> Path:
    path = _session_path(run_id)
    data = nx.node_link_data(G)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    return path


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def create_deep_research_session(run_id: str, query: str) -> Path:
    """Create the initial session graph with ROOT + Query + PlannerAgent nodes.

    Returns the path to the session JSON file.
    """
    G = nx.DiGraph()
    G.graph["session_id"] = run_id
    G.graph["original_query"] = query
    G.graph["status"] = "running"
    G.graph["research_mode"] = "deep_research"
    G.graph["globals_schema"] = {}

    G.add_node("ROOT", **_node_defaults("ROOT", agent="System", status="completed"))
    G.add_node("Query", **_node_defaults("Query", agent="UserQuery", status="completed", output=query))
    G.add_edge("ROOT", "Query")

    return _save(G, run_id)


def add_search_nodes(run_id: str, sub_queries: list[str], iteration: int = 1) -> None:
    """Add RetrieverAgent nodes for each sub-query (one iteration)."""
    G = _load(run_id)
    if G is None:
        return

    prefix = f"I{iteration}"
    parent = "Query"

    for i, sq in enumerate(sub_queries, 1):
        node_id = f"{prefix}_Search_{i}"
        G.add_node(node_id, **_node_defaults(
            node_id,
            agent="RetrieverAgent",
            agent_prompt=sq,
            status="running",
        ))
        G.add_edge(parent, node_id)

    _save(G, run_id)


def update_search_node(run_id: str, node_id: str, status: str, output: dict | None = None) -> None:
    """Update a single search node's status and output."""
    G = _load(run_id)
    if G is None or node_id not in G.nodes:
        return

    G.nodes[node_id]["status"] = status
    if output is not None:
        G.nodes[node_id]["output"] = output

    _save(G, run_id)


def add_synthesis_node(run_id: str, iteration: int = 1) -> str:
    """Add a SummarizerAgent node connected to the search nodes of this iteration."""
    G = _load(run_id)
    if G is None:
        return ""

    prefix = f"I{iteration}"
    node_id = f"{prefix}_Synthesize"
    G.add_node(node_id, **_node_defaults(
        node_id,
        agent="SummarizerAgent",
        status="running",
    ))

    # Connect from all search nodes of this iteration
    for n in list(G.nodes):
        if n.startswith(f"{prefix}_Search_"):
            G.add_edge(n, node_id)

    _save(G, run_id)
    return node_id


def mark_iteration_done(run_id: str, iteration: int, synthesis_output: str = "") -> None:
    """Mark the synthesis node of an iteration as completed."""
    G = _load(run_id)
    if G is None:
        return

    node_id = f"I{iteration}_Synthesize"
    if node_id in G.nodes:
        G.nodes[node_id]["status"] = "completed"
        G.nodes[node_id]["output"] = synthesis_output

    _save(G, run_id)


def add_thinker_node(
    run_id: str,
    contradictions: list[str],
    resolution_queries: list[str],
) -> str:
    """Add a ThinkerAgent node for contradiction analysis."""
    G = _load(run_id)
    if G is None:
        return ""

    node_id = "ThinkerAgent"
    G.add_node(node_id, **_node_defaults(
        node_id,
        agent="ThinkerAgent",
        agent_prompt=f"Analyzing {len(contradictions)} contradictions",
        status="completed",
        output={
            "contradictions": contradictions,
            "resolution_queries": resolution_queries,
        },
    ))

    # Connect from the last synthesis node
    synth_nodes = [n for n in G.nodes if n.endswith("_Synthesize")]
    if synth_nodes:
        last_synth = sorted(synth_nodes)[-1]
        G.add_edge(last_synth, node_id)

    _save(G, run_id)
    return node_id


def add_final_synthesis_node(run_id: str) -> str:
    """Add a FinalSynthesizerAgent node connected to thinker and resolution nodes."""
    G = _load(run_id)
    if G is None:
        return ""

    node_id = "FinalSynthesizer"
    G.add_node(node_id, **_node_defaults(
        node_id,
        agent="FinalSynthesizerAgent",
        status="running",
    ))

    # Connect from ThinkerAgent if it exists
    if "ThinkerAgent" in G.nodes:
        G.add_edge("ThinkerAgent", node_id)
    else:
        # Connect from last synthesis node if no thinker
        synth_nodes = [n for n in G.nodes if n.endswith("_Synthesize")]
        if synth_nodes:
            G.add_edge(sorted(synth_nodes)[-1], node_id)

    _save(G, run_id)
    return node_id


def mark_final_synthesis_done(run_id: str, output: str = "") -> None:
    """Mark the FinalSynthesizer node as completed."""
    G = _load(run_id)
    if G is None:
        return

    if "FinalSynthesizer" in G.nodes:
        G.nodes["FinalSynthesizer"]["status"] = "completed"
        G.nodes["FinalSynthesizer"]["output"] = output

    _save(G, run_id)


def mark_session_done(run_id: str) -> None:
    """Mark the entire session as completed."""
    G = _load(run_id)
    if G is None:
        return

    G.graph["status"] = "completed"
    _save(G, run_id)


def mark_session_failed(run_id: str, error: str = "") -> None:
    """Mark the session as failed."""
    G = _load(run_id)
    if G is None:
        return

    G.graph["status"] = "failed"
    G.graph["error"] = error
    _save(G, run_id)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _load(run_id: str) -> nx.DiGraph | None:
    """Load the session graph from disk."""
    path = _session_path(run_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "edges" in data:
            return nx.node_link_graph(data, edges="edges")
        elif "links" in data:
            return nx.node_link_graph(data, edges="links")
        elif "link" in data:
            return nx.node_link_graph(data, edges="link")
        else:
            data["edges"] = []
            return nx.node_link_graph(data, edges="edges")
    except Exception:
        return None
