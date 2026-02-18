"""Episodic memory storage and retrieval for session skeletons."""

import json
from pathlib import Path
from typing import List, Dict, Any

MEMORY_DIR = Path(__file__).resolve().parent / "episodes"
MEMORY_DIR.mkdir(exist_ok=True)


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
            text = json.dumps(data).lower()
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
