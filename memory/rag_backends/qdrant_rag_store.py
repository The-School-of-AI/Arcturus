"""
Qdrant-backed RAG vector store. Uses arcturus_rag_chunks collection.

Phase A: Tenant-scoped by user_id; space-scoped via space_id in payload.
Phase C: Sparse vectors (chunk-bm25) for hybrid search via FastEmbed SPLADE.
"""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as http_models
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        FilterSelector,
        Fusion,
        FusionQuery,
        MatchValue,
        Modifier,
        PointStruct,
        Prefetch,
        SparseVector,
        SparseVectorParams,
        VectorParams,
    )
except ImportError:
    raise ImportError("qdrant-client is required for RAG Qdrant backend. Install with: pip install qdrant-client")

from memory.qdrant_config import get_collection_config, get_qdrant_api_key, get_qdrant_url
from memory.space_constants import SPACE_ID_GLOBAL


def _distance_from_str(s: str):
    m = {"cosine": Distance.COSINE, "euclidean": Distance.EUCLID, "dot": Distance.DOT}
    return m.get((s or "cosine").lower(), Distance.COSINE)


def _chunk_id_to_point_id(chunk_id: str) -> int:
    """Convert chunk_id to Qdrant point ID (64-bit unsigned int)."""
    h = hashlib.md5(chunk_id.encode()).hexdigest()[:16]
    return int(h, 16)


