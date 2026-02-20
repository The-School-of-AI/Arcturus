"""Episodic memory module: stores and retrieves session skeleton recipes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from shared.state import PROJECT_ROOT

# Directory where skeleton files are stored
MEMORY_DIR = PROJECT_ROOT / "memory" / "episodic_skeletons"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _load_skeleton(file_path: Path) -> dict[str, Any]:
    """Load a skeleton JSON file."""
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _calculate_relevance_score(skeleton: dict[str, Any], query: str) -> float:
    """Compute keyword relevance score for an episode skeleton."""
    query_words = set(re.findall(r"\w+", query.lower()))
    if not query_words:
        return 0.0

    score = 0.0

    original_query = str(skeleton.get("original_query", "")).lower()
    if original_query:
        original_words = set(re.findall(r"\w+", original_query))
        score += len(query_words & original_words) * 3.0

    for node in skeleton.get("nodes", []):
        task_goal = str(node.get("task_goal", "")).lower()
        if task_goal:
            task_words = set(re.findall(r"\w+", task_goal))
            score += len(query_words & task_words) * 2.0

        instruction = str(node.get("instruction", "")).lower()
        if instruction:
            inst_words = set(re.findall(r"\w+", instruction))
            score += len(query_words & inst_words)

    return score / len(query_words)


def search_episodes(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search relevant past episodes by query similarity."""
    if not MEMORY_DIR.exists():
        return []

    scored_episodes: list[tuple[float, dict[str, Any]]] = []
    for file_path in MEMORY_DIR.glob("skeleton_*.json"):
        skeleton = _load_skeleton(file_path)
        if not skeleton:
            continue

        score = _calculate_relevance_score(skeleton, query)
        if score > 0:
            scored_episodes.append((score, skeleton))

    scored_episodes.sort(key=lambda x: x[0], reverse=True)
    return [episode for _, episode in scored_episodes[:limit]]


def get_recent_episodes(limit: int = 10) -> list[dict[str, Any]]:
    """Return most recently modified episode skeletons."""
    if not MEMORY_DIR.exists():
        return []

    skeleton_files = sorted(
        MEMORY_DIR.glob("skeleton_*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    episodes: list[dict[str, Any]] = []
    for file_path in skeleton_files[:limit]:
        skeleton = _load_skeleton(file_path)
        if skeleton:
            episodes.append(skeleton)

    return episodes
