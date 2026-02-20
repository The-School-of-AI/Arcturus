"""
FAISS-backed implementation of VectorStoreProtocol.

Wraps RemmeStore to provide the standard interface. Use for local-only,
file-based storage when Qdrant is not available.
"""

from typing import Dict, List, Any, Optional
import numpy as np

from remme.store import RemmeStore

from memory.backends.base import VectorStoreProtocol


def _l2_to_similarity(distance: float) -> float:
    """Convert L2 distance (lower=better) to similarity-like score (higher=better)."""
    return 1.0 / (1.0 + max(0, distance))


class FaissVectorStore:
    """
    FAISS-backed vector store. Implements VectorStoreProtocol.
    Wraps RemmeStore for backward compatibility.
    """

    def __init__(self, persistence_dir: str = "memory/remme_index", **kwargs: Any):
        self._store = RemmeStore(persistence_dir=persistence_dir)

    def add(
        self,
        text: str,
        embedding: np.ndarray,
        category: str = "general",
        source: str = "manual",
        metadata: Optional[Dict[str, Any]] = None,
        deduplication_threshold: float = 0.15,
    ) -> Dict[str, Any]:
        # RemmeStore uses 0.15 internally; metadata is not stored
        result = self._store.add(text=text, embedding=embedding, category=category, source=source)
        if metadata:
            result.update(metadata)
        return result

    def search(
        self,
        query_vector: np.ndarray,
        query_text: Optional[str] = None,
        k: int = 10,
        score_threshold: Optional[float] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        # RemmeStore uses L2 distance threshold (lower=better); convert our similarity threshold
        l2_threshold = 1.5
        if score_threshold is not None:
            # similarity 0.85 -> rough L2 ~0.18
            l2_threshold = (1.0 - score_threshold) * 2.0 if score_threshold < 1 else 0.1

        results = self._store.search(
            query_vector=query_vector,
            query_text=query_text,
            k=k,
            score_threshold=l2_threshold,
        )
        # Convert L2 distance to similarity-like score
        for r in results:
            if "score" in r:
                r["score"] = _l2_to_similarity(r["score"])
        if filter_metadata:
            results = [r for r in results if all(r.get(k) == v for k, v in filter_metadata.items())]
        return results[:k]

    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        for m in self._store.memories:
            if m.get("id") == memory_id:
                return m.copy()
        return None

    def update(
        self,
        memory_id: str,
        text: Optional[str] = None,
        embedding: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if text is None and embedding is None and not metadata:
            return False
        existing = self.get(memory_id)
        if not existing:
            return False
        new_text = text if text is not None else existing.get("text", "")
        new_emb = embedding if embedding is not None else None
        if new_emb is None:
            return False
        return self._store.update_text(memory_id, new_text, new_emb)

    def delete(self, memory_id: str) -> bool:
        return bool(self._store.delete(memory_id))

    def get_all(
        self,
        limit: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        results = self._store.get_all()
        if filter_metadata:
            results = [r for r in results if all(r.get(k) == v for k, v in filter_metadata.items())]
        return results[:limit] if limit else results

    def count(self) -> int:
        return len(self._store.memories)

    def get_scanned_run_ids(self) -> set:
        return self._store.get_scanned_run_ids()

    def mark_run_scanned(self, run_id: str) -> None:
        self._store.mark_run_scanned(run_id)