class QdrantRAGStore:
    """Qdrant-backed RAG chunk store. Uses arcturus_rag_chunks collection. Phase A: tenant + space scoped. Phase C: hybrid search with sparse vectors."""

    COLLECTION = "arcturus_rag_chunks"
    SPARSE_VECTOR_NAME = "chunk-bm25"

    def __init__(self, collection_name: str | None = None):
        self.collection_name = collection_name or self.COLLECTION
        cfg = get_collection_config(self.collection_name)
        self.dimension = cfg.get("dimension", 768)
        self._distance = _distance_from_str(cfg.get("distance", "cosine"))
        self._is_tenant = cfg.get("is_tenant", False)
        self._tenant_keyword_field = cfg.get("tenant_keyword_field", "user_id")
        self._sparse_config = cfg.get("sparse_vectors", {}).get(self.SPARSE_VECTOR_NAME)
        self.url = get_qdrant_url()
        api_key = get_qdrant_api_key()
        self.client = QdrantClient(url=self.url, api_key=api_key, timeout=10.0)
        self._ensure_collection()
        self._has_sparse = self._check_has_sparse()

    def _check_has_sparse(self) -> bool:
        """Check if collection has sparse vectors (e.g. created with Phase C config)."""
        try:
            info = self.client.get_collection(self.collection_name)
            sparse = getattr(info.config, "params", None) and getattr(
                info.config.params, "sparse_vectors", None
            )
            if sparse and self.SPARSE_VECTOR_NAME in sparse:
                return True
            return False
        except Exception:
            return False

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections()
        names = [c.name for c in collections.collections]
        if self.collection_name not in names:
            sparse_config = None
            if self._sparse_config and isinstance(self._sparse_config, dict):
                mod = Modifier.IDF if self._sparse_config.get("modifier") == "idf" else None
                sparse_config = {self.SPARSE_VECTOR_NAME: SparseVectorParams(modifier=mod or Modifier.IDF)}
            # Use named "default" for dense so we can combine with sparse in points
            vec_config = VectorParams(size=self.dimension, distance=self._distance)
            kwargs = dict(
                collection_name=self.collection_name,
                vectors_config={"default": vec_config} if sparse_config else vec_config,
            )
            if sparse_config:
                kwargs["sparse_vectors_config"] = sparse_config
            self.client.create_collection(**kwargs)
        # Create payload index on "doc" for delete_by_doc filter
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="doc",
                field_schema=http_models.KeywordIndexParams(type=http_models.KeywordIndexType.KEYWORD),
            )
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                pass
            else:
                # Fallback for older qdrant_client
                try:
                    self.client.create_payload_index(
                        collection_name=self.collection_name,
                        field_name="doc",
                        field_schema=http_models.KeywordIndexParams(type=http_models.KeywordIndexType.KEYWORD),
                    )
                except Exception:
                    pass
        # Phase A: tenant index for user_id
        if self._is_tenant and self._tenant_keyword_field:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=self._tenant_keyword_field,
                    field_schema=http_models.KeywordIndexParams(
                        type=http_models.KeywordIndexType.KEYWORD,
                        is_tenant=True,
                    ),
                )
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    pass
                else:
                    try:
                        self.client.create_payload_index(
                            collection_name=self.collection_name,
                            field_name=self._tenant_keyword_field,
                            field_schema=http_models.KeywordIndexParams(type=http_models.KeywordIndexType.KEYWORD, is_tenant=True),
                        )
                    except Exception:
                        pass

    def add_chunks(
        self,
        entries: List[Dict[str, Any]],
        embeddings: List[np.ndarray],
        remove_doc: str | None = None,
        user_id: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> None:
        """Add chunks to Qdrant. If remove_doc is set, delete existing points for that doc first.
        Phase A: user_id and space_id for tenant/space scope. Phase C: sparse vectors for hybrid search."""
        if not entries or not embeddings or len(entries) != len(embeddings):
            return
        if remove_doc is not None:
            self.delete_by_doc(doc_path=remove_doc, user_id=user_id)

        uid = user_id if (self._is_tenant and user_id) else (user_id or "")
        sid = (space_id or SPACE_ID_GLOBAL) if space_id is not None else SPACE_ID_GLOBAL

        # Phase C: generate sparse embeddings when collection has sparse vectors
        sparse_list: List[tuple[list[int], list[float]]] = []
        if self._has_sparse:
            try:
                from memory.sparse_embedding import embed_sparse
                texts = [ent.get("chunk", "") or "" for ent in entries]
                sparse_list = embed_sparse(texts)
            except Exception:
                sparse_list = []

        points = []
        for i, (ent, emb) in enumerate(zip(entries, embeddings)):
            chunk_id = ent.get("chunk_id", "")
            if not chunk_id:
                continue
            payload = {
                "doc": ent.get("doc", ""),
                "chunk": ent.get("chunk", ""),
                "chunk_id": chunk_id,
                "page": ent.get("page", 1),
            }
            if self._is_tenant and uid:
                payload[self._tenant_keyword_field] = uid
            payload["space_id"] = sid
            if ent.get("doc_type"):
                payload["doc_type"] = ent["doc_type"]
            if ent.get("session_id"):
                payload["session_id"] = ent["session_id"]
            vec = emb.tolist() if isinstance(emb, np.ndarray) else list(emb)
            if self._has_sparse and i < len(sparse_list):
                idx, vals = sparse_list[i]
                points.append(
                    PointStruct(
                        id=_chunk_id_to_point_id(chunk_id),
                        vector={"default": vec, self.SPARSE_VECTOR_NAME: SparseVector(indices=idx, values=vals)},
                        payload=payload,
                    )
                )
            else:
                points.append(PointStruct(id=_chunk_id_to_point_id(chunk_id), vector=vec, payload=payload))
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)

    def search(
        self,
        query_vector: np.ndarray,
        k: int,
        user_id: Optional[str] = None,
        space_id: Optional[str] = None,
        query_text: Optional[str] = None,
    ) -> List[tuple[str, float]]:
        """Vector or hybrid search. Returns [(chunk_id, score), ...]. Phase C: when query_text and _has_sparse, use prefetch hybrid + RRF."""
        search_filter = self._build_search_filter(user_id, space_id)

        if self._has_sparse and query_text and query_text.strip():
            # Phase C: hybrid search (prefetch dense + sparse, RRF fusion)
            try:
                from memory.sparse_embedding import embed_sparse_single

                idx, vals = embed_sparse_single(query_text)
                sparse_query = SparseVector(indices=idx, values=vals)
                vec = query_vector.tolist() if isinstance(query_vector, np.ndarray) else list(query_vector)
                # Prefetch: dense on "default", sparse on chunk-bm25
                prefetches = [
                    Prefetch(query=vec, using="default", limit=k * 2),
                    Prefetch(query=sparse_query, using=self.SPARSE_VECTOR_NAME, limit=k * 2),
                ]
                results = self.client.query_points(
                    collection_name=self.collection_name,
                    prefetch=prefetches,
                    query=FusionQuery(fusion=Fusion.RRF),
                    limit=k,
                    with_payload=True,
                    query_filter=search_filter,
                )
            except Exception:
                results = self._search_vector_only(query_vector, k, search_filter)
        else:
            results = self._search_vector_only(query_vector, k, search_filter)

        out = []
        points = results.points if hasattr(results, "points") else results
        for r in points:
            pid = getattr(r, "id", None)
            score = getattr(r, "score", None) or 0.0
            payload = getattr(r, "payload", {}) or {}
            chunk_id = payload.get("chunk_id", str(pid)) if payload else str(pid)
            out.append((chunk_id, float(score)))
        return out

    def _build_search_filter(
        self, user_id: Optional[str], space_id: Optional[str]
    ) -> Optional[Filter]:
        conditions = []
        if self._is_tenant and user_id:
            conditions.append(FieldCondition(key=self._tenant_keyword_field, match=MatchValue(value=user_id)))
            if space_id is not None:
                conditions.append(FieldCondition(key="space_id", match=MatchValue(value=space_id)))
        return Filter(must=conditions) if conditions else None

    def _search_vector_only(
        self,
        query_vector: np.ndarray,
        k: int,
        search_filter: Optional[Filter],
    ):
        vec = query_vector.tolist() if isinstance(query_vector, np.ndarray) else list(query_vector)
        kwargs = dict(
            collection_name=self.collection_name,
            query=vec,
            limit=k,
            with_payload=True,
            query_filter=search_filter,
        )
        if self._has_sparse:
            kwargs["using"] = "default"
        return self.client.query_points(**kwargs)

    def get_metadata(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Scroll points and return metadata for BM25. Phase A: filter by user_id when tenant."""
        out = []
        offset = None
        scroll_filter = None
        if self._is_tenant and user_id:
            scroll_filter = Filter(must=[FieldCondition(key=self._tenant_keyword_field, match=MatchValue(value=user_id))])
        while True:
            kwargs = dict(
                collection_name=self.collection_name,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            if scroll_filter:
                kwargs["scroll_filter"] = scroll_filter
            points, next_offset = self.client.scroll(**kwargs)
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

    def delete_by_doc(self, doc_path: str, user_id: Optional[str] = None) -> int:
        """Delete points where doc=doc_path. Phase A: scope by user_id when tenant."""
        conditions = [FieldCondition(key="doc", match=MatchValue(value=doc_path))]
        if self._is_tenant and user_id:
            conditions.append(FieldCondition(key=self._tenant_keyword_field, match=MatchValue(value=user_id)))
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(filter=Filter(must=conditions)),
        )
        return 1
