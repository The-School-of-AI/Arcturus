"""
Abstract interface for vector store backends.

Implement this protocol to add new providers (Qdrant, Weaviate, FAISS, etc.)
without changing application code. All methods use provider-agnostic types.
"""

from typing import Protocol, Dict, List, Any, Optional, runtime_checkable
import numpy as np


@runtime_checkable
class VectorStoreProtocol(Protocol):
    """
    Standard interface for vector store backends.

    Use this protocol for type hints and dependency injection.
    Switch providers by passing a different implementation to consumers.
    """

    def add(
        self,
        text: str,
        embedding: np.ndarray,
        category: str = "general",
        source: str = "manual",
        metadata: Optional[Dict[str, Any]] = None,
        deduplication_threshold: float = 0.15,
    ) -> Dict[str, Any]:
        """
        Add a new memory.

        Returns:
            Memory dict with id, text, category, source, created_at, updated_at.
        """
        ...

    def search(
        self,
        query_vector: np.ndarray,
        query_text: Optional[str] = None,
        k: int = 10,
        score_threshold: Optional[float] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search memories by vector similarity.

        Returns:
            List of memory dicts with id, score, text, and metadata.
        """
        ...

    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a memory by ID. Returns None if not found."""
        ...

    def update(
        self,
        memory_id: str,
        text: Optional[str] = None,
        embedding: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update an existing memory. Returns True if successful."""
        ...

    def delete(self, memory_id: str) -> bool:
        """Delete a memory. Returns True if successful."""
        ...

    def get_all(
        self,
        limit: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return all memories, optionally filtered and limited."""
        ...

    def count(self) -> int:
        """Return total number of memories."""
        ...
