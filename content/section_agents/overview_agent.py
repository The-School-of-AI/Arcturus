"""OverviewAgent stub: produces an executive summary section using Oracle outputs."""
from __future__ import annotations

import hashlib
from typing import Dict, Any


async def generate_section(query: str, page_context: Dict[str, Any], resources: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an overview section.

    For Phase 1 this is a deterministic stub that picks the top Oracle result
    and returns a short markdown block with a citation anchor.
    """
    results = resources.get("oracle_results", [])
    top = results[0] if results else None
    content = """
    ## Executive summary

    This page was synthesized for the query: **%s**.

    %s
    """ % (query, top["snippet"] if top else "No data available.")

    section_id = "overview_" + hashlib.sha1(query.encode("utf-8")).hexdigest()[:8]
    section = {
        "id": section_id,
        "type": "overview",
        "title": "Executive summary",
        "blocks": [{"kind": "markdown", "text": content.strip()}, {"kind": "citation", "ids": [top["citation_id"]] if top else []}],
        "widgets": [],
        "metadata": {},
    }
    return section
