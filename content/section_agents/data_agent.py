"""DataAgent: extract tables and generate charts from Oracle structured extracts.

Phase 2 enhancements:
- Multiple chart types (bar, line, pie, scatter)
- Chart generation from structured data
- Media blocks support
- Enhanced data visualization
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Dict, Any, List, Optional


def _extract_numeric_data(table: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract numeric data suitable for charting from table structure."""
    columns = table.get("columns", [])
    rows = table.get("rows", [])
    
    chart_data = []
    if len(columns) >= 2 and rows:
        # Find label and value columns
        label_col = 0
        value_cols = []
        
        for i, col in enumerate(columns):
            if any(keyword in col.lower() for keyword in ['value', 'amount', 'count', 'number', 'percent', '%', 'score', 'rate']):
                value_cols.append(i)
        
        if not value_cols and len(columns) >= 2:
            value_cols = [1]  # Default to second column
        
        # Convert rows to chart data
        for row in rows[:10]:  # Limit to 10 items for charts
            if len(row) > max(value_cols) if value_cols else 1:
                data_point = {"label": str(row[label_col] or "Unknown")}
                
                for i, val_col in enumerate(value_cols):
                    val = row[val_col]
                    # Try to extract numeric value
                    try:
                        if isinstance(val, (int, float)):
                            numeric_val = float(val)
                        elif isinstance(val, str):
                            # Handle percentage, currency, etc.
                            clean_val = val.replace('%', '').replace('$', '').replace(',', '').strip()
                            numeric_val = float(clean_val)
                        else:
                            continue
                        
                        key = f"value{i}" if len(value_cols) > 1 else "value"
                        data_point[key] = numeric_val
                    except (ValueError, AttributeError):
                        continue
                
                if any(k != "label" for k in data_point.keys()):
                    chart_data.append(data_point)
    
    return chart_data[:8]  # Limit chart points


def _generate_charts_from_data(query: str, chart_data: List[Dict[str, Any]], table_title: str = "") -> List[Dict[str, Any]]:
    """Generate multiple chart configurations from extracted data."""
    charts = []
    
    if not chart_data:
        return charts
    
    # Determine appropriate chart types based on data
    has_multiple_values = any(len([k for k in item.keys() if k != "label"]) > 1 for item in chart_data)
    
    chart_id_base = hashlib.sha1(f"{query}_{table_title}".encode()).hexdigest()[:8]
    
    # Bar chart (always suitable for categorical data)
    charts.append({
        "chart_id": f"bar_{chart_id_base}",
        "type": "bar",
        "title": f"Bar Chart: {table_title or 'Data Overview'}",
        "chart_data": {
            "labels": [item["label"] for item in chart_data],
            "datasets": [{
                "label": "Value",
                "data": [item.get("value", item.get("value0", 0)) for item in chart_data],
                "backgroundColor": "rgba(54, 162, 235, 0.6)",
                "borderColor": "rgba(54, 162, 235, 1)",
                "borderWidth": 1
            }]
        },
        "config": {
            "responsive": True,
            "plugins": {"legend": {"display": True}},
            "scales": {"y": {"beginAtZero": True}}
        }
    })
    
    # Line chart if data suggests trends
    if len(chart_data) >= 3:
        charts.append({
            "chart_id": f"line_{chart_id_base}",
            "type": "line",
            "title": f"Trend: {table_title or 'Data Trend'}",
            "chart_data": {
                "labels": [item["label"] for item in chart_data],
                "datasets": [{
                    "label": "Trend",
                    "data": [item.get("value", item.get("value0", 0)) for item in chart_data],
                    "borderColor": "rgba(255, 99, 132, 1)",
                    "backgroundColor": "rgba(255, 99, 132, 0.2)",
                    "tension": 0.4
                }]
            },
            "config": {
                "responsive": True,
                "plugins": {"legend": {"display": True}}
            }
        })
    
    # Pie chart for proportional data (if values sum meaningfully) 
    total_value = sum(item.get("value", item.get("value0", 0)) for item in chart_data)
    if total_value > 0 and len(chart_data) <= 6:
        charts.append({
            "chart_id": f"pie_{chart_id_base}",
            "type": "pie",
            "title": f"Distribution: {table_title or 'Data Distribution'}",
            "chart_data": {
                "labels": [item["label"] for item in chart_data],
                "datasets": [{
                    "data": [item.get("value", item.get("value0", 0)) for item in chart_data],
                    "backgroundColor": [
                        "rgba(255, 99, 132, 0.8)",
                        "rgba(54, 162, 235, 0.8)", 
                        "rgba(255, 205, 86, 0.8)",
                        "rgba(75, 192, 192, 0.8)",
                        "rgba(153, 102, 255, 0.8)",
                        "rgba(255, 159, 64, 0.8)"
                    ]
                }]
            },
            "config": {
                "responsive": True,
                "plugins": {"legend": {"position": "right"}}
            }
        })
    
    return charts


