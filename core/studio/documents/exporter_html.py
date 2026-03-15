"""HTML exporter — render DocumentContentTree as self-contained HTML."""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader

from core.schemas.studio_schema import DocumentContentTree
from core.studio.documents.markdown_render import markdown_to_html_web

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_MERMAID_MARKER = '<div class="mermaid">'
_SAFE_URL_SCHEMES = frozenset({"http", "https", "mailto", "ftp", ""})


def _sanitize_bibliography(entries: list[dict] | None) -> list[dict]:
    """Return bibliography entries with unsafe URL schemes removed.

    Allows http, https, mailto, ftp, and relative URLs.  Entries with
    other schemes (e.g. ``javascript:``) have their ``url`` key deleted
    so the template renders them as plain text instead of ``<a>`` tags.
    """
    if not entries:
        return entries or []
    sanitized = []
    for entry in entries:
        entry = dict(entry)  # shallow copy to avoid mutating the original
        url = entry.get("url", "")
        if url:
            scheme = urlparse(url).scheme.lower()
            if scheme not in _SAFE_URL_SCHEMES:
                del entry["url"]
        sanitized.append(entry)
    return sanitized


def _collect_all_content(sections: list[dict]) -> str:
    """Recursively collect all rendered content from sections + subsections."""
    parts: list[str] = []
    for s in sections:
        parts.append(s.get("content", ""))
        if s.get("subsections"):
            parts.append(_collect_all_content(s["subsections"]))
    return " ".join(parts)


def export_to_html(
    content_tree: DocumentContentTree,
    output_path: Path,
    hero_image: bytes | None = None,
) -> Path:
    """Render a DocumentContentTree to a self-contained HTML file.

    Follows the same Jinja2 pattern as export_to_pdf but writes HTML
    directly instead of converting through xhtml2pdf.

    Returns the output path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    css_inline = (_TEMPLATE_DIR / "document_web.css").read_text(encoding="utf-8")

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("document_web.html.j2")

    sections_data = [_section_to_dict(s) for s in content_tree.sections]

    # Render abstract once; reuse for Mermaid detection and template
    abstract_html = markdown_to_html_web(content_tree.abstract)

    # Check all sections (including nested) AND abstract for Mermaid diagrams
    has_mermaid = (
        _MERMAID_MARKER in _collect_all_content(sections_data)
        or _MERMAID_MARKER in abstract_html
    )

    # Encode hero image as base64 data URI for self-containment
    hero_data_uri = None
    if hero_image:
        b64 = base64.b64encode(hero_image).decode("ascii")
        hero_data_uri = f"data:image/jpeg;base64,{b64}"

    html_content = template.render(
        doc_title=content_tree.doc_title,
        doc_type=content_tree.doc_type,
        abstract=abstract_html,
        sections=sections_data,
        bibliography=_sanitize_bibliography(content_tree.bibliography),
        css_inline=css_inline,
        has_mermaid=has_mermaid,
        hero_image=hero_data_uri,
    )

    output_path.write_text(html_content, encoding="utf-8")
    return output_path


def _section_to_dict(section) -> dict:
    """Convert a DocumentSection to a dict for Jinja2 rendering."""
    return {
        "id": section.id,
        "heading": section.heading,
        "level": section.level,
        "content": markdown_to_html_web(section.content),
        "subsections": [_section_to_dict(s) for s in (section.subsections or [])],
        "citations": section.citations or [],
    }
