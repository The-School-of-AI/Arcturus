"""Bibliography and provenance helpers for document normalization."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set


def normalize_bibliography(entries: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Deduplicate bibliography entries by key and ensure required fields."""
    seen: Dict[str, int] = {}
    result: List[Dict[str, str]] = []
    for entry in entries:
        key = entry.get("key", "").strip()
        if not key:
            continue
        if key in seen:
            # Update existing entry with any new fields
            idx = seen[key]
            for field, value in entry.items():
                if value and (field not in result[idx] or not result[idx][field]):
                    result[idx][field] = value
        else:
            # Ensure required fields exist
            normalized = {
                "key": key,
                "title": entry.get("title", key),
                "author": entry.get("author", "Unknown"),
            }
            # Preserve extra fields
            for field, value in entry.items():
                if field not in normalized:
                    normalized[field] = value
            seen[key] = len(result)
            result.append(normalized)
    return result


def extract_citation_keys_from_sections(sections: List[Any]) -> Set[str]:
    """Recursively extract all citation keys from section trees."""
    keys: Set[str] = set()
    for section in sections:
        # Direct citations list
        citations = getattr(section, "citations", None) or []
        keys.update(citations)
        # Inline citation patterns like [key] in content
        content = getattr(section, "content", None) or ""
        keys.update(re.findall(r"\[([a-zA-Z0-9_-]+)\]", content))
        # Recurse into subsections
        subsections = getattr(section, "subsections", None) or []
        keys.update(extract_citation_keys_from_sections(subsections))
    return keys


def reconcile_citations_and_bibliography(
    sections: List[Any],
    bibliography: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """Add placeholder bibliography entries for orphan citation keys."""
    used_keys = extract_citation_keys_from_sections(sections)
    bib_keys = {entry["key"] for entry in bibliography}
    orphans = used_keys - bib_keys

    result = list(bibliography)
    for key in sorted(orphans):
        result.append({
            "key": key,
            "title": f"[{key}]",
            "author": "Unknown",
        })
    return result


def build_provenance_slots(
    bibliography: List[Dict[str, str]],
    existing_slots: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Generate placeholder provenance slots for bibliography entries."""
    existing_keys = set()
    if existing_slots:
        for slot in existing_slots:
            existing_keys.add(slot.get("citation_key", ""))

    slots = list(existing_slots or [])
    for entry in bibliography:
        key = entry.get("key", "")
        if key and key not in existing_keys:
            slots.append({
                "citation_key": key,
                "source_type": "reference",
                "verified": False,
            })
    return slots