def _generate_media_blocks(query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate media blocks from Oracle results."""
    media_blocks = []
    
    # Look for media references in Oracle results
    for result in results:
        media = result.get("media", {})
        
        # Images
        if media.get("images"):
            for img in media["images"][:2]:  # Limit to 2 images
                media_blocks.append({
                    "kind": "media",
                    "media_type": "image",
                    "url": img.get("url"),
                    "title": img.get("title", "Related Image"),
                    "description": img.get("description", ""),
                    "thumbnail": img.get("thumbnail"),
                    "source": result.get("url", "")
                })
        
        # Videos
        if media.get("videos"):
            for vid in media["videos"][:1]:  # Limit to 1 video
                media_blocks.append({
                    "kind": "media",
                    "media_type": "video",
                    "url": vid.get("url"),
                    "title": vid.get("title", "Related Video"),
                    "description": vid.get("description", ""),
                    "thumbnail": vid.get("thumbnail"),
                    "duration": vid.get("duration"),
                    "source": result.get("url", "")
                })
    
    return media_blocks


async def generate_section(query: str, page_context: Dict[str, Any], resources: Dict[str, Any]) -> Dict[str, Any]:
    """Generate enhanced data section with tables, charts, and media blocks."""
    results: List[Dict[str, Any]] = resources.get("oracle_results", [])
    
    section_id = "data_" + hashlib.sha1(query.encode("utf-8")).hexdigest()[:8]
    blocks = []
    charts = []
    
    # Process tables and generate charts
    tables_found = 0
    for r in results:
        tables = r.get("structured_extracts", {}).get("tables", [])
        for table in tables[:3]:  # Process up to 3 tables
            table_title = table.get("title", f"Data Table {tables_found + 1}")
            
            # Add table block
            blocks.append({
                "kind": "table",
                "title": table_title,
                "columns": table.get("columns", []),
                "rows": table.get("rows", []),
                "metadata": {
                    "source": r.get("title", "Unknown Source"),
                    "url": r.get("url", "")
                }
            })
            
            # Generate charts from table data
            chart_data = _extract_numeric_data(table)
            if chart_data:
                table_charts = _generate_charts_from_data(query, chart_data, table_title)
                charts.extend(table_charts[:2])  # Limit to 2 charts per table
            
            tables_found += 1
    
    # Add media blocks
    media_blocks = _generate_media_blocks(query, results)
    blocks.extend(media_blocks)
    
    # If no structured data found, add explanatory content
    if not blocks:
        blocks.append({
            "kind": "markdown", 
            "text": f"No structured data or media found for '{query}'. This section would benefit from additional data sources."
        })
    
    # Add summary chart if we have multiple data sources
    if tables_found > 1:
        charts.append({
            "chart_id": f"summary_{section_id}",
            "type": "scatter",
            "title": "Data Sources Overview",
            "chart_data": {
                "datasets": [{
                    "label": "Data Points",
                    "data": [{"x": i, "y": len(r.get("structured_extracts", {}).get("tables", []))} 
                             for i, r in enumerate(results[:tables_found])],
                    "backgroundColor": "rgba(75, 192, 192, 0.6)"
                }]
            },
            "config": {
                "responsive": True,
                "scales": {
                    "x": {"title": {"display": True, "text": "Source Index"}},
                    "y": {"title": {"display": True, "text": "Data Tables"}}
                }
            }
        })
    
    section = {
        "id": section_id,
        "type": "data",
        "title": "Data & Visualizations",
        "blocks": blocks,
        "charts": charts,
        "metadata": {
            "tables_count": tables_found,
            "charts_count": len(charts),
            "media_count": len(media_blocks),
            "enhanced": True
        },
    }
    return section
