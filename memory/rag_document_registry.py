"""
RAG Document Registry — Qdrant-backed document-level index for O(1) listing.

One point per (user_id, space_id, doc). Used by GET /api/rag/documents when
RAG_DOCUMENT_SOURCE=qdrant.
"""

import hashlib
import os
from typing import Any, Dict, List, Optional

try:
    from qdrant_client import QdrantClient
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
    raise ImportError("qdrant-client required. Install: pip install qdrant-client")

from memory.qdrant_config import get_collection_config, get_qdrant_api_key, get_qdrant_url
from memory.space_constants import SPACE_ID_GLOBAL


def _doc_to_point_id(doc: str, user_id: str, space_id: str) -> int:
    """Deterministic point ID from doc+user+space."""
    key = f"{user_id}:{space_id}:{doc}"
    h = hashlib.md5(key.encode()).hexdigest()[:16]
    return int(h, 16)


def _ensure_registry_collection(client: QdrantClient, name: str, cfg: dict) -> None:
    """Create collection if not exists. Uses 1-dim dummy vector."""
    from qdrant_client.http import models as http_models

    collections = client.get_collections()
    if any(c.name == name for c in collections.collections):
        return

    dim = cfg.get("dimension", 1)
    dist = cfg.get("distance", "cosine")
    dist_map = {"cosine": Distance.COSINE, "euclidean": Distance.EUCLID, "dot": Distance.DOT}
    distance = dist_map.get((dist or "cosine").lower(), Distance.COSINE)

    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dim, distance=distance),
    )
    for field in ["doc", "space_id", "user_id"]:
        try:
            client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=http_models.KeywordIndexParams(type=http_models.KeywordIndexType.KEYWORD),
            )
        except Exception as e:
            if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                pass  # ignore
    is_tenant = cfg.get("is_tenant", False)
    if is_tenant:
        try:
            client.create_payload_index(
                collection_name=name,
                field_name="user_id",
                field_schema=http_models.KeywordIndexParams(
                    type=http_models.KeywordIndexType.KEYWORD,
                    is_tenant=True,
                ),
            )
        except Exception:
            pass


class RAGDocumentRegistry:
    """Document-level registry in Qdrant for fast listing."""

    DEFAULT_COLLECTION = "arcturus_rag_documents"

    def __init__(self, collection_name: Optional[str] = None):
        self.collection_name = collection_name or self.DEFAULT_COLLECTION
        cfg = get_collection_config(self.collection_name)
        self._is_tenant = cfg.get("is_tenant", False)
        self._dim = cfg.get("dimension", 1)
        self.url = get_qdrant_url()
        api_key = get_qdrant_api_key()
        self.client = QdrantClient(url=self.url, api_key=api_key, timeout=10.0)
        _ensure_registry_collection(self.client, self.collection_name, cfg)

    def upsert_doc(
        self,
        doc: str,
        user_id: str,
        space_id: str,
        chunk_count: int = 0,
        content_hash: Optional[str] = None,
        storage: str = "local",
    ) -> None:
        """Upsert a document entry."""
        sid = space_id or SPACE_ID_GLOBAL
        uid = user_id if self._is_tenant else ""
        pid = _doc_to_point_id(doc, uid, sid)
        payload = {
            "doc": doc,
            "user_id": uid,
            "space_id": sid,
            "chunk_count": chunk_count,
            "storage": storage,
        }
        if content_hash:
            payload["content_hash"] = content_hash

        # Dummy vector (Qdrant requires vectors)
        vec = [0.0] * self._dim
        self.client.upsert(
            collection_name=self.collection_name,
            points=[PointStruct(id=pid, vector=vec, payload=payload)],
        )

    def delete_doc(self, doc: str, user_id: Optional[str] = None) -> None:
        """Delete document entry."""
        conditions = [FieldCondition(key="doc", match=MatchValue(value=doc))]
        if self._is_tenant and user_id:
            conditions.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(filter=Filter(must=conditions)),
        )

    def list_documents(
        self,
        user_id: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List documents. Filter by user_id (tenant) and optionally space_id."""
        conditions = []
        if self._is_tenant and user_id:
            conditions.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
        if space_id is not None:
            conditions.append(FieldCondition(key="space_id", match=MatchValue(value=space_id)))

        scroll_filter = Filter(must=conditions) if conditions else None
        out = []
        offset = None
        while True:
            kwargs = {
                "collection_name": self.collection_name,
                "limit": 1000,
                "offset": offset,
                "with_payload": True,
                "with_vectors": False,
            }
            if scroll_filter:
                kwargs["scroll_filter"] = scroll_filter
            points, next_offset = self.client.scroll(**kwargs)
            for p in points:
                payload = getattr(p, "payload", {}) or {}
                out.append({
                    "doc": payload.get("doc", ""),
                    "space_id": payload.get("space_id", SPACE_ID_GLOBAL),
                    "chunk_count": payload.get("chunk_count", 0),
                    "content_hash": payload.get("content_hash"),
                    "storage": payload.get("storage", "local"),
                })
            if next_offset is None:
                break
            offset = next_offset
        return out


def get_rag_document_registry(collection_name: Optional[str] = None) -> Optional[RAGDocumentRegistry]:
    """Return registry when using Qdrant; None for FAISS."""
    provider = os.environ.get("RAG_VECTOR_STORE_PROVIDER", "faiss").lower()
    if provider != "qdrant":
        return None
    return RAGDocumentRegistry(collection_name=collection_name)
