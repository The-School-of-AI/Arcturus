"""OverviewAgent: produces an enhanced executive summary section using Oracle outputs.

Phase 2 enhancements:
- Key metrics extraction and highlighting
- Media blocks integration
- Multi-source summary synthesis
- Enhanced content structure
"""
from __future__ import annotations

import hashlib
from typing import Dict, Any, List


def _extract_key_metrics(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract key metrics from Oracle results for overview highlights."""
    metrics = []
    
    for result in results[:3]:  # Process top 3 results
        tables = result.get("structured_extracts", {}).get("tables", [])
        for table in tables:
            rows = table.get("rows", [])
            columns = table.get("columns", [])
            
            # Look for key metrics (percentages, currencies, growth rates)
            for row in rows[:5]:  # Check first 5 rows
                if len(row) >= 2:
                    metric_name = str(row[0])
                    metric_value = str(row[1] if len(row) > 1 else "")
                    
                    # Filter for important-looking metrics
                    if any(keyword in metric_name.lower() for keyword in 
                           ['growth', 'cagr', 'revenue', 'market', 'size', 'share', 'rate']):
                        metrics.append({
                            "name": metric_name,
                            "value": metric_value,
                            "source": result.get("title", "Unknown Source")
                        })
    
    return metrics[:4]  # Limit to 4 key metrics


def _generate_executive_summary(query: str, results: List[Dict[str, Any]], key_metrics: List[Dict[str, Any]]) -> str:
    """Generate enhanced executive summary with key insights."""
    if not results:
        return f"No comprehensive data available for '{query}'. Additional research may be required."
    
    # Build summary from multiple sources
    summary_parts = [
        f"# Executive Summary: {query.title()}",
        "",
        f"This analysis synthesizes information from {len(results)} authoritative sources to provide a comprehensive overview of {query}."
    ]
    
    # Add key metrics if available
    if key_metrics:
        summary_parts.extend([
            "",
            "## Key Metrics:",
            ""
        ])
        for metric in key_metrics:
            summary_parts.append(f"- **{metric['name']}**: {metric['value']}")
    
    # Add key insights from top sources
    if len(results) >= 2:
        summary_parts.extend([
            "",
            "## Key Insights:",
            "",
            f"Based on {results[0].get('source_type', 'research')} from {results[0].get('title', 'primary source')}, {results[0].get('snippet', 'relevant findings have been identified')}."
        ])
        
        if len(results) > 1:
            summary_parts.append(
                f"\nAdditional analysis from {results[1].get('title', 'secondary source')} provides complementary insights: {results[1].get('snippet', 'supporting data available')}."
            )
    
    return "\n".join(summary_parts)


async def generate_section(query: str, page_context: Dict[str, Any], resources: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an enhanced overview section with metrics, media, and comprehensive summary."""
    results = resources.get("oracle_results", [])
    
    # Extract key metrics for highlights
    key_metrics = _extract_key_metrics(results)
    
    # Generate comprehensive executive summary
    summary_content = _generate_executive_summary(query, results, key_metrics)
    
    section_id = "overview_" + hashlib.sha1(query.encode("utf-8")).hexdigest()[:8]
    
    # Build blocks with enhanced content
    blocks = [
        {
            "kind": "markdown", 
            "text": summary_content
        }
    ]
    
    # Add key metrics as highlight blocks
    if key_metrics:
        for metric in key_metrics[:2]:  # Top 2 metrics as highlights
            blocks.append({
                "kind": "highlight",
                "metric": metric["name"],
                "value": metric["value"],
                "source": metric["source"],
                "style": "metric-card"
            })
    
    # Add media from top result if available
    if results:
        top_result = results[0]
        media = top_result.get("media", {})
        
        # Add first image if available
        if media.get("images"):
            first_image = media["images"][0]
            blocks.append({
                "kind": "media",
                "media_type": "image",
                "url": first_image["url"],
                "title": first_image.get("title", "Overview Visualization"),
                "description": first_image.get("description", ""),
                "thumbnail": first_image.get("thumbnail"),
                "source": top_result.get("url", "")
            })
    
    # Add citation references
    citation_ids = [r["citation_id"] for r in results[:3] if r.get("citation_id")]  # Top 3 sources
    if citation_ids:
        blocks.append({
            "kind": "citation", 
            "ids": citation_ids
        })
    
    section = {
        "id": section_id,
        "type": "overview",
        "title": "Executive Summary",
        "blocks": blocks,
        "widgets": [],
        "metadata": {
            "key_metrics_count": len(key_metrics),
            "sources_synthesized": len(results),
            "enhanced": True
        },
    }
    return section
