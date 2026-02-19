"""Episodic memory storage and retrieval for session skeletons."""

import json
from pathlib import Path
from typing import Any, Dict, List

MEMORY_DIR = Path(__file__).resolve().parent / "episodes"
MEMORY_DIR.mkdir(exist_ok=True)


def _extract_searchable_text(data: Any) -> str:
    """Recursively extract string values from a nested structure, ignoring dict keys."""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        return " ".join(_extract_searchable_text(v) for v in data.values())
    if isinstance(data, list):
        return " ".join(_extract_searchable_text(item) for item in data)
    return str(data) if data is not None else ""


def search_episodes(query: str, limit: int = 3) -> List[Dict]:
    """Search skeleton files for episodes matching the query (keyword match)."""
    if not MEMORY_DIR.exists():
        return []

    results = []
    query_lower = query.lower()
    query_terms = query_lower.split()

    for f in sorted(MEMORY_DIR.glob("skeleton_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text())
            text = _extract_searchable_text(data).lower()
            if any(term in text for term in query_terms):
                results.append(data)
                if len(results) >= limit:
                    break
        except Exception:
            continue

    return results


def get_recent_episodes(limit: int = 5) -> List[Dict]:
    """Return the most recent episode skeletons."""
    if not MEMORY_DIR.exists():
        return []

    results = []
    for f in sorted(MEMORY_DIR.glob("skeleton_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            results.append(json.loads(f.read_text()))
            if len(results) >= limit:
                break
        except Exception:
            continue

    return results
