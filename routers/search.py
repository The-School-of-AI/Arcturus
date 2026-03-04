"""
routers/search.py
API endpoints for Oracle search features.
"""
import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from sse_starlette.sse import EventSourceResponse
from dataclasses import asdict

from shared.state import active_loops
from search.focus_modes import list_focus_modes, get_focus_config
from search.query_decomposer import decompose
from search.crawl_pipeline import CrawlPipeline
from search.synthesizer import synthesize, SynthesisResult
from search.deep_research import DeepResearchOrchestrator

router = APIRouter(prefix="/search", tags=["Search"])

# Track active deep research orchestrators for stop support
_active_orchestrators: dict[str, DeepResearchOrchestrator] = {}


# === Pydantic Models ===

class QuickSearchRequest(BaseModel):
    query: str
    focus_mode: str = "web"
    max_sources: int = 10


class DeepSearchRequest(BaseModel):
    query: str
    focus_mode: str = "web"
    max_iterations: int = 3


class DecomposeRequest(BaseModel):
    query: str
    focus_mode: str = "web"
    n_queries: int = 6


# === Endpoints ===

@router.get("/focus-modes")
async def get_focus_modes():
    """List all available focus modes with labels and descriptions."""
    modes = list_focus_modes()
    return [
        {
            "name": m.name,
            "label": m.label,
            "description": m.description,
            "citation_format": m.citation_format,
        }
        for m in modes
    ]


@router.post("/decompose")
async def decompose_query(request: DecomposeRequest):
    """Preview query decomposition into sub-queries without executing search."""
    sub_queries = await decompose(
        request.query,
        focus_mode=request.focus_mode,
        n_queries=request.n_queries,
    )
    return {"query": request.query, "sub_queries": sub_queries}


@router.post("")
async def quick_search(request: QuickSearchRequest):
    """Quick search: decompose -> crawl -> synthesize in a single request.

    Returns markdown with inline citations. No iterative gap analysis.
    """
    # 1. Decompose
    sub_queries = await decompose(
        request.query, focus_mode=request.focus_mode, n_queries=4
    )

    # 2. Crawl
    pipeline = CrawlPipeline()
    docs = await pipeline.search_and_extract(
        sub_queries, top_k=request.max_sources
    )
    good_docs = [
        {"url": d.url, "title": d.title, "content": d.content}
        for d in docs if d.error is None
    ]

    if not good_docs:
        return {
            "status": "completed",
            "markdown": "No search results found for this query.",
            "citations": [],
            "source_count": 0,
        }

    # 3. Synthesize
    result = await synthesize(
        query=request.query,
        sources=good_docs,
        focus_mode=request.focus_mode,
        iteration=1,
    )

    return {
        "status": "completed",
        "markdown": result.answer_md,
        "citations": [asdict(c) for c in result.citations],
        "source_count": len(result.citations),
        "executive_summary": result.executive_summary,
        "contradictions": result.contradictions,
    }


@router.post("/deep")
async def deep_search(request: DeepSearchRequest, req: Request):
    """Deep research with SSE streaming.

    Returns an EventSource stream of DeepResearchEvent objects.
    The client receives real-time progress updates as each phase completes.
    """
    run_id = str(int(datetime.now().timestamp()))
    orchestrator = DeepResearchOrchestrator()
    _active_orchestrators[run_id] = orchestrator

    async def event_generator():
        try:
            async for event in orchestrator.run(
                query=request.query,
                run_id=run_id,
                focus_mode=request.focus_mode,
                max_iterations=request.max_iterations,
            ):
                if await req.is_disconnected():
                    orchestrator.stop()
                    break
                yield {
                    "event": "message",
                    "data": json.dumps(
                        {"type": event.type_, **event.data}, default=str
                    ),
                }
        except asyncio.CancelledError:
            orchestrator.stop()
        finally:
            _active_orchestrators.pop(run_id, None)

    return EventSourceResponse(event_generator())


@router.post("/{run_id}/stop")
async def stop_search(run_id: str):
    """Stop an in-progress deep research run."""
    orch = _active_orchestrators.get(run_id)
    if orch is None:
        raise HTTPException(status_code=404, detail="No active search with this run_id")
    orch.stop()
    return {"run_id": run_id, "status": "stopping"}
