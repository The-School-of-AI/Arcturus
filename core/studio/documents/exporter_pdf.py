"""PDF exporter — render DocumentContentTree via HTML→xhtml2pdf."""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from core.schemas.studio_schema import DocumentContentTree
from core.studio.documents.markdown_render import markdown_to_html

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def export_to_pdf(
    content_tree: DocumentContentTree,
    output_path: Path,
) -> Path:
    """Render a DocumentContentTree to a PDF file.

    Uses Jinja2 for HTML templating and xhtml2pdf for PDF rendering.
    Returns the output path.

    Raises RuntimeError if xhtml2pdf is not available.
    """
    # Lazy import — keep startup fast
    try:
        from xhtml2pdf import pisa
    except ImportError as e:
        raise RuntimeError(
            "xhtml2pdf is required for PDF export. "
            "Install it with: pip install xhtml2pdf"
        ) from e

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Read CSS content for inline embedding
    css_file = _TEMPLATE_DIR / "document_base.css"
    css_inline = css_file.read_text(encoding="utf-8")

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
        abstract=markdown_to_html(content_tree.abstract),
        sections=sections_data,
        bibliography=content_tree.bibliography,
        css_inline=css_inline,
    )

    # Render PDF
    with open(str(output_path), "wb") as f:
        pisa_status = pisa.CreatePDF(html_content, dest=f)

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(
            f"PDF generation failed (pisa errors: {pisa_status.err})"
        )

    return output_path


def _section_to_dict(section) -> dict:
    """Convert a DocumentSection to a dict for Jinja2 rendering."""
    return {
        "id": section.id,
        "heading": section.heading,
        "level": section.level,
        "content": markdown_to_html(section.content),
        "subsections": [_section_to_dict(s) for s in (section.subsections or [])],
        "citations": section.citations or [],
    }
