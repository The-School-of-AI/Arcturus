"""Multi-format export engine for P03 Spark pages.

Supports export to PDF, Markdown, HTML, and DOCX formats.
Phase 3: Interactive blocks and section-level refresh features.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional
import time


def _format_markdown_content(page: Dict[str, Any]) -> str:
    """Convert page JSON to clean Markdown format."""
    lines = [
        f"# {page.get('title', 'Untitled Page')}",
        "",
        f"*Generated from query: {page.get('query', 'N/A')}*",
        f"*Created: {page.get('metadata', {}).get('created_at', 'Unknown')}*",
        ""
    ]
    
    # Process sections
    for section in page.get("sections", []):
        lines.extend([
            f"## {section.get('title', 'Untitled Section')}",
            ""
        ])
        
        # Process blocks
        for block in section.get("blocks", []):
            if block.get("kind") == "markdown":
                lines.extend([block.get("text", ""), ""])
            
            elif block.get("kind") == "table":
                # Convert table to markdown
                columns = block.get("columns", [])
                rows = block.get("rows", [])
                
                if columns and rows:
                    # Table header
                    lines.append("| " + " | ".join(columns) + " |")
                    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
                    
                    # Table rows
                    for row in rows:
                        if len(row) == len(columns):
                            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
                    lines.append("")
            
            elif block.get("kind") == "highlight":
                metric = block.get("metric", "")
                value = block.get("value", "")
                source = block.get("source", "")
                lines.extend([
                    f"**{metric}:** {value}",
                    f"*Source: {source}*",
                    ""
                ])
            
            elif block.get("kind") == "media":
                media_type = block.get("media_type", "media")
                title = block.get("title", "Media")
                url = block.get("url", "")
                description = block.get("description", "")
                
                lines.extend([
                    f"### {title}",
                    f"*{media_type.title()}*: [View {media_type}]({url})",
                    f"{description}" if description else "",
                    ""
                ])
            
            elif block.get("kind") == "insight":
                title = block.get("title", "Insight")
                content = block.get("content", "")
                source = block.get("data_source", "")
                
                lines.extend([
                    f"### 💡 {title}",
                    content,
                    f"*Source: {source}*" if source else "",
                    ""
                ])
        
        # Process charts
        for chart in section.get("charts", []):
            chart_type = chart.get("type", "chart")
            chart_title = chart.get("title", "Chart")
            lines.extend([
                f"### 📊 {chart_title}",
                f"*Chart type: {chart_type.title()}*",
                "*[Chart visualization would appear here in interactive view]*",
                ""
            ])
    
    # Add citations
    citations = page.get("citations", {})
    if citations:
        lines.extend([
            "## References",
            ""
        ])
        for cid, citation in citations.items():
            title = citation.get("title", "Unknown Source")
            url = citation.get("url", "")
            credibility = citation.get("credibility", 0)
            
            lines.extend([
                f"**{cid}**: [{title}]({url}) (Credibility: {credibility:.2f})",
                ""
            ])
    
    return "\\n".join(lines)


def _format_html_content(page: Dict[str, Any]) -> str:
    """Convert page JSON to HTML format."""
    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        f"    <title>{page.get('title', 'Untitled Page')}</title>",
        "    <meta charset='utf-8'>",
        "    <style>",
        "        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }",
        "        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }",
        "        h2 { color: #34495e; border-left: 4px solid #3498db; padding-left: 15px; }",
        "        .metric-card { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 15px; margin: 10px 0; }",
        "        .chart-placeholder { background: #e9ecef; border-radius: 8px; padding: 40px; text-align: center; color: #6c757d; }",
        "        table { border-collapse: collapse; width: 100%; margin: 15px 0; }",
        "        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }",
        "        th { background-color: #f2f2f2; font-weight: bold; }",
        "        .media-block { border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px 0; }",
        "        .insight-block { background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 15px; margin: 10px 0; }",
        "        .citations { background: #f8f9fa; padding: 20px; border-radius: 8px; margin-top: 30px; }",
        "    </style>",
        "</head>",
        "<body>",
        f"    <h1>{page.get('title', 'Untitled Page')}</h1>",
        f"    <p><em>Generated from query: {page.get('query', 'N/A')}</em></p>",
        f"    <p><em>Created: {page.get('metadata', {}).get('created_at', 'Unknown')}</em></p>",
    ]
    
    # Process sections
    for section in page.get("sections", []):
        html_parts.extend([
            f"    <h2>{section.get('title', 'Untitled Section')}</h2>",
        ])
        
        # Process blocks
        for block in section.get("blocks", []):
            if block.get("kind") == "markdown":
                text = block.get("text", "").replace("\\n", "<br>")
                html_parts.append(f"    <div>{text}</div>")
            
            elif block.get("kind") == "table":
                columns = block.get("columns", [])
                rows = block.get("rows", [])
                
                if columns and rows:
                    html_parts.append("    <table>")
                    html_parts.append("        <thead><tr>")
                    for col in columns:
                        html_parts.append(f"            <th>{col}</th>")
                    html_parts.append("        </tr></thead>")
                    html_parts.append("        <tbody>")
                    
                    for row in rows:
                        html_parts.append("            <tr>")
                        for cell in row:
                            html_parts.append(f"                <td>{cell}</td>")
                        html_parts.append("            </tr>")
                    
                    html_parts.append("        </tbody>")
                    html_parts.append("    </table>")
            
            elif block.get("kind") == "highlight":
                metric = block.get("metric", "")
                value = block.get("value", "")
                source = block.get("source", "")
                html_parts.extend([
                    "    <div class='metric-card'>",
                    f"        <h4>{metric}</h4>",
                    f"        <p><strong>{value}</strong></p>",
                    f"        <small>Source: {source}</small>",
                    "    </div>"
                ])
            
            elif block.get("kind") == "media":
                title = block.get("title", "Media")
                url = block.get("url", "")
                description = block.get("description", "")
                media_type = block.get("media_type", "media")
                
                html_parts.extend([
                    "    <div class='media-block'>",
                    f"        <h4>{title}</h4>",
                    f"        <p><a href='{url}' target='_blank'>View {media_type}</a></p>",
                    f"        <p>{description}</p>",
                    "    </div>"
                ])
            
            elif block.get("kind") == "insight":
                title = block.get("title", "Insight")
                content = block.get("content", "")
                source = block.get("data_source", "")
                
                html_parts.extend([
                    "    <div class='insight-block'>",
                    f"        <h4>💡 {title}</h4>",
                    f"        <p>{content}</p>",
                    f"        <small>Source: {source}</small>" if source else "",
                    "    </div>"
                ])
        
        # Process charts
        for chart in section.get("charts", []):
            chart_type = chart.get("type", "chart")
            chart_title = chart.get("title", "Chart")
            html_parts.extend([
                "    <div class='chart-placeholder'>",
                f"        <h4>📊 {chart_title}</h4>",
                f"        <p>Chart type: {chart_type.title()}</p>",
                "        <p>[Interactive chart would appear here]</p>",
                "    </div>"
            ])
    
    # Add citations
    citations = page.get("citations", {})
    if citations:
        html_parts.extend([
            "    <div class='citations'>",
            "        <h2>References</h2>",
        ])
        for cid, citation in citations.items():
            title = citation.get("title", "Unknown Source")
            url = citation.get("url", "")
            credibility = citation.get("credibility", 0)
            
            html_parts.extend([
                f"        <p><strong>{cid}</strong>: <a href='{url}' target='_blank'>{title}</a> (Credibility: {credibility:.2f})</p>",
            ])
        html_parts.append("    </div>")
    
    html_parts.extend([
        "</body>",
        "</html>"
    ])
    
    return "\\n".join(html_parts)


def _format_docx_content(page: Dict[str, Any]) -> str:
    """Generate DOCX-compatible content (simplified for Phase 3)."""
    # For Phase 3, return a structured text format that could be converted to DOCX
    # In production, this would use python-docx library
    return f"""DOCX Export: {page.get('title', 'Untitled Page')}

