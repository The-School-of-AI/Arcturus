"""Simple Oracle client mock used by P03 during Phase 1.

This module provides a deterministic search_oracle() function that returns a
normalized response shape. In production Spark would call Project P02 (Oracle)
HTTPRequest endpoints; for Phase 1 we keep a local deterministic mock so tests
are deterministic and fast.
"""
from __future__ import annotations

import time
import uuid
from typing import Dict, List


def _make_result(idx: int) -> Dict:
    cid = f"T{idx:03d}"
    return {
        "citation_id": cid,
        "url": f"https://example.org/source/{cid}",
        "title": f"Example Source {idx}",
        "extracted_text": f"This is an extracted snippet from source {idx} describing various facts.",
        "snippet": f"Snippet for source {idx}",
        "published_at": "2025-12-01T00:00:00Z",
        "source_type": "article",
        "credibility_score": round(0.8 - idx * 0.05, 2),
        "structured_extracts": {
            "tables": [
                {
                    "id": f"tbl{idx}",
                    "columns": ["metric", "value"],
                    "rows": [["CAGR", f"{20.9 - idx:.1f}%"]],
                }
            ]
        },
    }


def search_oracle(query: str, k: int = 5, timeout: float = 5.0) -> Dict:
    """Return a deterministic mock response for `query`.

    Args:
        query: user query
        k: max results
        timeout: unused for mock

    Returns:
        dict with keys: query_id, results (list), metrics
    """
    if not query or not query.strip():
        return {"query_id": str(uuid.uuid4()), "results": [], "metrics": {"elapsed_ms": 0, "num_sources": 0}}

    start = time.time()
    # produce k deterministic results
    results: List[Dict] = [_make_result(i + 1) for i in range(min(k, 5))]
    elapsed = int((time.time() - start) * 1000)
    return {"query_id": str(uuid.uuid4()), "results": results, "metrics": {"elapsed_ms": elapsed, "num_sources": len(results)}}
