"""
Phase C: Client-side sparse embeddings via FastEmbed (SPLADE).

Used for hybrid search in RAG (arcturus_rag_chunks) and memories (arcturus_memories).
"""

from __future__ import annotations

from typing import Any, List, Optional

# Default SPLADE model (Apache licensed, commercial use)
DEFAULT_SPARSE_MODEL = "prithivida/Splade_PP_en_v1"

_model: Any = None


def _get_sparse_model(model_name: str = DEFAULT_SPARSE_MODEL):
    """Lazy-load FastEmbed SparseTextEmbedding model."""
    global _model
    if _model is None:
        try:
            from fastembed import SparseTextEmbedding
            _model = SparseTextEmbedding(model_name=model_name)
        except ImportError as e:
            raise ImportError(
                "fastembed is required for Phase C hybrid search. Install with: pip install fastembed"
            ) from e
    return _model


def embed_sparse(
    texts: List[str],
    model_name: str = DEFAULT_SPARSE_MODEL,
    batch_size: int = 32,
) -> List[tuple[list[int], list[float]]]:
    """
    Generate sparse embeddings for texts using FastEmbed SPLADE.

    Returns:
        List of (indices, values) tuples, one per input text.
        Each indices/values pair is suitable for qdrant_client.models.SparseVector.
    """
    if not texts:
        return []
    model = _get_sparse_model(model_name)
    embeddings = list(model.embed(texts, batch_size=batch_size))
    out = []
    for emb in embeddings:
        indices = emb.indices.tolist() if hasattr(emb.indices, "tolist") else list(emb.indices)
        values = emb.values.tolist() if hasattr(emb.values, "tolist") else list(emb.values)
        out.append((indices, values))
    return out


def embed_sparse_single(text: str, model_name: str = DEFAULT_SPARSE_MODEL) -> tuple[list[int], list[float]]:
    """Generate sparse embedding for a single text."""
    results = embed_sparse([text], model_name=model_name)
    return results[0] if results else ([], [])
