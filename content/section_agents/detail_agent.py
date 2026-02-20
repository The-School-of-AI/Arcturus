"""DetailAgent stub: produces a deeper dive section using Oracle outputs."""
from __future__ import annotations

import hashlib
from typing import Dict, Any


async def generate_section(query: str, page_context: Dict[str, Any], resources: Dict[str, Any]) -> Dict[str, Any]:
    results = resources.get("oracle_results", [])
    # join a couple of snippets to make a detail paragraph
    texts = [r.get("extracted_text", "") for r in results[:2]]
    text = "\n\n".join(t for t in texts if t)
    title = "Detail"
    section_id = "detail_" + hashlib.sha1((query + title).encode("utf-8")).hexdigest()[:8]
    section = {
        "id": section_id,
        "type": "detail",
        "title": title,
        "blocks": [{"kind": "markdown", "text": text or "No detailed data available."}, {"kind": "citation", "ids": [r.get("citation_id") for r in results[:2]]}],
        "widgets": [],
        "metadata": {},
    }
    return section
