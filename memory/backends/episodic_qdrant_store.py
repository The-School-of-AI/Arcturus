"""
Phase B: Qdrant-backed episodic memory store.
Stores session skeleton recipes for semantic search and space-scoped retrieval.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as http_models
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
except ImportError:
    raise ImportError("qdrant-client is required. Install with: pip install qdrant-client")

from core.utils import log_step, log_error

from memory.qdrant_config import get_collection_config, get_qdrant_url, get_qdrant_api_key
from memory.space_constants import SPACE_ID_GLOBAL
from memory.user_id import get_user_id


EPISODIC_COLLECTION = "arcturus_episodic"


def _distance_from_str(s: str):
    m = {"cosine": Distance.COSINE, "euclidean": Distance.EUCLID, "dot": Distance.DOT}
    return m.get((s or "cosine").lower(), Distance.COSINE)


class EpisodicQdrantStore:
    """
    Qdrant-backed episodic store for session skeletons.
    Tenant-scoped by user_id; filterable by space_id.
    """

    def __init__(self):
        cfg = get_collection_config(EPISODIC_COLLECTION)
        self.collection_name = EPISODIC_COLLECTION
        self.dimension = cfg.get("dimension", 768)
        self._distance = _distance_from_str(cfg.get("distance", "cosine"))
        self._is_tenant = cfg.get("is_tenant", True)
        self._tenant_keyword_field = cfg.get("tenant_keyword_field", "user_id")
        url = get_qdrant_url()
        api_key = get_qdrant_api_key()
        self.client = QdrantClient(url=url, api_key=api_key, timeout=10.0)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections()
        names = [c.name for c in collections.collections]
        if self.collection_name not in names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.dimension, distance=self._distance),
            )
            log_step(f"📦 Created episodic collection: {self.collection_name}", symbol="✨")
        cfg = get_collection_config(self.collection_name)
        if cfg.get("is_tenant") and cfg.get("tenant_keyword_field"):
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=self._tenant_keyword_field,
                    field_schema=http_models.KeywordIndexParams(
                        type=http_models.KeywordIndexType.KEYWORD,
                        is_tenant=True,
                    ),
                )
                log_step(f"🔑 Episodic tenant index on {self._tenant_keyword_field}", symbol="✨")
            except Exception as e:
                if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                    log_error(f"Episodic tenant index failed: {e}")
        for field in cfg.get("indexed_payload_fields", []):
            if field == self._tenant_keyword_field:
                continue
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=http_models.KeywordIndexParams(type=http_models.KeywordIndexType.KEYWORD),
                )
            except Exception as e:
                if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                    log_error(f"Episodic index for {field} failed: {e}")

    def upsert(
        self,
        session_id: str,
        searchable_text: str,
        embedding: np.ndarray,
        skeleton_json: str,
        original_query: str,
        outcome: str = "completed",
        user_id: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> str:
        """Upsert an episode (idempotent by session_id)."""
        user_id = user_id or get_user_id()
        space_id = space_id or SPACE_ID_GLOBAL
        point_id = str(session_id)
        now = datetime.now().isoformat()
        vec = embedding.tolist() if isinstance(embedding, np.ndarray) else list(embedding)
        payload = {
            "user_id": user_id,
            "space_id": space_id,
            "session_id": session_id,
            "original_query": original_query,
            "outcome": outcome,
            "skeleton_json": skeleton_json,
            "created_at": now,
            "updated_at": now,
        }
        point = PointStruct(id=point_id, vector=vec, payload=payload)
        self.client.upsert(collection_name=self.collection_name, points=[point])
        log_step(f"💾 Episodic saved: {session_id[:12]}...", symbol="🧠")
        return point_id

    def sync_upsert(
        self,
        session_id: str,
        skeleton_json: str,
        original_query: str,
        outcome: str,
        user_id: str,
        space_id: str,
        embedding: np.ndarray,
        updated_at: Optional[str] = None,
    ) -> bool:
        """Apply synced episode (from pull). Caller provides embedding."""
        try:
            import json
            sk = json.loads(skeleton_json) if isinstance(skeleton_json, str) else skeleton_json
            searchable = original_query
            for n in sk.get("nodes", []):
                tg = n.get("task_goal") or n.get("description")
                if tg:
                    searchable += "\n" + str(tg)[:300]
                inst = n.get("instruction")
                if inst:
                    searchable += "\n" + str(inst)[:300]
            if not searchable.strip():
                searchable = original_query
            vec = embedding.tolist() if isinstance(embedding, np.ndarray) else list(embedding)
            now = updated_at or datetime.now().isoformat()
            payload = {
                "user_id": user_id,
                "space_id": space_id or SPACE_ID_GLOBAL,
                "session_id": session_id,
                "original_query": original_query,
                "outcome": outcome or "completed",
                "skeleton_json": skeleton_json,
                "created_at": now,
                "updated_at": now,
            }
            point = PointStruct(id=str(session_id), vector=vec, payload=payload)
            self.client.upsert(collection_name=self.collection_name, points=[point])
            return True
        except Exception as e:
            log_error(f"Episodic sync_upsert failed: {e}")
            return False

    def delete(self, session_id: str) -> bool:
        """Delete episode by session_id."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[str(session_id)],
            )
            return True
        except Exception as e:
            log_error(f"Episodic delete failed: {e}")
            return False

    def search(
        self,
        query_vector: np.ndarray,
        limit: int = 10,
        user_id: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Vector search with optional user_id and space_id filters."""
        user_id = user_id or get_user_id()
        conditions = []
        if self._is_tenant and user_id:
            conditions.append(FieldCondition(key=self._tenant_keyword_field, match=MatchValue(value=user_id)))
        if space_id is not None:
            conditions.append(FieldCondition(key="space_id", match=MatchValue(value=space_id)))
        search_filter = Filter(must=conditions) if conditions else None
        vec = query_vector.tolist() if isinstance(query_vector, np.ndarray) else list(query_vector)
        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=vec,
                limit=limit,
                query_filter=search_filter,
            )
            out = []
            for r in (results.result if hasattr(results, "result") else results):
                if hasattr(r, "id") and hasattr(r, "score") and hasattr(r, "payload"):
                    sk = r.payload.get("skeleton_json", "{}")
                    try:
                        import json
                        skeleton = json.loads(sk)
                    except Exception:
                        skeleton = {}
                    out.append({"id": str(r.id), "score": 1.0 - r.score, **r.payload, "nodes": skeleton.get("nodes", [])})
                elif isinstance(r, dict):
                    out.append(r)
            return out
        except Exception as e:
            log_error(f"Episodic search failed: {e}")
            return []

    def get_recent(
        self,
        limit: int = 10,
        user_id: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return recent episodes by scroll. Filters by user_id and optional space_id."""
        user_id = user_id or get_user_id()
        conditions = []
        if self._is_tenant and user_id:
            conditions.append(FieldCondition(key=self._tenant_keyword_field, match=MatchValue(value=user_id)))
        if space_id is not None:
            conditions.append(FieldCondition(key="space_id", match=MatchValue(value=space_id)))
        scroll_filter = Filter(must=conditions) if conditions else None
        try:
            points, _ = self.client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                scroll_filter=scroll_filter,
                with_payload=True,
                with_vectors=False,
            )
            out = []
            for p in points:
                sk = p.payload.get("skeleton_json", "{}")
                try:
                    import json
                    skeleton = json.loads(sk)
                except Exception:
                    skeleton = {}
                out.append({"id": str(p.id), **p.payload, "nodes": skeleton.get("nodes", [])})
            out.sort(key=lambda x: x.get("updated_at", x.get("created_at", "")), reverse=True)
            return out[:limit]
        except Exception as e:
            log_error(f"Episodic get_recent failed: {e}")
            return []

    def get_all(
        self,
        limit: Optional[int] = 10000,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return all episodes for sync. Scopes by user_id."""
        user_id = user_id or get_user_id()
        conditions = []
        if self._is_tenant and user_id:
            conditions.append(FieldCondition(key=self._tenant_keyword_field, match=MatchValue(value=user_id)))
        scroll_filter = Filter(must=conditions) if conditions else None
        try:
            out = []
            offset = None
            while True:
                points, next_offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=1000,
                    offset=offset,
                    scroll_filter=scroll_filter,
                    with_payload=True,
                    with_vectors=False,
                )
                for p in points:
                    out.append({"id": str(p.id), **p.payload})
                if next_offset is None or (limit and len(out) >= limit):
                    break
                offset = next_offset
            return out[:limit] if limit else out
        except Exception as e:
            log_error(f"Episodic get_all failed: {e}")
            return []
