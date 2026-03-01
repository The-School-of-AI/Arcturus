"""Document outline and draft normalization for Phase 4 document types."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from core.schemas.studio_schema import DocumentContentTree, DocumentSection
from core.studio.documents.citations import (
    build_provenance_slots,
    normalize_bibliography,
    reconcile_citations_and_bibliography,
)
from core.studio.documents.types import (
    DEFAULT_DOC_TYPE,
    DOC_TYPE_TEMPLATES,
    get_doc_type_template,
    resolve_document_type,
)

logger = logging.getLogger(__name__)

MAX_DEPTH = 3

# Placeholder patterns to strip from content
_PLACEHOLDER_PATTERNS = [
    re.compile(r"\b(?:TBD|TODO|Lorem ipsum|Content to be developed|To be added|Placeholder)\b", re.IGNORECASE),
]


def normalize_document_content_tree_raw(data: dict) -> dict:
    """Normalize raw LLM JSON dict before Pydantic validation.

    Maps common LLM field-name variants to the canonical
    DocumentContentTree / DocumentSection field names so that
    ``validate_content_tree`` doesn't blow up with a 422.
    """
    # --- Top-level field aliases ---
    # doc_title
    if "doc_title" not in data:
        for alias in ("title", "name", "document_title"):
            if alias in data:
                data["doc_title"] = data.pop(alias)
                break
        else:
            data["doc_title"] = "Untitled Document"

    # doc_type
    if "doc_type" not in data:
        for alias in ("type", "document_type"):
            if alias in data:
                data["doc_type"] = data.pop(alias)
                break
        else:
            data["doc_type"] = DEFAULT_DOC_TYPE

    # Normalize unknown doc_type values to default
    if data["doc_type"] not in DOC_TYPE_TEMPLATES:
        logger.info(
            "Normalizing unknown doc_type '%s' to '%s' in raw data",
            data["doc_type"],
            DEFAULT_DOC_TYPE,
        )
        data["doc_type"] = DEFAULT_DOC_TYPE

    # sections — ensure it exists
    if "sections" not in data:
        data["sections"] = []

    # Normalize each section recursively
    data["sections"] = [_normalize_section_raw(s) for s in data["sections"] if isinstance(s, dict)]

    # bibliography — ensure it's a list
    if "bibliography" not in data:
        data["bibliography"] = []

    return data


def _normalize_section_raw(section: dict) -> dict:
    """Normalize a single section dict (and its children) recursively."""
    # heading: LLMs often use 'title' or 'name' instead of 'heading'
    if "heading" not in section:
        for alias in ("title", "name", "section_title"):
            if alias in section:
                section["heading"] = section.pop(alias)
                break
        else:
            section["heading"] = "Untitled Section"

    # id: coerce to str
    if "id" in section:
        section["id"] = str(section["id"])
    else:
        section["id"] = "sec0"

    # level: ensure int, default 1
    if "level" not in section:
        section["level"] = 1
    else:
        try:
            section["level"] = int(section["level"])
        except (TypeError, ValueError):
            section["level"] = 1

    # subsections: LLMs sometimes use 'children' (from the outline schema)
    if "subsections" not in section:
        for alias in ("children", "sub_sections"):
            if alias in section:
                section["subsections"] = section.pop(alias)
                break
        else:
            section["subsections"] = []

    # Recurse into subsections
    if isinstance(section["subsections"], list):
        section["subsections"] = [
            _normalize_section_raw(s) for s in section["subsections"] if isinstance(s, dict)
        ]
    else:
        section["subsections"] = []

    # citations: ensure list
    if "citations" not in section:
        section["citations"] = []

    return section


def normalize_document_outline(
    outline: Any,
    parameters: Optional[Dict[str, Any]] = None,
    user_prompt: Optional[str] = None,
) -> Any:
    """Normalize a document outline after LLM generation.

    - Resolves doc_type from parameters/prompt
    - Stores doc_type in outline parameters
    - Clamps section count to template limits
    - Inserts missing required sections
    """
    params = parameters or (outline.parameters if hasattr(outline, "parameters") else {})

    doc_type = resolve_document_type(params, user_prompt)
    template = get_doc_type_template(doc_type)

    # Store resolved doc_type in outline parameters
    if hasattr(outline, "parameters") and outline.parameters is not None:
        outline.parameters["doc_type"] = doc_type
    elif hasattr(outline, "parameters"):
        outline.parameters = {"doc_type": doc_type}

    # Clamp section count
    items = outline.items if hasattr(outline, "items") else []
    min_sections = template.get("min_sections", 3)
    max_sections = template.get("max_sections", 20)

    if len(items) > max_sections:
        outline.items = items[:max_sections]
        logger.info("Clamped outline items from %d to %d", len(items), max_sections)

    # Ensure required sections exist (by heading match)
    existing_titles = {item.title.lower().strip() for item in outline.items}
    required = template.get("required_sections", [])
    for req_section in required:
        if req_section.lower() not in existing_titles:
            from core.schemas.studio_schema import OutlineItem
            new_id = str(len(outline.items) + 1)
            outline.items.append(OutlineItem(
                id=new_id,
                title=req_section,
                description=f"Required section for {doc_type}",
                children=[],
            ))
            logger.info("Inserted missing required section: %s", req_section)

    return outline


def normalize_document_content_tree(
    content_tree: DocumentContentTree,
    outline: Optional[Any] = None,
    artifact_id: Optional[str] = None,
) -> DocumentContentTree:
    """Normalize a document content tree after LLM generation.

    - Validates doc_type
    - Synthesizes abstract if missing
    - Normalizes section IDs and levels
    - Removes placeholder text
    - Normalizes bibliography
    - Builds provenance slots in metadata
    """
    # Validate doc_type
    if content_tree.doc_type not in DOC_TYPE_TEMPLATES:
        logger.info("Normalizing unknown doc_type '%s' to '%s'", content_tree.doc_type, DEFAULT_DOC_TYPE)
        content_tree.doc_type = DEFAULT_DOC_TYPE

    # Synthesize abstract if missing
    if not content_tree.abstract and content_tree.sections:
        first_content = _find_first_content(content_tree.sections)
        if first_content:
            # Take first 200 chars as abstract
            content_tree.abstract = first_content[:200].rstrip() + ("..." if len(first_content) > 200 else "")

    # Normalize section IDs and levels
    _normalize_sections(content_tree.sections, prefix="sec", level=1, depth=1)

    # Remove placeholder text from all sections
    _strip_placeholders(content_tree.sections)

    # Normalize bibliography
    content_tree.bibliography = normalize_bibliography(content_tree.bibliography)
    content_tree.bibliography = reconcile_citations_and_bibliography(
        content_tree.sections, content_tree.bibliography
    )

    # Build provenance slots in metadata
    if content_tree.metadata is None:
        content_tree.metadata = {}
    existing_slots = content_tree.metadata.get("provenance_slots", [])
    content_tree.metadata["provenance_slots"] = build_provenance_slots(
        content_tree.bibliography, existing_slots
    )

    return content_tree


def _find_first_content(sections: List[DocumentSection]) -> Optional[str]:
    """Find the first non-empty content in a section tree."""
    for section in sections:
        if section.content and section.content.strip():
            return section.content.strip()
        if section.subsections:
            result = _find_first_content(section.subsections)
            if result:
                return result
    return None


def _normalize_sections(
    sections: List[DocumentSection],
    prefix: str,
    level: int,
    depth: int,
) -> None:
    """Recursively normalize section IDs and clamp levels."""
    for i, section in enumerate(sections, 1):
        section.id = f"{prefix}{i}"
        section.level = level

        if depth >= MAX_DEPTH:
            # Flatten any deeper subsections
            section.subsections = []
        elif section.subsections:
            _normalize_sections(
                section.subsections,
                prefix=f"{prefix}{i}_",
                level=level + 1,
                depth=depth + 1,
            )


def _strip_placeholders(sections: List[DocumentSection]) -> None:
    """Remove placeholder text patterns from section content."""
    for section in sections:
        if section.content:
            for pattern in _PLACEHOLDER_PATTERNS:
                section.content = pattern.sub("", section.content).strip()
        if section.subsections:
            _strip_placeholders(section.subsections)