Query: {page.get('query', 'N/A')}
Created: {page.get('metadata', {}).get('created_at', 'Unknown')}

{_format_markdown_content(page)}

[Note: Full DOCX export with python-docx library would be implemented in production]
"""


def export_page_to_format(page_id: str, format_type: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Export a page to the specified format.
    
    Args:
        page_id: The page to export
        format_type: One of 'pdf', 'markdown', 'html', 'docx'
        options: Export options (theme, layout, etc.)
    
    Returns:
        Export result with content or file path
    """
    options = options or {}
    
    # Load page
    try:
        from content import page_generator
        page = page_generator.load_page(page_id)
    except FileNotFoundError:
        return {"success": False, "error": f"Page {page_id} not found"}
    
    try:
        if format_type == "markdown":
            content = _format_markdown_content(page)
            filename = f"{page_id}.md"
            
        elif format_type == "html":
            content = _format_html_content(page)
            filename = f"{page_id}.html"
            
        elif format_type == "docx":
            content = _format_docx_content(page)
            filename = f"{page_id}.docx"
            
        elif format_type == "pdf":
            # For Phase 3, generate HTML and note PDF conversion needed
            html_content = _format_html_content(page)
            content = f"PDF Export (Phase 3 - HTML base):\\n{html_content}\\n\\n[Note: PDF generation via WeasyPrint would be implemented in production]"
            filename = f"{page_id}.pdf"
            
        else:
            return {"success": False, "error": f"Unsupported format: {format_type}"}
        
        # Save export to output directory
        output_dir = Path(__file__).resolve().parents[1] / "output" / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        export_path = output_dir / filename
        export_path.write_text(content, encoding="utf-8")
        
        return {
            "success": True,
            "format": format_type,
            "filename": filename,
            "path": str(export_path),
            "size": len(content),
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        
    except Exception as e:
        return {"success": False, "error": f"Export failed: {str(e)}"}


def get_export_formats() -> List[Dict[str, Any]]:
    """Get list of supported export formats with descriptions."""
    return [
        {
            "format": "markdown",
            "name": "Markdown",
            "description": "Clean Markdown format for documentation",
            "extension": ".md",
            "supports_charts": False,
            "supports_media": True
        },
        {
            "format": "html", 
            "name": "HTML",
            "description": "Styled HTML with CSS for web viewing",
            "extension": ".html",
            "supports_charts": False,  # Placeholders in Phase 3
            "supports_media": True
        },
        {
            "format": "pdf",
            "name": "PDF", 
            "description": "PDF document (via HTML conversion)",
            "extension": ".pdf",
            "supports_charts": False,
            "supports_media": True
        },
        {
            "format": "docx",
            "name": "Word Document",
            "description": "Microsoft Word compatible document", 
            "extension": ".docx",
            "supports_charts": False,
            "supports_media": True
        }
    ]