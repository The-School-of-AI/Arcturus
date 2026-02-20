"""Episodic memory: skeleton storage and search (recipe retrieval)."""
import json
from pathlib import Path

from shared.state import PROJECT_ROOT


# Directory for skeleton_*.json files (under project root data area to avoid cluttering package)
MEMORY_DIR = PROJECT_ROOT / "memory" / "episodic_skeletons"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def search_episodes(query: str, limit: int = 5) -> list[dict]:
    """
    Search saved episode skeletons by text similarity (keyword overlap).
    Returns list of skeleton dicts with "id", "original_query", "nodes", etc., best matches first.
    """
    if not MEMORY_DIR.exists():
        return []
    query_lower = query.lower().split()
    scored: list[tuple[float, dict]] = []
    for path in MEMORY_DIR.glob("skeleton_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        text = (data.get("original_query") or "") + " " + " ".join(
            (n.get("task_goal") or n.get("description") or "")
            for n in data.get("nodes", [])
        )
        text_lower = text.lower()
        score = sum(1 for w in query_lower if w in text_lower)
        if score > 0:
            scored.append((score, data))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:limit]]


def get_recent_episodes(limit: int = 10) -> list[dict]:
    """Return the most recently modified episode skeletons."""
    if not MEMORY_DIR.exists():
        return []
    paths = sorted(
        MEMORY_DIR.glob("skeleton_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out = []
    for path in paths[:limit]:
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out