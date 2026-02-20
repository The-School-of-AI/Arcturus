"""Multi-agent page orchestrator (Phase 1).

This is a minimal orchestrator that:
- calls `content.oracle_client.search_oracle` (mock)
- calls section agents in parallel
- composes a page JSON and persists it to `data/pages/` as JSON
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List

from content import oracle_client
from content.section_agents import overview_generate_section, detail_generate_section, data_generate_section, source_generate_section

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "pages"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _build_citations_map(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    citations = {}
    for r in results:
        cid = r.get("citation_id")
        citations[cid] = {
            "url": r.get("url"),
            "title": r.get("title"),
            "snippet": r.get("snippet"),
            "credibility": r.get("credibility_score"),
        }
    return citations


async def generate_page(query: str, template: str = "topic_overview", created_by: str = "dev") -> Dict[str, Any]:
    if not query or not query.strip():
        raise ValueError("query is required")

    start = time.time()
    # call oracle (mock)
    oracle_resp = oracle_client.search_oracle(query, k=5)
    results = oracle_resp.get("results", [])

    # prepare resources passed to agents
    resources = {"oracle_results": results}

    # run agents in parallel
    coros = [overview_generate_section(query, {}, resources), detail_generate_section(query, {}, resources), data_generate_section(query, {}, resources), source_generate_section(query, {}, resources)]
    sections = await asyncio.gather(*coros)

    # compose page
    page_id = f"page_{uuid.uuid4().hex[:8]}"
    page = {
        "id": page_id,
        "title": f"Spark: {query}",
        "query": query,
        "template": template,
        "sections": sections,
        "citations": _build_citations_map(results),
        "metadata": {"created_by": created_by, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "versions": []},
    }

    # persist
    path = DATA_DIR / f"{page_id}.json"
    path.write_text(json.dumps(page, indent=2), encoding="utf-8")

    return page


def load_page(page_id: str) -> Dict[str, Any]:
    path = DATA_DIR / f"{page_id}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))
