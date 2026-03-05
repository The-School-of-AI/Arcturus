"""SourceAgent stub: curate and return top sources as citations."""
from __future__ import annotations

import hashlib
from typing import Dict, Any, List


async def generate_section(query: str, page_context: Dict[str, Any], resources: Dict[str, Any]) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = resources.get("oracle_results", [])
    # create a small sources list (top 3)
    sources = []
    for r in results[:3]:
        sources.append({"id": r.get("citation_id"), "title": r.get("title"), "url": r.get("url"), "snippet": r.get("snippet")})

    section_id = "sources_" + hashlib.sha1(query.encode("utf-8")).hexdigest()[:8]
    blocks = [{"kind": "markdown", "text": "Top sources:"}]
    # append a citation block that references all
    blocks.append({"kind": "citation", "ids": [s["id"] for s in sources]})

    section = {
        "id": section_id,
        "type": "source",
        "title": "Sources & Evidence",
        "blocks": blocks,
        "metadata": {},
    }
    # pass up citations via page_context if desired
    return section
