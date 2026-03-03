"""
RAG Vector Store — Provider-agnostic storage for RAG document chunks.

Uses arcturus_rag_chunks collection in Qdrant, or falls back to local FAISS.
Switch via RAG_VECTOR_STORE_PROVIDER=qdrant|faiss (default: faiss for backward compatibility).

Metadata (doc, chunk, chunk_id, page) is kept in metadata.json for BM25 indexing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class RAGVectorStoreProtocol(Protocol):
    """Interface for RAG chunk storage (vectors). Metadata is kept in metadata.json by caller."""

    def add_chunks(
        self,
        entries: List[Dict[str, Any]],
        embeddings: List[np.ndarray],
        remove_doc: Optional[str] = None,
    ) -> None:
        """Add chunks to vector store. If remove_doc set, delete existing for that doc first."""
        ...

    def search(self, query_vector: np.ndarray, k: int) -> List[tuple[str, float]]:
        """Vector similarity search. Returns [(chunk_id, score), ...]. Higher score = more similar."""
        ...

    def delete_by_doc(self, doc_path: str) -> int:
        """Remove all chunks for a document. Returns count removed."""
        ...


def get_rag_vector_store(
    provider: Optional[str] = None,
    index_dir: Optional[Path] = None,
    **kwargs: Any,
) -> RAGVectorStoreProtocol:
    """
    Factory for RAG vector store. Default: faiss (backward compatible).

    Args:
        provider: "qdrant" or "faiss". Default: env RAG_VECTOR_STORE_PROVIDER or "faiss".
        index_dir: Directory for FAISS index/metadata (default: mcp_servers/faiss_index).
        **kwargs: Passed to backend (e.g. collection_name for Qdrant).
    """
    p = provider or os.environ.get("RAG_VECTOR_STORE_PROVIDER", "faiss")
    p = p.lower()

    if p == "qdrant":
        from memory.rag_backends.qdrant_rag_store import QdrantRAGStore
        return QdrantRAGStore(**kwargs)
    if p == "faiss":
        from memory.rag_backends.faiss_rag_store import FaissRAGStore
        idx = index_dir or Path(__file__).parent.parent / "mcp_servers" / "faiss_index"
        return FaissRAGStore(index_dir=idx)
    raise ValueError(f"Unknown RAG provider: {p}. Use 'qdrant' or 'faiss'.")
