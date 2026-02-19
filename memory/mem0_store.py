"""Factual/semantic memory store for user preferences and facts (stub compatible with mem0-style API)."""
from pathlib import Path
from typing import Any

from shared.state import PROJECT_ROOT


class MemoryStore:
    """
    Minimal factual memory store: search returns stored facts (e.g. from remme or JSON).
    Compatible with base_agent's expectation: .search(query, limit=3) -> list of dicts with 'memory' or 'content'.
    """

    def __init__(self, data_path: Path | None = None):
        self._path = data_path or (PROJECT_ROOT / "memory" / "factual_memory.json")
        self._memories: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                import json
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self._memories = raw if isinstance(raw, list) else raw.get("memories", [])
            except Exception:
                self._memories = []

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any] | str]:
        """
        Return facts that match the query (simple keyword match).
        Each item is a dict with 'memory' or 'content' key, or a string.
        """
        if not query or not self._memories:
            return []
        q = query.lower().split()
        scored: list[tuple[int, dict]] = []
        for m in self._memories:
            text = (m.get("memory") or m.get("content") or str(m)).lower()
            score = sum(1 for w in q if w in text)
            if score > 0:
                scored.append((score, m))
        scored.sort(key=lambda x: -x[0])
        return [m for _, m in scored[:limit]]
