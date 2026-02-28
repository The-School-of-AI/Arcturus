"""
search/deep_research.py
Iterative deep research orchestrator (up to 5 iterations).
Yields SSE-friendly DeepResearchEvent dicts for streaming to the frontend.
Also writes/updates a session JSON on disk so the canvas graph shows
PlannerAgent -> SearchAgent N -> SynthesizerAgent nodes in real time.
"""
import asyncio
import json
import sys
import os
import uuid
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import AsyncIterator, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.query_decomposer import decompose
from search.crawl_pipeline import CrawlPipeline, SourceDocument
from search.synthesizer import synthesize, identify_gaps, SynthesisResult
from search.focus_modes import get_focus_config
from search import graph_bridge


# ---------------------------------------------------------------------------
# Event type for SSE streaming
# ---------------------------------------------------------------------------

@dataclass
class DeepResearchEvent:
    type_: str   # "phase", "sources", "synthesis", "gap", "done", "error"
    data: dict

    def to_sse(self) -> str:
        """Format as an SSE `data:` line."""
        payload = {"type": self.type_, **self.data}
        return f"data: {json.dumps(payload, default=str)}\n\n"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class DeepResearchOrchestrator:
    """Iterative deep research pipeline.

    Each iteration:
        1. Decompose query into sub-queries  (query_decomposer)
        2. Crawl & extract sources in parallel (crawl_pipeline)
        3. Synthesize with citations            (synthesizer)
        4. Identify gaps                        (synthesizer.identify_gaps)
        5. If gaps remain and iterations left → loop with gap queries

    Yields DeepResearchEvent at each phase for real-time SSE streaming.
    Writes session graph via graph_bridge so the canvas stays in sync.
    """

    def __init__(self):
        self.pipeline = CrawlPipeline()
        self._stopped = False

    def stop(self):
        self._stopped = True

    async def run(
        self,
        query: str,
        run_id: str | None = None,
        focus_mode: str = "web",
        max_iterations: int = 3,
        memory_context: str = "",
    ) -> AsyncIterator[DeepResearchEvent]:
        """Execute the iterative deep research pipeline.

        Yields DeepResearchEvent dicts suitable for SSE streaming.
        """
        run_id = run_id or str(int(datetime.now().timestamp()))
        focus_cfg = get_focus_config(focus_mode)
        all_sources: list[dict] = []
        current_query = query
        final_result: SynthesisResult | None = None

        # Create session graph for canvas
        graph_bridge.create_deep_research_session(run_id, query)

        try:
            for iteration in range(1, max_iterations + 1):
                if self._stopped:
                    break

                # ── Phase 1: Query Decomposition ──
                yield DeepResearchEvent("phase", {
                    "phase": "decomposition",
                    "iteration": iteration,
                    "query": current_query,
                })

                sub_queries = await decompose(
                    current_query, focus_mode=focus_mode, n_queries=6
                )

                yield DeepResearchEvent("phase", {
                    "phase": "decomposition_done",
                    "iteration": iteration,
                    "sub_queries": sub_queries,
                })

                # Update canvas graph
                graph_bridge.add_search_nodes(run_id, sub_queries, iteration)

                if self._stopped:
                    break

                # ── Phase 2: Parallel Crawl & Extract ──
                yield DeepResearchEvent("phase", {
                    "phase": "crawling",
                    "iteration": iteration,
                    "sub_query_count": len(sub_queries),
                })

                docs = await self.pipeline.search_and_extract(
                    sub_queries, top_k=10
                )

                # Convert SourceDocuments to dicts for synthesizer
                good_docs = [asdict(d) for d in docs if d.error is None]
                all_sources.extend(good_docs)

                # Update canvas: mark search nodes completed
                for i in range(1, len(sub_queries) + 1):
                    node_id = f"I{iteration}_Search_{i}"
                    graph_bridge.update_search_node(
                        run_id, node_id, "completed",
                        {"source_count": len(good_docs)},
                    )

                yield DeepResearchEvent("sources", {
                    "iteration": iteration,
                    "new_sources": len(good_docs),
                    "total_sources": len(all_sources),
                    "sample_urls": [d["url"] for d in good_docs[:5]],
                })

                if self._stopped:
                    break

                # ── Phase 3: Synthesis ──
                yield DeepResearchEvent("phase", {
                    "phase": "synthesis",
                    "iteration": iteration,
                    "source_count": len(all_sources),
                })

                synth_node_id = graph_bridge.add_synthesis_node(run_id, iteration)

                final_result = await synthesize(
                    query=query,
                    sources=all_sources,
                    focus_mode=focus_mode,
                    iteration=iteration,
                )

                graph_bridge.mark_iteration_done(
                    run_id, iteration, final_result.answer_md[:500]
                )

                yield DeepResearchEvent("synthesis", {
                    "iteration": iteration,
                    "markdown": final_result.answer_md,
                    "citation_count": len(final_result.citations),
                    "executive_summary": final_result.executive_summary,
                    "contradictions": final_result.contradictions,
                })

                if self._stopped:
                    break

                # ── Phase 4: Gap Analysis ──
                if iteration < max_iterations:
                    yield DeepResearchEvent("phase", {
                        "phase": "gap_analysis",
                        "iteration": iteration,
                    })

                    gaps = await identify_gaps(query, final_result.answer_md)

                    if not gaps:
                        yield DeepResearchEvent("gap", {
                            "iteration": iteration,
                            "gaps": [],
                            "message": "No significant gaps found. Research complete.",
                        })
                        break

                    yield DeepResearchEvent("gap", {
                        "iteration": iteration,
                        "gaps": gaps,
                    })

                    # Next iteration searches for the gaps
                    current_query = "; ".join(gaps)

            # ── Done ──
            graph_bridge.mark_session_done(run_id)

            citations_list = []
            if final_result:
                citations_list = [asdict(c) for c in final_result.citations]

            yield DeepResearchEvent("done", {
                "run_id": run_id,
                "final_report": final_result.answer_md if final_result else "",
                "citations": citations_list,
                "total_sources": len(all_sources),
                "executive_summary": final_result.executive_summary if final_result else "",
            })

        except Exception as e:
            graph_bridge.mark_session_failed(run_id, str(e))
            yield DeepResearchEvent("error", {
                "run_id": run_id,
                "error": str(e),
            })
