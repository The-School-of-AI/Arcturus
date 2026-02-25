"""
Vector store backends for Arcturus memory system.

Implement VectorStoreProtocol to add a new provider (Qdrant, Weaviate, FAISS, etc.).
"""

from memory.backends.base import VectorStoreProtocol
from memory.backends.qdrant_store import QdrantVectorStore
from memory.backends.faiss_store import FaissVectorStore

__all__ = [
    "VectorStoreProtocol",
    "QdrantVectorStore",
    "FaissVectorStore",
]
