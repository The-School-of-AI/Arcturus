"""ComparisonAgent stub: generates side-by-side analysis when multiple entities are involved."""
from __future__ import annotations

import hashlib
from typing import Dict, Any, List


async def generate_section(query: str, page_context: Dict[str, Any], resources: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a comparison section.

    For Phase 1 this is a deterministic stub that looks for multiple entities
    in the query and creates a basic comparison table or text blocks.
    """
    results: List[Dict[str, Any]] = resources.get("oracle_results", [])
    
    # Simple heuristic: if query contains comparison words, create comparison section
    comparison_words = ["vs", "versus", "compare", "comparison", "between", "and"]
    has_comparison = any(word in query.lower() for word in comparison_words)
    
    section_id = "comparison_" + hashlib.sha1(query.encode("utf-8")).hexdigest()[:8]
    
    if has_comparison and len(results) >= 2:
        # Create a comparison table using first two results
        result1 = results[0]
        result2 = results[1]
        
        blocks = [
            {
                "kind": "markdown",
                "text": f"## Comparison Analysis\n\nComparing key aspects found in the search results:"
            },
            {
                "kind": "table",
                "columns": ["Aspect", "Result 1", "Result 2"],
                "rows": [
                    ["Source", result1.get("title", "Unknown"), result2.get("title", "Unknown")],
                    ["Credibility", f"{result1.get('credibility_score', 0):.2f}", f"{result2.get('credibility_score', 0):.2f}"],
                    ["Content", result1.get("snippet", "")[:100] + "...", result2.get("snippet", "")[:100] + "..."]
                ]
            },
            {
                "kind": "citation",
                "ids": [result1.get("citation_id"), result2.get("citation_id")]
            }
        ]
    else:
        blocks = [
            {
                "kind": "markdown", 
                "text": f"## Analysis\n\nBased on available data for: **{query}**\n\nNo comparative analysis possible with current data."
            }
        ]
    
    section = {
        "id": section_id,
        "type": "comparison",
        "title": "Comparison Analysis",
        "blocks": blocks,
        "widgets": [],
        "metadata": {"comparison_detected": has_comparison},
    }
    
    return section