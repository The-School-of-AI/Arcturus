"""Document type registry — templates and resolution for Phase 4 doc types."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# === Document type templates ===

DOC_TYPE_TEMPLATES: dict[str, dict[str, Any]] = {
    "technical_spec": {
        "label": "Technical Specification",
        "required_sections": ["Introduction", "Requirements", "Architecture", "Implementation"],
        "optional_sections": ["Glossary", "Appendix", "References", "Testing Strategy"],
        "min_sections": 4,
        "max_sections": 15,
    },
    "report": {
        "label": "Report",
        "required_sections": ["Executive Summary", "Introduction", "Findings", "Conclusion"],
        "optional_sections": ["Methodology", "Recommendations", "Appendix", "References"],
        "min_sections": 4,
        "max_sections": 20,
    },
    "proposal": {
        "label": "Proposal",
        "required_sections": ["Executive Summary", "Problem Statement", "Proposed Solution", "Timeline"],
        "optional_sections": ["Budget", "Risk Assessment", "Team", "References"],
        "min_sections": 4,
        "max_sections": 15,
    },
}

DEFAULT_DOC_TYPE = "report"

# Keywords mapped to doc types for auto-detection from prompts
_KEYWORD_MAP: dict[str, str] = {
    "technical_spec": "technical_spec",
    "tech spec": "technical_spec",
    "specification": "technical_spec",
    "architecture": "technical_spec",
    "report": "report",
    "analysis": "report",
    "findings": "report",
    "proposal": "proposal",
    "rfp": "proposal",
    "pitch": "proposal",
}


def resolve_document_type(
    parameters: dict[str, Any] | None = None,
    user_prompt: str | None = None,
) -> str:
    """Resolve document type with priority: parameters → prompt keywords → default."""
    # 1. Explicit parameter
    if parameters:
        explicit = parameters.get("doc_type") or parameters.get("document_type")
        if explicit and explicit in DOC_TYPE_TEMPLATES:
            return explicit

    # 2. Keyword detection from prompt
    if user_prompt:
        prompt_lower = user_prompt.lower()
        for keyword, doc_type in _KEYWORD_MAP.items():
            if keyword in prompt_lower:
                return doc_type

    return DEFAULT_DOC_TYPE


def get_doc_type_template(doc_type: str) -> dict[str, Any]:
    """Return template for a doc type, falling back to report."""
    return DOC_TYPE_TEMPLATES.get(doc_type, DOC_TYPE_TEMPLATES[DEFAULT_DOC_TYPE])
