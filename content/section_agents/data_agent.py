"""DataAgent stub: extract table/chart blocks from Oracle structured extracts."""
from __future__ import annotations

import hashlib
from typing import Dict, Any, List


async def generate_section(query: str, page_context: Dict[str, Any], resources: Dict[str, Any]) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = resources.get("oracle_results", [])
    # collect first table we find
    table = None
    for r in results:
        tables = r.get("structured_extracts", {}).get("tables", [])
        if tables:
            table = tables[0]
            break

    section_id = "data_" + hashlib.sha1(query.encode("utf-8")).hexdigest()[:8]
    blocks = []
    if table:
        blocks.append({"kind": "table", "columns": table.get("columns", []), "rows": table.get("rows", [])})
    else:
        blocks.append({"kind": "markdown", "text": "No structured data found."})

    section = {
        "id": section_id,
        "type": "data",
        "title": "Data & Figures",
        "blocks": blocks,
        "charts": [],
        "metadata": {},
    }
    return section
