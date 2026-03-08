"""ComparisonAgent: generates enhanced side-by-side analysis with visualizations.

Phase 2 enhancements:
- Multi-entity comparison with visual charts
- Comprehensive comparison metrics
- Scoring and evaluation matrices
- Enhanced data visualization for comparisons
"""
from __future__ import annotations

import hashlib
from typing import Dict, Any, List, Tuple


def _detect_comparison_entities(query: str, results: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Detect if query involves comparison and extract entities being compared."""
    comparison_words = ["vs", "versus", "compare", "comparison", "between", "difference", 
                      "better", "best", "worst", "against", "or"]
    has_comparison = any(word in query.lower() for word in comparison_words)
    
    entities = []
    if has_comparison:
        # Extract potential entities from query and results
        query_words = query.lower().split()
        for result in results[:4]:  # Check first 4 results
            title = result.get("title", "")
            # Extract meaningful terms that could be entities
            title_words = title.lower().split()
            for word in title_words:
                if len(word) > 3 and word not in ["the", "and", "for", "with", "analysis", "report"]:
                    if word not in entities:
                        entities.append(word.capitalize())
    
    return has_comparison, entities[:6]  # Limit to 6 entities


def _extract_comparison_metrics(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract numerical metrics suitable for comparison from Oracle results."""
    comparison_data = []
    
    for idx, result in enumerate(results[:4]):
        entity_data = {
            "name": result.get("title", f"Entity {idx + 1}"),
            "credibility": result.get("credibility_score", 0.5),
            "source_type": result.get("source_type", "unknown"),
            "citation_id": result.get("citation_id", f"C{idx+1}"),
            "metrics": {}
        }
        
        # Extract numerical data from tables
        tables = result.get("structured_extracts", {}).get("tables", [])
        for table in tables:
            columns = table.get("columns", [])
            rows = table.get("rows", [])
            
            for row in rows[:5]:  # Process first 5 rows
                if len(row) >= 2:
                    metric_name = str(row[0]).lower()
                    metric_value = row[1]
                    
                    # Try to extract numerical values
                    try:
                        if isinstance(metric_value, (int, float)):
                            entity_data["metrics"][metric_name] = float(metric_value)
                        elif isinstance(metric_value, str):
                            # Handle percentages, currency, etc.
                            clean_val = metric_value.replace('%', '').replace('$', '').replace(',', '').strip()
                            entity_data["metrics"][metric_name] = float(clean_val)
                    except (ValueError, AttributeError):
                        pass
        
        comparison_data.append(entity_data)
    
    return comparison_data


def _generate_comparison_charts(comparison_data: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Generate comparison charts from extracted metrics."""
    charts = []
    
    if len(comparison_data) < 2:
        return charts
    
    chart_id_base = hashlib.sha1(f"comparison_{query}".encode()).hexdigest()[:8]
    
    # Find common metrics across entities
    all_metrics = set()
    for entity in comparison_data:
        all_metrics.update(entity["metrics"].keys())
    
    common_metrics = []
    for metric in all_metrics:
        entities_with_metric = sum(1 for entity in comparison_data if metric in entity["metrics"])
        if entities_with_metric >= 2:  # At least 2 entities have this metric
            common_metrics.append(metric)
    
    # Create comparison bar chart
    if common_metrics:
        primary_metric = common_metrics[0]
        
        charts.append({
            "chart_id": f"comp_bar_{chart_id_base}",
            "type": "bar",
            "title": f"Comparison: {primary_metric.title()}",
            "chart_data": {
                "labels": [entity["name"][:20] for entity in comparison_data if primary_metric in entity["metrics"]],
                "datasets": [{
                    "label": primary_metric.title(),
                    "data": [entity["metrics"][primary_metric] for entity in comparison_data if primary_metric in entity["metrics"]],
                    "backgroundColor": [
                        "rgba(54, 162, 235, 0.6)",
                        "rgba(255, 99, 132, 0.6)",
                        "rgba(255, 205, 86, 0.6)",
                        "rgba(75, 192, 192, 0.6)"
                    ],
                    "borderColor": [
                        "rgba(54, 162, 235, 1)",
                        "rgba(255, 99, 132, 1)",
                        "rgba(255, 205, 86, 1)",
                        "rgba(75, 192, 192, 1)"
                    ],
                    "borderWidth": 1
                }]
            },
            "config": {
                "responsive": True,
                "plugins": {"legend": {"display": True}},
                "scales": {"y": {"beginAtZero": True}}
            }
        })
    
    # Create multi-metric radar chart if multiple common metrics
    if len(common_metrics) >= 3:
        datasets = []
        colors = [
            "rgba(54, 162, 235, 0.6)",
            "rgba(255, 99, 132, 0.6)", 
            "rgba(255, 205, 86, 0.6)",
            "rgba(75, 192, 192, 0.6)"
        ]
        
        for idx, entity in enumerate(comparison_data[:4]):
            if len(entity["metrics"]) >= 2:
                data_points = [entity["metrics"].get(metric, 0) for metric in common_metrics[:6]]
                datasets.append({
                    "label": entity["name"][:15],
                    "data": data_points,
                    "backgroundColor": colors[idx % len(colors)],
                    "borderColor": colors[idx % len(colors)].replace("0.6", "1"),
                    "pointBackgroundColor": colors[idx % len(colors)]
                })
        
        if datasets:
            charts.append({
                "chart_id": f"comp_radar_{chart_id_base}",
                "type": "radar",
                "title": "Multi-Metric Comparison",
                "chart_data": {
                    "labels": [metric.title() for metric in common_metrics[:6]],
                    "datasets": datasets
                },
                "config": {
                    "responsive": True,
                    "plugins": {"legend": {"position": "top"}},
                    "scales": {"r": {"beginAtZero": True}}
                }
            })
    
    return charts


def _generate_comparison_table(comparison_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate comprehensive comparison table."""
    if not comparison_data:
        return None
    
    # Build columns
    columns = ["Aspect"] + [entity["name"][:20] for entity in comparison_data]
    rows = []
    
    # Add basic comparison rows
    rows.append(["Source Type"] + [entity["source_type"].title() for entity in comparison_data])
    rows.append(["Credibility"] + [f"{entity['credibility']:.2f}" for entity in comparison_data])
    
    # Add metric comparison rows
    all_metrics = set()
    for entity in comparison_data:
        all_metrics.update(entity["metrics"].keys())
    
    for metric in sorted(all_metrics):
        row = [metric.title()]
        for entity in comparison_data:
            value = entity["metrics"].get(metric, "N/A")
            row.append(f"{value:.2f}" if isinstance(value, (int, float)) else str(value))
        rows.append(row)
    
    return {
        "kind": "table",
        "title": "Detailed Comparison",
        "columns": columns,
        "rows": rows,
        "metadata": {
            "entities_compared": len(comparison_data),
            "metrics_analyzed": len(all_metrics)
        }
    }


async def generate_section(query: str, page_context: Dict[str, Any], resources: Dict[str, Any]) -> Dict[str, Any]:
    """Generate enhanced comparison section with charts and comprehensive analysis."""
    results: List[Dict[str, Any]] = resources.get("oracle_results", [])
    
    # Detect comparison intent and entities
    has_comparison, entities = _detect_comparison_entities(query, results)
    
    section_id = "comparison_" + hashlib.sha1(query.encode("utf-8")).hexdigest()[:8]
    blocks = []
    charts = []
    
    if has_comparison and len(results) >= 2:
        # Extract comparison metrics
        comparison_data = _extract_comparison_metrics(results)
        
        # Generate introduction
        blocks.append({
            "kind": "markdown",
            "text": f"# Comparative Analysis: {query.title()}\n\nThis section provides a comprehensive side-by-side analysis of {len(comparison_data)} entities based on available research data. The comparison includes quantitative metrics, credibility scoring, and visual representations to facilitate informed decision-making."
        })
        
        # Add comparison table
        comparison_table = _generate_comparison_table(comparison_data)
        if comparison_table:
            blocks.append(comparison_table)
        
        # Generate comparison charts
        comparison_charts = _generate_comparison_charts(comparison_data, query)
        charts.extend(comparison_charts)
        
        # Add insights summary
        if comparison_data:
            # Find highest/lowest performers
            if comparison_data[0]["metrics"]:
                primary_metric = list(comparison_data[0]["metrics"].keys())[0]
                sorted_entities = sorted(comparison_data, 
                                       key=lambda x: x["metrics"].get(primary_metric, 0), 
                                       reverse=True)
                
                insights = f"**Key Insights:**\n\n"
                if len(sorted_entities) >= 2:
                    insights += f"- **Top performer:** {sorted_entities[0]['name']} leads in {primary_metric} metrics\n"
                    insights += f"- **Credibility leader:** {max(comparison_data, key=lambda x: x['credibility'])['name']} has the highest source credibility ({max(comparison_data, key=lambda x: x['credibility'])['credibility']:.2f})\n"
                    insights += f"- **Data coverage:** Analysis includes {len(set().union(*[e['metrics'].keys() for e in comparison_data]))} distinct metrics across {len(comparison_data)} entities"
                
                blocks.append({
                    "kind": "markdown",
                    "text": insights
                })
        
        # Add citations
        citation_ids = [entity["citation_id"] for entity in comparison_data if entity.get("citation_id")]
        if citation_ids:
            blocks.append({
                "kind": "citation",
                "ids": citation_ids
            })
    
    else:
        # No comparison detected or insufficient data
        blocks.append({
            "kind": "markdown", 
            "text": f"""# Analysis: {query.title()}

Based on available research data, this appears to be an analytical query rather than a comparative one. {'Detected entities: ' + ', '.join(entities) if entities else 'No comparative entities identified.'}

For comparative analysis, try queries with terms like 'vs', 'compare', or 'between' along with specific entities to analyze."""
        })
        
        # Still add general citation if results available
        if results:
            citation_ids = [r.get("citation_id") for r in results[:2] if r.get("citation_id")]
            if citation_ids:
                blocks.append({
                    "kind": "citation",
                    "ids": citation_ids
                })
    
    section = {
        "id": section_id,
        "type": "comparison",
        "title": "Comparative Analysis",
        "blocks": blocks,
        "charts": charts,
        "metadata": {
            "comparison_detected": has_comparison,
            "entities_found": len(entities),
            "charts_generated": len(charts),
            "enhanced": True
        },
    }
    
    return section