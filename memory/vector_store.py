"""
Vector Store for Arcturus Memory System (Project 11: Mnemo)

Provider-agnostic interface for vector storage. Switch backends (Qdrant, Weaviate, FAISS)
without changing application code.

Usage:

    # Application code: depend on the protocol, not a specific backend
    from memory.vector_store import get_vector_store, VectorStoreProtocol

    store: VectorStoreProtocol = get_vector_store(provider="qdrant")
    store.add(text="...", embedding=vec)
    results = store.search(query_vector=query_vec, k=5)

    # Or configure via env: VECTOR_STORE_PROVIDER=qdrant
"""

from typing import Dict, List, Any, Optional
import os

from memory.backends.base import VectorStoreProtocol

# Re-export protocol for type hints and dependency injection
__all__ = [
    "VectorStoreProtocol",
    "get_vector_store",
    "QdrantVectorStore",
]


def get_vector_store(
    provider: Optional[str] = None,
    **kwargs: Any,
) -> VectorStoreProtocol:
    """
    Factory for vector store backends. Switch providers without changing caller code.

    Args:
        provider: One of "qdrant", "faiss", "weaviate". Defaults to env VECTOR_STORE_PROVIDER or "faiss".
        **kwargs: Passed to the backend constructor (e.g. url, collection_name for Qdrant).

    Returns:
        VectorStoreProtocol implementation.

    Example:
        store = get_vector_store(provider="qdrant")  # url/api_key from config
        store = get_vector_store(provider="faiss", persistence_dir="memory/faiss_index")
    """
    p = provider or os.environ.get("VECTOR_STORE_PROVIDER", "faiss")
    p = p.lower()

    if p == "qdrant":
        from memory.backends.qdrant_store import QdrantVectorStore
        from memory.qdrant_config import get_default_collection
        # Use collection_name from kwargs or default from config
        if "collection_name" not in kwargs:
            kwargs["collection_name"] = get_default_collection()
        return QdrantVectorStore(**kwargs)
    if p == "faiss":
        from memory.backends.faiss_store import FaissVectorStore
        return FaissVectorStore(**kwargs)
    if p == "weaviate":
        raise NotImplementedError(
            "Weaviate backend not implemented. Use provider='qdrant' or 'faiss'."
        )
    raise ValueError(f"Unknown vector store provider: {provider}. Use 'qdrant', 'faiss', or 'weaviate'.")


# Concrete implementations for direct use if needed
from memory.backends.qdrant_store import QdrantVectorStore
