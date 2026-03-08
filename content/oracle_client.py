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


def _make_result(idx: int, query: str = "") -> Dict:
    cid = f"T{idx:03d}"
    
    # Generate diverse table structures based on index and query
    tables = []
    
    if idx == 1:  # Market data table
        tables.append({
            "id": f"market_tbl{idx}",
            "title": "Market Statistics",
            "columns": ["Metric", "2024", "2025", "2026 (Forecast)"],
            "rows": [
                ["Market Size ($B)", "12.4", "15.8", "20.3"],
                ["Growth Rate (%)", "18.5", "27.4", "28.5"],
                ["Units Sold (M)", "8.2", "12.1", "17.8"]
            ]
        })
    elif idx == 2:  # Regional breakdown
        tables.append({
            "id": f"region_tbl{idx}",
            "title": "Regional Analysis",
            "columns": ["Region", "Market Share (%)", "Revenue ($M)"],
            "rows": [
                ["North America", "35.2", "4280"],
                ["Europe", "28.7", "3495"],
                ["Asia Pacific", "31.1", "3783"],
                ["Others", "5.0", "608"]
            ]
        })
    elif idx == 3:  # Performance metrics
        tables.append({
            "id": f"perf_tbl{idx}",
            "title": "Performance Comparison",
            "columns": ["Product", "Rating", "Price ($)", "Sales (K)"],
            "rows": [
                ["Model A", "4.5", "299", "45.2"],
                ["Model B", "4.2", "399", "38.7"],
                ["Model C", "4.7", "499", "52.1"],
                ["Model D", "4.1", "249", "33.8"]
            ]
        })
    else:  # Default numerical data
        tables.append({
            "id": f"data_tbl{idx}",
            "title": f"Data Set {idx}",
            "columns": ["Category", "Value", "Percentage"],
            "rows": [
                [f"Item {idx}A", f"{100 + idx * 15}", f"{20 + idx * 5}%"],
                [f"Item {idx}B", f"{85 + idx * 12}", f"{15 + idx * 3}%"],
                [f"Item {idx}C", f"{120 + idx * 8}", f"{25 + idx * 2}%"]
            ]
        })
    
    # Generate media content based on index
    media = {}
    if idx <= 2:  # First two results have media
        media["images"] = []
        media["videos"] = []
        
        if idx == 1:
            media["images"].append({
                "url": f"https://example.org/images/chart_{idx}.png",
                "title": "Market Growth Chart",
                "description": "Visual representation of market growth trends",
                "thumbnail": f"https://example.org/thumbnails/chart_{idx}_thumb.png"
            })
            media["videos"].append({
                "url": f"https://example.org/videos/analysis_{idx}.mp4",
                "title": "Market Analysis Video",
                "description": "Expert analysis of market trends and forecasts",
                "thumbnail": f"https://example.org/thumbnails/video_{idx}_thumb.png",
                "duration": "5:42"
            })
        elif idx == 2:
            media["images"].extend([
                {
                    "url": f"https://example.org/images/regional_{idx}.png",
                    "title": "Regional Distribution Map", 
                    "description": "Geographic distribution of market presence",
                    "thumbnail": f"https://example.org/thumbnails/map_{idx}_thumb.png"
                },
                {
                    "url": f"https://example.org/images/infographic_{idx}.jpg",
                    "title": "Market Infographic",
                    "description": "Key statistics and trends visualization", 
                    "thumbnail": f"https://example.org/thumbnails/info_{idx}_thumb.jpg"
                }
            ])
    
    return {
        "citation_id": cid,
        "url": f"https://example.org/source/{cid}",
        "title": f"Analysis Report {idx}: {query[:20] if query else 'Market Data'}",
        "extracted_text": f"This comprehensive report {idx} provides detailed analysis of {query if query else 'market trends'} with supporting data and visualizations.",
        "snippet": f"Report {idx} snippet covering key findings and statistical analysis",
        "published_at": f"2025-{12-idx:02d}-01T00:00:00Z",
        "source_type": "research_report" if idx <= 2 else "article",
        "credibility_score": round(0.95 - idx * 0.05, 2),
        "structured_extracts": {
            "tables": tables
        },
        "media": media if media.get("images") or media.get("videos") else {}
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
    # produce k deterministic results with query context
    results: List[Dict] = [_make_result(i + 1, query) for i in range(min(k, 5))]
    elapsed = int((time.time() - start) * 1000)
    return {"query_id": str(uuid.uuid4()), "results": results, "metrics": {"elapsed_ms": elapsed, "num_sources": len(results)}}
