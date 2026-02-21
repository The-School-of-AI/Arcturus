"""
Qdrant-backed implementation of VectorStoreProtocol.
"""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import numpy as np

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        VectorParams,
        PointStruct,
        Filter,
        FieldCondition,
        MatchValue,
    )
except ImportError:
    raise ImportError(
        "qdrant-client is required for Qdrant backend. Install with: pip install qdrant-client"
    )

from core.utils import log_step, log_error

from memory.backends.base import VectorStoreProtocol


class QdrantVectorStore:
    """
    Qdrant-backed vector store. Implements VectorStoreProtocol.
    """

    DEFAULT_COLLECTION = "arcturus_memories"
    DEFAULT_DIMENSION = 768

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection_name: str = DEFAULT_COLLECTION,
        dimension: int = DEFAULT_DIMENSION,
        api_key: Optional[str] = None,
        scanned_runs_path: Optional[Path] = None,
    ):
        self.url = url
        self.collection_name = collection_name
        self.dimension = dimension
        self.client = QdrantClient(url=url, api_key=api_key, timeout=10.0)
        self._scanned_runs_path = Path(scanned_runs_path) if scanned_runs_path else Path(__file__).parent.parent.parent / "memory" / "remme_index" / "scanned_runs.json"
        self._ensure_collection()
        log_step(f"✅ QdrantVectorStore initialized: {url}/{collection_name}", symbol="🔧")

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections()
        if self.collection_name not in [c.name for c in collections.collections]:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
            )
            log_step(f"📦 Created collection: {self.collection_name}", symbol="✨")

    def add(
        self,
        text: str,
        embedding: np.ndarray,
        category: str = "general",
        source: str = "manual",
        metadata: Optional[Dict[str, Any]] = None,
        deduplication_threshold: float = 0.15,
    ) -> Dict[str, Any]:
        embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else list(embedding)
        if deduplication_threshold > 0:
            similar = self.search(
                query_vector=np.array(embedding_list),
                k=1,
                score_threshold=1.0 - deduplication_threshold,
            )
            if similar:
                memory_id = similar[0]["id"]
                self._update_timestamp(memory_id, source)
                return similar[0]

        memory_id = str(uuid.uuid4())
        payload = {
            "text": text,
            "category": category,
            "source": source,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        if metadata:
            payload.update(metadata)

        point = PointStruct(id=memory_id, vector=embedding_list, payload=payload)
        self.client.upsert(collection_name=self.collection_name, points=[point])
        log_step(f"💾 Added memory: {memory_id[:8]}... ({len(text)} chars)", symbol="📝")
        return {"id": memory_id, **payload}

    def search(
        self,
        query_vector: np.ndarray,
        query_text: Optional[str] = None,
        k: int = 10,
        score_threshold: Optional[float] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        query_vector = query_vector.tolist() if isinstance(query_vector, np.ndarray) else list(query_vector)
        search_filter = None
        if filter_metadata:
            conditions = [
                FieldCondition(key=key, match=MatchValue(value=value))
                for key, value in filter_metadata.items()
            ]
            if conditions:
                search_filter = Filter(must=conditions)

        distance_threshold = None
        if score_threshold is not None:
            distance_threshold = 1.0 - score_threshold

        try:
            # if hasattr(self.client, "search"):
            #     search_results = self.client.search(
            #         collection_name=self.collection_name,
            #         query_vector=query_vector,
            #         limit=k * 2 if query_text else k,
            #         score_threshold=distance_threshold,
            #         query_filter=search_filter,
            #     )
            # else:
            #     from qdrant_client.http import models as rest_models
            #     search_request = rest_models.SearchRequest(
            #         vector=query_vector,
            #         limit=k * 2 if query_text else k,
            #         score_threshold=distance_threshold,
            #         filter=search_filter,
            #     )
            #     response = self.client.http.collections_api.query_points(
            #         collection_name=self.collection_name,
            #         search_request=search_request,
            #     )
            #     search_results = response.result
            search_results = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vector,
                    limit=k * 2 if query_text else k,
                    score_threshold=distance_threshold,
                    query_filter=search_filter,
                )

            if hasattr(search_results, "result"):
                search_results = search_results.result

            results = []
            for result in search_results:
                if hasattr(result, "id") and hasattr(result, "score") and hasattr(result, "payload"):
                    memory = {"id": str(result.id), "score": 1.0 - result.score, **result.payload}
                    results.append(memory)
                elif isinstance(result, dict):
                    results.append(result)
                else:
                    rid = getattr(result, "id", None) or getattr(result, "point_id", None)
                    rscore = getattr(result, "score", None) or getattr(result, "distance", None)
                    rpayload = getattr(result, "payload", {}) or {}
                    if rid is not None:
                        results.append({"id": str(rid), "score": 1.0 - (rscore or 0), **rpayload})

            if query_text:
                results = self._apply_keyword_boosting(results, query_text, k)
            return results[:k]
        except Exception as e:
            log_error(f"Failed to search Qdrant: {e}")
            return []

    def _apply_keyword_boosting(
        self, results: List[Dict], query_text: str, k: int
    ) -> List[Dict]:
        query_words = set(re.findall(r"\b\w+\b", query_text.lower()))
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "do", "does", "did",
            "you", "your", "have", "has", "had", "any", "about", "of", "our",
            "to", "what", "we", "in", "with", "from", "for", "and", "or", "but",
            "so", "how", "when", "where", "why", "this", "that", "these", "those",
        }
        keywords = query_words - stop_words
        if not keywords:
            return results[:k]
        boosted = {}
        for r in results:
            text_lower = r.get("text", "").lower()
            match_count = sum(1 for kw in keywords if re.search(rf"\b{re.escape(kw)}\b", text_lower))
            if match_count > 0:
                r = r.copy()
                r["score"] = min(1.0, r.get("score", 0) * (1.0 + match_count * 0.7))
                r["source"] = f"{r.get('source', '')} (hybrid_boost)"
            boosted[r["id"]] = r
        return sorted(boosted.values(), key=lambda x: x.get("score", 0), reverse=True)[:k]

    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        try:
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id],
            )
            if result:
                p = result[0]
                return {"id": str(p.id), **p.payload}
            return None
        except Exception as e:
            log_error(f"Failed to get memory {memory_id}: {e}")
            return None

    def update(
        self,
        memory_id: str,
        text: Optional[str] = None,
        embedding: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            existing = self.get(memory_id)
            if not existing:
                return False
            updated = existing.copy()
            updated.pop("id", None)
            updated["updated_at"] = datetime.now().isoformat()
            if text:
                updated["text"] = text
            if metadata:
                updated.update(metadata)
            vec = embedding.tolist() if embedding is not None else self._get_vector_for_point(memory_id)
            if vec is None:
                return False
            point = PointStruct(id=memory_id, vector=vec, payload=updated)
            self.client.upsert(collection_name=self.collection_name, points=[point])
            log_step(f"✏️ Updated memory: {memory_id[:8]}...", symbol="🔄")
            return True
        except Exception as e:
            log_error(f"Failed to update memory {memory_id}: {e}")
            return False

    def _get_vector_for_point(self, memory_id: str) -> Optional[List[float]]:
        """Retrieve existing vector when updating payload only. Qdrant requires vector on upsert."""
        try:
            pts = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id],
                with_vectors=True,
            )
            if pts and hasattr(pts[0], "vector"):
                v = pts[0].vector
                return v if isinstance(v, list) else v.tolist()
        except Exception:
            pass
        return None

    def delete(self, memory_id: str) -> bool:
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[memory_id],
            )
            log_step(f"🗑️ Deleted memory: {memory_id[:8]}...", symbol="❌")
            return True
        except Exception as e:
            log_error(f"Failed to delete memory {memory_id}: {e}")
            return False

    def get_all(
        self,
        limit: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        try:
            search_filter = None
            if filter_metadata:
                conditions = [
                    FieldCondition(key=key, match=MatchValue(value=value))
                    for key, value in filter_metadata.items()
                ]
                if conditions:
                    search_filter = Filter(must=conditions)
            results = []
            offset = None
            while True:
                points, next_offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=1000,
                    offset=offset,
                    scroll_filter=search_filter,
                )
                for p in points:
                    results.append({"id": str(p.id), **p.payload})
                if next_offset is None or (limit and len(results) >= limit):
                    break
                offset = next_offset
            return results[:limit] if limit else results
        except Exception as e:
            log_error(f"Failed to get all memories: {e}")
            return []

    def count(self) -> int:
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count
        except Exception as e:
            log_error(f"Failed to get collection count: {e}")
            return 0

    def get_scanned_run_ids(self) -> Set[str]:
        """Return run IDs already scanned (stored in sidecar JSON)."""
        if not self._scanned_runs_path.exists():
            return set()
        try:
            data = json.loads(self._scanned_runs_path.read_text())
            return set(data) if isinstance(data, list) else set(data.get("ids", []))
        except Exception:
            return set()

    def mark_run_scanned(self, run_id: str) -> None:
        """Persist scanned run ID to sidecar JSON."""
        ids = self.get_scanned_run_ids()
        if run_id not in ids:
            ids.add(run_id)
            self._scanned_runs_path.parent.mkdir(parents=True, exist_ok=True)
            self._scanned_runs_path.write_text(json.dumps(list(ids), indent=2))

    def _update_timestamp(self, memory_id: str, source: str) -> None:
        existing = self.get(memory_id)
        if existing:
            updated = existing.copy()
            updated.pop("id", None)
            updated["updated_at"] = datetime.now().isoformat()
            src = updated.get("source", "")
            if source not in src:
                updated["source"] = f"{src}, {source}"
            vec = self._get_vector_for_point(memory_id)
            if vec:
                point = PointStruct(id=memory_id, vector=vec, payload=updated)
                self.client.upsert(collection_name=self.collection_name, points=[point])
