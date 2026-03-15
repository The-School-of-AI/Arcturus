"""DetailAgent: produces enhanced deeper dive section using Oracle outputs.

Phase 2 enhancements:
- Multi-source content synthesis
- Media blocks integration
- Structured sub-sections
- Enhanced readability and depth
"""
from __future__ import annotations

import hashlib
from typing import Dict, Any, List


def _organize_content_by_themes(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Organize Oracle results into thematic sub-sections for detailed analysis."""
    themes = []
    
    for i, result in enumerate(results[:4]):  # Process up to 4 results for detail
        # Extract key themes from titles and content
        title = result.get("title", f"Source {i+1}")
        content = result.get("extracted_text", "")
        snippet = result.get("snippet", "")
        
        # Determine theme based on content analysis
        theme_keywords = {
            "market": ["market", "industry", "business", "economy", "commercial"],
            "technology": ["technology", "technical", "innovation", "development", "engineering"],
            "analysis": ["analysis", "research", "study", "findings", "report"],
            "trends": ["trend", "future", "forecast", "prediction", "outlook"]
        }
        
        detected_theme = "general"
        max_matches = 0
        
        text_to_check = (title + " " + snippet).lower()
        for theme, keywords in theme_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in text_to_check)
            if matches > max_matches:
                max_matches = matches
                detected_theme = theme
        
        themes.append({
            "theme": detected_theme,
            "title": title,
            "content": content,
            "snippet": snippet,
            "source": result,
            "credibility": result.get("credibility_score", 0.5)
        })
    
    return themes


def _generate_detailed_content(query: str, themes: List[Dict[str, Any]]) -> str:
    """Generate comprehensive detailed content from organized themes."""
    if not themes:
        return f"Detailed analysis for '{query}' requires additional data sources for comprehensive coverage."
    
    content_parts = [
        f"# Detailed Analysis: {query.title()}",
        "",
        f"This detailed examination draws from {len(themes)} authoritative sources to provide comprehensive insights into {query}."
    ]
    
    # Group themes for better organization
    theme_groups = {}
    for theme_data in themes:
        theme = theme_data["theme"]
        if theme not in theme_groups:
            theme_groups[theme] = []
        theme_groups[theme].append(theme_data)
    
    # Generate sections for each theme
    for theme, theme_items in theme_groups.items():
        content_parts.extend([
            "",
            f"## {theme.title()} Perspective",
            ""
        ])
        
        for item in theme_items:
            content_parts.extend([
                f"### {item['title']}",
                "",
                f"{item['content'][:500]}{'...' if len(item['content']) > 500 else ''}",
                "",
                f"*Source credibility: {item['credibility']:.1f}/1.0*",
                ""
            ])
    
    return "\n".join(content_parts)


async def generate_section(query: str, page_context: Dict[str, Any], resources: Dict[str, Any]) -> Dict[str, Any]:
    """Generate enhanced detailed section with organized themes and media integration."""
    results = resources.get("oracle_results", [])
    
    # Organize content by themes
    themes = _organize_content_by_themes(results)
    
    # Generate comprehensive detailed content
    detailed_content = _generate_detailed_content(query, themes)
    
    section_id = "detail_" + hashlib.sha1((query + "detail").encode("utf-8")).hexdigest()[:8]
    
    # Build enhanced blocks
    blocks = [
        {
            "kind": "markdown",
            "text": detailed_content
        }
    ]
    
    # Add relevant media from sources
    media_count = 0
    for result in results[:3]:  # Check first 3 results for media
        media = result.get("media", {})
        
        # Add videos for detailed explanations
        if media.get("videos") and media_count < 1:  # Limit to 1 video in detail
            video = media["videos"][0]
            blocks.append({
                "kind": "media",
                "media_type": "video",
                "url": video["url"],
                "title": video.get("title", "Detailed Video Analysis"),
                "description": video.get("description", ""),
                "thumbnail": video.get("thumbnail"),
                "duration": video.get("duration"),
                "source": result.get("url", "")
            })
            media_count += 1
    
    # Add structured data insights if available
    for result in results[:2]:  # Process first 2 results for structured insights
        tables = result.get("structured_extracts", {}).get("tables", [])
        for table in tables[:1]:  # One table insight per result
            if len(table.get("rows", [])) > 1:  # Only if substantial data
                blocks.append({
                    "kind": "insight",
                    "title": f"Data Insight: {table.get('title', 'Analysis')}",
                    "content": f"Analysis reveals {len(table['rows'])} key data points from {result.get('title', 'research source')}, providing quantitative support for the detailed findings.",
                    "data_source": result.get("title", "Unknown Source"),
                    "credibility": result.get("credibility_score", 0.5)
                })
    
    # Add citations from all processed results
    citation_ids = [r["citation_id"] for r in results[:4] if r.get("citation_id")]  # Top 4 sources
    if citation_ids:
        blocks.append({
            "kind": "citation",
            "ids": citation_ids
        })
    
    section = {
        "id": section_id,
        "type": "detail",
        "title": "Detailed Analysis",
        "blocks": blocks,
        "widgets": [],
        "metadata": {
            "themes_analyzed": len(set(t["theme"] for t in themes)),
            "sources_processed": len(results),
            "media_included": media_count,
            "enhanced": True
        },
    }
    return section
