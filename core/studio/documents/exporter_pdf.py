"""PDF exporter — render DocumentContentTree via HTML→WeasyPrint."""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from core.schemas.studio_schema import DocumentContentTree

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def export_to_pdf(
    content_tree: DocumentContentTree,
    output_path: Path,
) -> Path:
    """Render a DocumentContentTree to a PDF file.

    Uses Jinja2 for HTML templating and WeasyPrint for PDF rendering.
    Returns the output path.

    Raises RuntimeError if WeasyPrint is not available.
    """
    # Lazy import — WeasyPrint has heavy native deps
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise RuntimeError(
            "WeasyPrint is required for PDF export. "
            "Install it with: pip install weasyprint"
        ) from e

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build HTML from template
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("document_base.html.j2")

    # Prepare sections as dicts for template
    sections_data = [_section_to_dict(s) for s in content_tree.sections]

    html_content = template.render(
        doc_title=content_tree.doc_title,
        doc_type=content_tree.doc_type,
        abstract=content_tree.abstract,
        sections=sections_data,
        bibliography=content_tree.bibliography,
        css_path=str(_TEMPLATE_DIR / "document_base.css"),
    )

    # Render PDF
    html_obj = HTML(string=html_content, base_url=str(_TEMPLATE_DIR))
    html_obj.write_pdf(str(output_path))

    return output_path


def _section_to_dict(section) -> dict:
    """Convert a DocumentSection to a dict for Jinja2 rendering."""
    return {
        "id": section.id,
        "heading": section.heading,
        "level": section.level,
        "content": section.content or "",
        "subsections": [_section_to_dict(s) for s in (section.subsections or [])],
        "citations": section.citations or [],
    }
