"""Execution context: plan graph, session persistence, and step lifecycle."""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import networkx as nx

from shared.state import PROJECT_ROOT

SESSION_BASE = PROJECT_ROOT / "memory" / "session_summaries_index"


class ExecutionContextManager:
    """Holds the plan graph (NetworkX), session id, and persists to session_summaries_index."""

    def __init__(
        self,
        graph_data: dict,
        session_id: str | None = None,
        original_query: str | None = None,
        file_manifest: list | None = None,
    ):
        self.stop_requested = False
        self.multi_mcp = None
        self.memory_context = None

        # Build NetworkX graph from dict (nodes + edges)
        data = dict(graph_data)
        if "edges" not in data and "links" not in data:
            data.setdefault("edges", [])
        if "edges" in data:
            self.plan_graph = nx.node_link_graph(data, edges="edges")
        else:
            self.plan_graph = nx.node_link_graph(data, edges="links")

        # Graph-level attributes: from explicit args or from graph_data top-level keys
        g = self.plan_graph.graph
        g.setdefault("globals_schema", graph_data.get("globals_schema") or {})
        g["session_id"] = session_id if session_id is not None else graph_data.get("session_id", "")
        g["original_query"] = original_query if original_query is not None else graph_data.get("original_query", "")
        g["file_manifest"] = file_manifest if file_manifest is not None else graph_data.get("file_manifest", [])
        g.setdefault("created_at", graph_data.get("created_at") or datetime.utcnow().isoformat())
        g.setdefault("status", graph_data.get("status", "running"))

    @classmethod
    def load_session(cls, session_file: Path) -> "ExecutionContextManager":
        """Load context from a saved session JSON file."""
        path = Path(session_file)
        data = json.loads(path.read_text(encoding="utf-8"))
        if "edges" in data:
            G = nx.node_link_graph(data, edges="edges")
        elif "links" in data:
            G = nx.node_link_graph(data, edges="links")
        else:
            data.setdefault("edges", [])
            G = nx.node_link_graph(data, edges="edges")
        inst = cls.__new__(cls)
        inst.plan_graph = G
        inst.stop_requested = False
        inst.multi_mcp = None
        inst.memory_context = None
        return inst

    def _save_session(self) -> None:
        """Persist plan_graph to session_summaries_index/YYYY/MM/DD/session_{id}.json"""
        sid = self.plan_graph.graph.get("session_id")
        if not sid:
            return
        SESSION_BASE.mkdir(parents=True, exist_ok=True)
        now = datetime.utcnow()
        subdir = SESSION_BASE / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"
        subdir.mkdir(parents=True, exist_ok=True)
        path = subdir / f"session_{sid}.json"
        data = nx.node_link_data(self.plan_graph, edges="edges")
        path.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

    def stop(self) -> None:
        self.stop_requested = True

    def get_ready_steps(self) -> list[str]:
        """Return node ids that are ready (all predecessors completed)."""
        ready = []
        for node_id in self.plan_graph.nodes:
            if node_id == "ROOT":
                continue
            if self.plan_graph.nodes[node_id].get("status") != "pending":
                continue
            preds = list(self.plan_graph.predecessors(node_id))
            if all(
                self.plan_graph.nodes[p].get("status") in ("completed", "skipped")
                for p in preds
            ):
                ready.append(node_id)
        return ready

    def get_step_data(self, step_id: str) -> dict:
        """Return the node data for step_id."""
        return self.plan_graph.nodes[step_id]

    def get_inputs(self, reads: list[str]) -> dict[str, Any]:
        """Return globals_schema entries for the given read keys."""
        g = self.plan_graph.graph.get("globals_schema", {})
        return {k: g.get(k) for k in reads if k in g}

    def mark_failed(self, node_id: str, error: str | None = None) -> None:
        self.plan_graph.nodes[node_id]["status"] = "failed"
        if error is not None:
            self.plan_graph.nodes[node_id]["error"] = error
        self.plan_graph.graph["status"] = "failed"

    def mark_running(self, step_id: str) -> None:
        self.plan_graph.nodes[step_id]["status"] = "running"

    async def mark_done(self, step_id: str, output: dict | Any) -> None:
        """Mark step completed and write outputs to globals_schema."""
        self.plan_graph.nodes[step_id]["status"] = "completed"
        self.plan_graph.nodes[step_id]["output"] = output
        writes = self.plan_graph.nodes[step_id].get("writes", [])
        if writes and isinstance(output, dict):
            g = self.plan_graph.graph.setdefault("globals_schema", {})
            for key in writes:
                if key in output:
                    g[key] = output[key]

    def get_execution_summary(self) -> dict:
        """Return a summary with final_outputs and status."""
        completed = [
            n for n in self.plan_graph.nodes
            if self.plan_graph.nodes[n].get("status") == "completed"
        ]
        final_outputs = {}
        for n in completed:
            out = self.plan_graph.nodes[n].get("output")
            if out is not None:
                final_outputs[n] = out
        return {
            "status": self.plan_graph.graph.get("status", "unknown"),
            "session_id": self.plan_graph.graph.get("session_id"),
            "final_outputs": final_outputs,
        }
