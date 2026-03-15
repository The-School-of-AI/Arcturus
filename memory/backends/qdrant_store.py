"""
Qdrant-backed implementation of VectorStoreProtocol.

Phase C: Sparse vectors (text-bm25) for hybrid search via FastEmbed SPLADE.
"""

import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _utc_iso_now() -> str:
    """Return current UTC time as ISO8601 string with Z suffix (sync merge compatibility)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
from typing import Dict, List, Any, Optional, Set
import numpy as np
import pdb

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as http_models
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        Fusion,
        FusionQuery,
        IsEmptyCondition,
        MatchAny,
        MatchValue,
        Modifier,
        PointStruct,
        Prefetch,
        SparseVector,
        SparseVectorParams,
        VectorParams,
    )
    from qdrant_client.http.models import PayloadField
except ImportError:
    raise ImportError(
        "qdrant-client is required for Qdrant backend. Install with: pip install qdrant-client"
    )

from core.utils import log_step, log_error

from memory.backends.base import VectorStoreProtocol
from memory.qdrant_config import get_collection_config, get_default_collection, get_qdrant_url, get_qdrant_api_key
from memory.space_constants import SPACE_ID_GLOBAL, VISIBILITY_PRIVATE
from memory.user_id import get_user_id
from memory.lifecycle import initialize_payload


def _distance_from_str(s: str):
    m = {"cosine": Distance.COSINE, "euclidean": Distance.EUCLID, "dot": Distance.DOT}
    return m.get((s or "cosine").lower(), Distance.COSINE)


class QdrantVectorStore:
    """
    Qdrant-backed vector store. Implements VectorStoreProtocol.
    Collection config (dimension, distance, etc.) is loaded from config/qdrant_config.yaml.
    """

    def __init__(
        self,
        collection_name: Optional[str] = None,
        dimension: Optional[int] = None,
        scanned_runs_path: Optional[Path] = None,
    ):
        self.collection_name = collection_name or get_default_collection()
        cfg = get_collection_config(self.collection_name)
        self.dimension = dimension if dimension is not None else cfg.get("dimension", 768)
        self._distance = _distance_from_str(cfg.get("distance", "cosine"))
        self._is_tenant = cfg.get("is_tenant", False)
        self._tenant_keyword_field = cfg.get("tenant_keyword_field", "user_id")
        self._sparse_config = cfg.get("sparse_vectors", {}).get("text-bm25")
        self.url = get_qdrant_url()
        api_key = get_qdrant_api_key()
        self.client = QdrantClient(url=self.url, api_key=api_key, timeout=10.0)
        self._scanned_runs_path = Path(scanned_runs_path) if scanned_runs_path else Path(__file__).parent.parent.parent / "memory" / "remme_index" / "scanned_runs.json"
        self._ensure_collection()
        self._has_sparse = self._check_has_sparse()
        log_step(f"✅ QdrantVectorStore initialized: {self.url}/{self.collection_name}", symbol="🔧")

    def _check_has_sparse(self) -> bool:
        """Check if collection has sparse vectors (Phase C)."""
        try:
            info = self.client.get_collection(self.collection_name)
            sparse = getattr(info.config, "params", None) and getattr(
                info.config.params, "sparse_vectors", None
            )
            return bool(sparse and "text-bm25" in sparse)
        except Exception:
            return False

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections()
        collection_names = [c.name for c in collections.collections]
        created = False
        if self.collection_name not in collection_names:
            sparse_config = None
            if self._sparse_config and isinstance(self._sparse_config, dict):
                sparse_config = {"text-bm25": SparseVectorParams(modifier=Modifier.IDF)}
            vec_config = VectorParams(size=self.dimension, distance=self._distance)
            kwargs = dict(
                collection_name=self.collection_name,
                vectors_config={"default": vec_config} if sparse_config else vec_config,
            )
            if sparse_config:
                kwargs["sparse_vectors_config"] = sparse_config
            self.client.create_collection(**kwargs)
            log_step(f"📦 Created collection: {self.collection_name}", symbol="✨")
            created = True
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
                log_step(f"🔑 Created tenant index on {self._tenant_keyword_field}", symbol="✨")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    pass
                else:
                    log_error(f"Failed to create tenant payload index: {e}")

        # Create keyword indexes for filter fields (required for Qdrant Cloud filtered search)
        cfg = get_collection_config(self.collection_name)
        indexed_fields = cfg.get("indexed_payload_fields", [])
        for field in indexed_fields:
            if field == self._tenant_keyword_field:
                continue
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=http_models.KeywordIndexParams(
                        type=http_models.KeywordIndexType.KEYWORD,
                    ),
                )
                log_step(f"🔑 Created payload index on {field}", symbol="✨")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    pass
                else:
                    log_error(f"Failed to create payload index for {field}: {e}")

    def _ingest_to_knowledge_graph(self, memory_id: str, text: str, payload: Dict[str, Any]) -> None:
        """Extract entities (and facts when Mnemo), write to Neo4j, update Qdrant payload with entity_ids."""
        # pdb.set_trace()
        try:
            from memory.knowledge_graph import get_knowledge_graph
            from memory.mnemo_config import is_mnemo_enabled

            kg = get_knowledge_graph()
            if not kg or not kg.enabled:
                return
            user_id = payload.get(self._tenant_keyword_field) or (get_user_id() if self._is_tenant else None)
            if not user_id:
                return
            session_id = payload.get("session_id") or "unknown"
            if is_mnemo_enabled():
                from shared.state import get_unified_extractor
                unified = get_unified_extractor()
                extraction = unified.extract_from_memory_text(text)
                print(f"[QdrantVectorStore] Extracted entities {extraction} from the text {text}") 
                legacy = extraction.to_legacy_entity_result()
                entities = legacy.get("entities")
                entity_relationships = legacy.get("entity_relationships")
                user_facts = legacy.get("user_facts")
                facts = list(extraction.facts) if extraction.facts else None
                evidence_events = list(extraction.evidence_events) if extraction.evidence_events else None
            else:
                from memory.entity_extractor import EntityExtractor
                extractor = EntityExtractor()
                extracted = extractor.extract(text)
                entities = extracted.get("entities")
                entity_relationships = extracted.get("entity_relationships")
                user_facts = extracted.get("user_facts")
                facts = None
                evidence_events = None
            space_id_val = payload.get("space_id")
            if space_id_val == SPACE_ID_GLOBAL:
                space_id_val = None
            result = kg.ingest_memory(
                memory_id=memory_id,
                text=text,
                user_id=user_id,
                session_id=session_id,
                category=payload.get("category", "general"),
                source=payload.get("source", "manual"),
                space_id=space_id_val,
                entities=entities,
                entity_relationships=entity_relationships,
                user_facts=user_facts,
                facts=facts,
                evidence_events=evidence_events,
            )
            entity_ids = result.get("entity_ids", result if isinstance(result, list) else [])
            entity_labels = result.get("entity_labels", []) if isinstance(result, dict) else []
            if entity_ids or entity_labels:
                meta = {"entity_ids": entity_ids}
                if entity_labels:
                    meta["entity_labels"] = entity_labels
                self.update(memory_id, metadata=meta)
        except Exception as e:
            log_error(f"Knowledge graph ingestion failed: {e}")

    def _tenant_filter(self, filter_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Merge tenant user_id into filter metadata."""
        current_user_id = get_user_id() if self._is_tenant else None
        base: Dict[str, Any] = {self._tenant_keyword_field: current_user_id} if self._is_tenant and current_user_id else {}
        if filter_metadata:
            base.update(filter_metadata)
        return base

    def add(
        self,
        text: str,
        embedding: np.ndarray,
        category: str = "general",
        source: str = "manual",
        metadata: Optional[Dict[str, Any]] = None,
        deduplication_threshold: float = 0.15,
        session_id: Optional[str] = None,
        skip_kg_ingest: bool = False,
        space_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else list(embedding)
        if deduplication_threshold > 0:
            min_similarity = 1.0 - deduplication_threshold  # e.g. 0.85 for threshold 0.15
            similar = self.search(
                query_vector=np.array(embedding_list),
                query_text=None,  # dense-only for dedup; no space filter to match any user memory
                k=1,
                score_threshold=min_similarity,
                filter_metadata=self._tenant_filter() if self._is_tenant else None,
            )
            # Only treat as duplicate if the returned score (similarity) actually meets threshold.
            # Qdrant may return results that don't meet score_threshold; enforce in code.
            if similar and (similar[0].get("score") or 0) >= min_similarity:
                memory_id = similar[0]["id"]
                self._update_timestamp(memory_id, source)
                return similar[0]

        memory_id = str(uuid.uuid4())
        now_ts = _utc_iso_now()
        payload = {
            "text": text,
            "category": category,
            "source": source,
            "created_at": now_ts,
            "updated_at": now_ts,
            "version": 1,
            "deleted": False,
        }
        try:
            from memory.sync_config import get_device_id
            payload["device_id"] = get_device_id()
        except Exception:
            payload["device_id"] = ""
        current_user_id = get_user_id() if self._is_tenant else None
        if self._is_tenant and current_user_id:
            payload[self._tenant_keyword_field] = current_user_id
        if session_id:
            payload["session_id"] = session_id
        elif metadata and metadata.get("session_id"):
            payload["session_id"] = metadata["session_id"]
        elif source and source.startswith("run_"):
            payload["session_id"] = source.replace("run_", "")
        if metadata:
            payload.update(metadata)
        payload["space_id"] = space_id or (metadata or {}).get("space_id") or SPACE_ID_GLOBAL
        # Default visibility is private to the owning user unless explicitly overridden.
        if "visibility" not in payload:
            payload["visibility"] = VISIBILITY_PRIVATE

        # Initialize lifecycle-related fields (importance, access_count, archived, last_accessed_at).
        initialize_payload(payload)

        # Phase C: include sparse vector when collection has text-bm25
        if self._has_sparse and text:
            try:
                from memory.sparse_embedding import embed_sparse_single
                idx, vals = embed_sparse_single(text)
                vec_data = {"default": embedding_list, "text-bm25": SparseVector(indices=idx, values=vals)}
            except Exception:
                vec_data = embedding_list
        else:
            vec_data = embedding_list
        point = PointStruct(id=memory_id, vector=vec_data, payload=payload)
        t0 = time.perf_counter()
        self.client.upsert(collection_name=self.collection_name, points=[point])
        upsert_ms = (time.perf_counter() - t0) * 1000
        log_step(f"💾 Added memory: {memory_id[:8]}... ({len(text)} chars)", symbol="📝")

        # Neo4j knowledge graph ingestion (if enabled). Skip when add comes from session pipeline;
        # session extraction is ingested via ingest_from_unified_extraction (entities from full context).
        # When ASYNC_KG_INGEST=true: return after upsert, run KG in background for faster add latency.
        kg_ms = 0.0
        if not skip_kg_ingest:
            try:
                from memory.mnemo_config import is_async_kg_ingest_enabled
                if is_async_kg_ingest_enabled():
                    # Fire-and-forget; memory is searchable immediately; KG lags slightly
                    payload_copy = dict(payload)
                    thread = threading.Thread(
                        target=self._ingest_to_knowledge_graph,
                        args=(memory_id, text, payload_copy),
                        daemon=True,
                        name="kg-ingest",
                    )
                    thread.start()
                else:
                    t1 = time.perf_counter()
                    self._ingest_to_knowledge_graph(memory_id, text, payload)
                    kg_ms = (time.perf_counter() - t1) * 1000
            except ImportError:
                self._ingest_to_knowledge_graph(memory_id, text, payload)
        total_ms = (time.perf_counter() - t0) * 1000
        log_step(
            f"⏱ realtime_index: upsert={upsert_ms:.1f}ms | kg={kg_ms:.1f}ms | total={total_ms:.1f}ms",
            symbol="⏱",
        )

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
        merged_filter = self._tenant_filter(filter_metadata)
        search_filter = None
        if merged_filter:
            conditions = []
            for key, value in merged_filter.items():
                if key == "space_ids" and isinstance(value, list):
                    conditions.append(
                        FieldCondition(key="space_id", match=MatchAny(any=value))
                    )
                else:
                    conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
            if conditions:
                search_filter = Filter(must=conditions)

        distance_threshold = 1.0 - score_threshold if score_threshold is not None else None

        try:
            if self._has_sparse and query_text and query_text.strip():
                # Phase C: hybrid prefetch (dense + sparse) + RRF fusion
                try:
                    from memory.sparse_embedding import embed_sparse_single
                    idx, vals = embed_sparse_single(query_text)
                    sparse_query = SparseVector(indices=idx, values=vals)
                    prefetches = [
                        Prefetch(query=query_vector, using="default", limit=k * 2),
                        Prefetch(query=sparse_query, using="text-bm25", limit=k * 2),
                    ]
                    search_results = self.client.query_points(
                        collection_name=self.collection_name,
                        prefetch=prefetches,
                        query=FusionQuery(fusion=Fusion.RRF),
                        limit=k * 2,
                        with_payload=True,
                        query_filter=search_filter,
                    )
                except Exception:
                    search_results = self._do_vector_search(query_vector, k * 2, distance_threshold, search_filter)
            else:
                search_results = self._do_vector_search(query_vector, k * 2 if query_text else k, distance_threshold, search_filter)

            if hasattr(search_results, "result"):
                search_results = search_results.result
            elif hasattr(search_results, "points"):
                search_results = search_results.points

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

            if query_text and not (self._has_sparse and query_text.strip()):
                results = self._apply_keyword_boosting(results, query_text, k)
            return results[:k]
        except Exception as e:
            log_error(f"Failed to search Qdrant: {e}")
            return []

    def _do_vector_search(
        self,
        query_vector: list,
        limit: int,
        score_threshold: Optional[float],
        search_filter: Optional[Filter],
    ):
        kwargs = dict(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
            query_filter=search_filter,
        )
        if score_threshold is not None:
            kwargs["score_threshold"] = score_threshold
        if self._has_sparse:
            kwargs["using"] = "default"
        return self.client.query_points(**kwargs)

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
                payload = dict(p.payload)
                current_user_id = get_user_id() if self._is_tenant else None
                if self._is_tenant and current_user_id:
                    if payload.get(self._tenant_keyword_field) != current_user_id:
                        return None
                return {"id": str(p.id), **payload}
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
            updated["updated_at"] = _utc_iso_now()
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

    def sync_upsert(
        self,
        memory_id: str,
        text: str,
        embedding: np.ndarray,
        payload: Dict[str, Any],
    ) -> bool:
        """
        Phase 4 Sync: upsert memory with explicit id (for applying pulled changes).
        Skips KG ingest (caller handles separately if needed).
        """
        try:
            vec = embedding.tolist() if isinstance(embedding, np.ndarray) else list(embedding)
            merged = dict(payload)
            merged["text"] = text
            if "version" not in merged:
                merged["version"] = 1
            if "updated_at" not in merged:
                merged["updated_at"] = _utc_iso_now()
            if "deleted" not in merged:
                merged["deleted"] = False
            current_user_id = get_user_id() if self._is_tenant else None
            if self._is_tenant and current_user_id and "user_id" not in merged:
                merged[self._tenant_keyword_field] = current_user_id
            point = PointStruct(id=memory_id, vector=vec, payload=merged)
            self.client.upsert(collection_name=self.collection_name, points=[point])
            return True
        except Exception as e:
            log_error(f"Sync upsert failed for {memory_id[:8]}: {e}")
            return False

    def delete(self, memory_id: str) -> bool:
        if self._is_tenant and self.get(memory_id) is None:
            return False
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[memory_id],
            )
            log_step(f"🗑️ Deleted memory: {memory_id[:8]}...", symbol="❌")
            # Keep knowledge graph in sync: remove Memory node and its relationships
            try:
                from memory.knowledge_graph import get_knowledge_graph
                kg = get_knowledge_graph()
                if kg and kg.enabled:
                    kg.delete_memory(memory_id)
            except Exception as e:
                log_error(f"Knowledge graph delete_memory failed: {e}")
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
            merged_filter = self._tenant_filter(filter_metadata)
            search_filter = None
            if merged_filter:
                must_conditions: List[Any] = []
                for key, value in merged_filter.items():
                    # Global space: include points with space_id=="__global__" OR missing/empty space_id (legacy).
                    if key == "space_id" and value == SPACE_ID_GLOBAL:
                        must_conditions.append(
                            Filter(
                                should=[
                                    FieldCondition(key="space_id", match=MatchValue(value=SPACE_ID_GLOBAL)),
                                    IsEmptyCondition(is_empty=PayloadField(key="space_id")),
                                ]
                            )
                        )
                    else:
                        must_conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
                if must_conditions:
                    search_filter = Filter(must=must_conditions)
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
            current_user_id = get_user_id() if self._is_tenant else None
            if self._is_tenant and current_user_id:
                results = self.get_all(limit=2**31 - 1)
                return len(results)
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
        existing = self.get(memory_id)  # already tenant-scoped
        if existing:
            updated = existing.copy()
            updated.pop("id", None)
            updated["updated_at"] = _utc_iso_now()
            src = updated.get("source", "")
            if source not in src:
                updated["source"] = f"{src}, {source}"
            vec = self._get_vector_for_point(memory_id)
            if vec:
                point = PointStruct(id=memory_id, vector=vec, payload=updated)
                self.client.upsert(collection_name=self.collection_name, points=[point])
