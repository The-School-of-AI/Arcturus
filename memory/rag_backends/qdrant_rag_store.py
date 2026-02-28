"""
Qdrant-backed RAG vector store. Uses arcturus_rag_chunks collection.
"""

import hashlib
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as http_models
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        FilterSelector,
        MatchValue,
        PointStruct,
        VectorParams,
    )
except ImportError:
    raise ImportError("qdrant-client is required for RAG Qdrant backend. Install with: pip install qdrant-client")

from memory.qdrant_config import get_collection_config, get_qdrant_api_key, get_qdrant_url


def _distance_from_str(s: str):
    m = {"cosine": Distance.COSINE, "euclidean": Distance.EUCLID, "dot": Distance.DOT}
    return m.get((s or "cosine").lower(), Distance.COSINE)


def _chunk_id_to_point_id(chunk_id: str) -> int:
    """Convert chunk_id to Qdrant point ID (64-bit unsigned int)."""
    h = hashlib.md5(chunk_id.encode()).hexdigest()[:16]
    return int(h, 16)


class QdrantRAGStore:
    """Qdrant-backed RAG chunk store. Uses arcturus_rag_chunks collection."""

    COLLECTION = "arcturus_rag_chunks"

    def __init__(self, collection_name: str | None = None):
        self.collection_name = collection_name or self.COLLECTION
        cfg = get_collection_config(self.collection_name)
        self.dimension = cfg.get("dimension", 768)
        self._distance = _distance_from_str(cfg.get("distance", "cosine"))
        self.url = get_qdrant_url()
        api_key = get_qdrant_api_key()
        self.client = QdrantClient(url=self.url, api_key=api_key, timeout=10.0)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections()
        names = [c.name for c in collections.collections]
        if self.collection_name not in names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.dimension, distance=self._distance),
            )
        # Create payload index on "doc" for delete_by_doc filter
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="doc",
                field_schema=http_models.KeywordIndexParams(type=http_models.KeywordIndexType.KEYWORD),
            )
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                pass  # Index already exists

    def add_chunks(
        self,
        entries: List[Dict[str, Any]],
        embeddings: List[np.ndarray],
        remove_doc: str | None = None,
    ) -> None:
        """Add chunks to Qdrant. If remove_doc is set, delete existing points for that doc first."""
        if not entries or not embeddings or len(entries) != len(embeddings):
            return
        if remove_doc is not None:
            self.delete_by_doc(doc_path=remove_doc)

        points = []
        for ent, emb in zip(entries, embeddings):
            chunk_id = ent.get("chunk_id", "")
            if not chunk_id:
                continue
            payload = {
                "doc": ent.get("doc", ""),
                "chunk": ent.get("chunk", ""),
                "chunk_id": chunk_id,
                "page": ent.get("page", 1),
            }
            vec = emb.tolist() if isinstance(emb, np.ndarray) else list(emb)
            point_id = _chunk_id_to_point_id(chunk_id)
            points.append(PointStruct(id=point_id, vector=vec, payload=payload))
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)

    def search(
        self,
        query_vector: np.ndarray,
        k: int,
    ) -> List[tuple[str, float]]:
        """Vector search. Returns [(chunk_id, score), ...]. Score is similarity (higher = better)."""
        vec = query_vector.tolist() if isinstance(query_vector, np.ndarray) else list(query_vector)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vec,
            limit=k,
            with_payload=True,
        )
        out = []
        for r in (results.points if hasattr(results, "points") else results):
            pid = getattr(r, "id", None)
            score = getattr(r, "score", None) or 0.0
            payload = getattr(r, "payload", {}) or {}
            chunk_id = payload.get("chunk_id", str(pid)) if payload else str(pid)
            out.append((chunk_id, float(score)))
        return out

    def get_metadata(self) -> List[Dict[str, Any]]:
        """Scroll all points and return metadata for BM25. May be slow for large collections."""
        out = []
        offset = None
        while True:
            points, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for p in points:
                payload = getattr(p, "payload", {}) or {}
                out.append({
                    "chunk_id": payload.get("chunk_id", str(p.id)),
                    "doc": payload.get("doc", ""),
                    "chunk": payload.get("chunk", ""),
                    "page": payload.get("page", 1),
                })
            if next_offset is None:
                break
            offset = next_offset
        return out

    def delete_by_doc(self, doc_path: str) -> int:
        """Delete all points where doc=doc_path. Returns count deleted."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key="doc", match=MatchValue(value=doc_path))])
            ),
        )
        return 1
