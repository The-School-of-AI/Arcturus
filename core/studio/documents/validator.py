"""Document export validators — DOCX and PDF post-export checks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from core.schemas.studio_schema import DocumentContentTree

logger = logging.getLogger(__name__)


def validate_docx(
    output_path: Path,
    content_tree: Optional[DocumentContentTree] = None,
) -> Dict[str, Any]:
    """Validate an exported DOCX file.

    Returns dict with: valid, format, errors, warnings, paragraph_count,
    heading_count, text_present, bibliography_present.
    """
    errors = []
    warnings = []

    try:
        from docx import Document
        doc = Document(str(output_path))
    except Exception as e:
        return {
            "valid": False,
            "format": "docx",
            "errors": [f"Cannot open DOCX: {e}"],
            "warnings": [],
            "paragraph_count": 0,
            "heading_count": 0,
            "text_present": False,
            "bibliography_present": False,
        }

    paragraphs = doc.paragraphs
    paragraph_count = len(paragraphs)
    heading_count = sum(
        1 for p in paragraphs
        if p.style and p.style.name and p.style.name.startswith("Heading")
    )
    text_present = any(p.text.strip() for p in paragraphs)

    # Check for bibliography section
    bibliography_present = any(
        "bibliography" in (p.text or "").lower()
        for p in paragraphs
        if p.style and p.style.name and p.style.name.startswith("Heading")
    )

    if paragraph_count == 0:
        errors.append("DOCX has no paragraphs")
    if heading_count == 0:
        errors.append("DOCX has no headings")
    if not text_present:
        errors.append("DOCX has no text content")

    # Cross-check with content tree if provided
    if content_tree:
        expected_sections = _count_sections(content_tree.sections)
        if heading_count < expected_sections:
            warnings.append(
                f"Expected at least {expected_sections} headings, found {heading_count}"
            )
        if content_tree.bibliography and not bibliography_present:
            warnings.append("Bibliography section not found in DOCX")

    return {
        "valid": len(errors) == 0,
        "format": "docx",
        "errors": errors,
        "warnings": warnings,
        "paragraph_count": paragraph_count,
        "heading_count": heading_count,
        "text_present": text_present,
        "bibliography_present": bibliography_present,
    }


def validate_pdf(
    output_path: Path,
    content_tree: Optional[DocumentContentTree] = None,
) -> Dict[str, Any]:
    """Validate an exported PDF file.

    Uses pymupdf (fitz) for PDF inspection.
    Returns dict with: valid, format, errors, warnings, page_count,
    text_present, bibliography_present.
    """
    errors = []
    warnings = []

    try:
        import fitz
        pdf_doc = fitz.open(str(output_path))
    except Exception as e:
        return {
            "valid": False,
            "format": "pdf",
            "errors": [f"Cannot open PDF: {e}"],
            "warnings": [],
            "page_count": 0,
            "text_present": False,
            "bibliography_present": False,
        }

    page_count = len(pdf_doc)
    all_text = ""
    for page in pdf_doc:
        all_text += page.get_text()
    pdf_doc.close()

    text_present = bool(all_text.strip())
    bibliography_present = "bibliography" in all_text.lower()

    if page_count == 0:
        errors.append("PDF has no pages")
    if not text_present:
        errors.append("PDF has no text content")

    # Cross-check with content tree if provided
    if content_tree:
        if content_tree.doc_title and content_tree.doc_title not in all_text:
            warnings.append("Document title not found in PDF text")
        if content_tree.bibliography and not bibliography_present:
            warnings.append("Bibliography section not found in PDF")

    return {
        "valid": len(errors) == 0,
        "format": "pdf",
        "errors": errors,
        "warnings": warnings,
        "page_count": page_count,
        "text_present": text_present,
        "bibliography_present": bibliography_present,
    }


def _count_sections(sections) -> int:
    """Count total sections including subsections."""
    count = 0
    for section in sections:
        count += 1
        if section.subsections:
            count += _count_sections(section.subsections)
    return count
