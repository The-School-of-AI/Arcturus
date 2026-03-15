"""
search/cache.py
In-memory semantic cache using FAISS (already in pyproject.toml).
No Redis required. Reuses existing get_embedding() from remme.utils.
"""
import asyncio
import pickle
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

# Module-level state — lives for the lifetime of the API process.
_cache_entries: list[dict] = []     # [{query, result, timestamp}, ...]
_embeddings: list[np.ndarray] = []  # parallel list of embeddings


def _get_index():
    """Build a flat FAISS index from the current embeddings list."""
    try:
        import faiss
    except ImportError:
        return None

    if not _embeddings:
        return None

    dim = _embeddings[0].shape[0]
    index = faiss.IndexFlatIP(dim)  # inner-product on L2-normalised vecs = cosine
    matrix = np.stack(_embeddings).astype("float32")
    index.add(matrix)
    return index


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def get_or_none(query: str, threshold: float = 0.92) -> Optional[dict]:
    """Return a cached SynthesisResult dict if *query* is semantically close enough.

    This is synchronous because get_embedding() uses blocking requests.
    Returns None on miss.
    """
    if not _cache_entries:
        return None

    index = _get_index()
    if index is None:
        return None

    from remme.utils import get_embedding
    vec = _normalize(get_embedding(query, task_type="search_query")).reshape(1, -1)

    distances, indices = index.search(vec, 1)
    if distances[0][0] >= threshold:
        entry = _cache_entries[indices[0][0]]
        return entry["result"]

    return None


def put(query: str, result) -> None:
    """Store a synthesis result keyed by the query's embedding."""
    from remme.utils import get_embedding
    vec = _normalize(get_embedding(query, task_type="search_document"))

    _cache_entries.append({
        "query": query,
        "result": result,
        "timestamp": time.time(),
    })
    _embeddings.append(vec)


def clear() -> None:
    """Reset the cache."""
    _cache_entries.clear()
    _embeddings.clear()


def size() -> int:
    """Number of entries in the cache."""
    return len(_cache_entries)
