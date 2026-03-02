"""
Neo4j Knowledge Graph — Stores extracted entities and relationships from Remme memories.

Ties to Qdrant via memory_id (Qdrant point id) and entity_ids (Neo4j entity ids in Qdrant payload).
Schema: User, Memory, Session, Entity nodes; HAS_MEMORY, FROM_SESSION, CONTAINS_ENTITY,
RELATED_TO, LIVES_IN, WORKS_AT, KNOWS, PREFERS relationships.

Enable via NEO4J_ENABLED=true and NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from core.utils import log_error, log_step

# Optional Neo4j dependency
try:
    from neo4j import GraphDatabase
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False
    GraphDatabase = None


def _is_neo4j_enabled() -> bool:
    """Check if Neo4j integration is enabled via env."""
    return os.environ.get("NEO4J_ENABLED", "").lower() in ("true", "1", "yes")


def _get_neo4j_config() -> Dict[str, str]:
    """Get Neo4j connection config from env."""
    return {
        "uri": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        "user": os.environ.get("NEO4J_USER", "neo4j"),
        "password": os.environ.get("NEO4J_PASSWORD", ""),
    }


class KnowledgeGraph:
    """
    Neo4j-backed knowledge graph for Remme memories.
    Creates User, Memory, Session, Entity nodes and relationships.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self._driver = None
        cfg = _get_neo4j_config()
        self.uri = uri or cfg["uri"]
        self.user = user or cfg["user"]
        self.password = password or cfg["password"]
        self._enabled = _is_neo4j_enabled() and _NEO4J_AVAILABLE
        if self._enabled and self.password:
            try:
                self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
                self._driver.verify_connectivity()
                self._ensure_schema()
                log_step("✅ KnowledgeGraph (Neo4j) initialized", symbol="🔧")
            except Exception as e:
                log_error(f"Neo4j connection failed: {e}")
                self._enabled = False
        elif self._enabled and not self.password:
            log_error("NEO4J_PASSWORD required when NEO4J_ENABLED=true")
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None

    def _ensure_schema(self) -> None:
        """Create constraints and indexes if they don't exist."""
        with self._driver.session() as session:
            # Unique constraints for idempotent upserts
            for q in [
                "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
                "CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE",
                "CREATE CONSTRAINT session_id IF NOT EXISTS FOR (s:Session) REQUIRE s.session_id IS UNIQUE",
                "CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.composite_key IS UNIQUE",
            ]:
                try:
                    session.run(q)
                except Exception:
                    pass  # constraint may already exist
            session.run(
                "CREATE INDEX entity_name_type IF NOT EXISTS FOR (e:Entity) ON (e.name, e.type)"
            )

    def _run_query(self, query: str, parameters: Optional[Dict] = None) -> List[Dict]:
        """Execute a read query and return records as list of dicts."""
        if not self._enabled or not self._driver:
            return []
        try:
            with self._driver.session() as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
        except Exception as e:
            log_error(f"Neo4j query failed: {e}")
            return []

    def _run_write(self, query: str, parameters: Optional[Dict] = None) -> None:
        """Execute a write query."""
        if not self._enabled or not self._driver:
            return
        try:
            with self._driver.session() as session:
                session.run(query, parameters or {})
        except Exception as e:
            log_error(f"Neo4j write failed: {e}")

    def get_or_create_user(self, user_id: str) -> str:
        """Get or create User node. Returns Neo4j internal id (we use user_id as identifier)."""
        self._run_write(
            """
            MERGE (u:User {user_id: $user_id})
            ON CREATE SET u.id = $user_id, u.created_at = datetime()
            RETURN u.user_id
            """,
            {"user_id": user_id},
        )
        return user_id

    def get_or_create_session(
        self,
        session_id: str,
        original_query: Optional[str] = None,
    ) -> str:
        """Get or create Session node."""
        self._run_write(
            """
            MERGE (s:Session {session_id: $session_id})
            ON CREATE SET
                s.id = $session_id,
                s.original_query = $original_query,
                s.created_at = datetime()
            ON MATCH SET
                s.original_query = COALESCE($original_query, s.original_query)
            """,
            {
                "session_id": session_id,
                "original_query": original_query or "",
            },
        )
        return session_id

    def create_memory(
        self,
        memory_id: str,
        user_id: str,
        session_id: str,
        category: str = "general",
        source: str = "manual",
    ) -> None:
        """Create Memory node and link to User and Session."""
        self.get_or_create_user(user_id)
        self.get_or_create_session(session_id)
        self._run_write(
            """
            MERGE (m:Memory {id: $mid})
            ON CREATE SET
                m.category = $category,
                m.source = $source,
                m.created_at = datetime()
            ON MATCH SET
                m.category = $category,
                m.source = $source
            WITH m
            MATCH (u:User {user_id: $user_id})
            MERGE (u)-[:HAS_MEMORY]->(m)
            WITH m
            MATCH (s:Session {session_id: $session_id})
            MERGE (m)-[:FROM_SESSION]->(s)
            """,
            {
                "mid": memory_id,
                "user_id": user_id,
                "session_id": session_id,
                "category": category,
                "source": source,
            },
        )

    def get_or_create_entity(self, entity_type: str, name: str) -> str:
        """Get or create Entity node. Returns entity id (uuid). Deduplicates by composite_key."""
        composite_key = f"{entity_type}::{name}"
        entity_id = str(uuid.uuid4())
        records = self._run_query(
            """
            MERGE (e:Entity {composite_key: $composite_key})
            ON CREATE SET e.id = $entity_id, e.type = $entity_type, e.name = $name, e.created_at = datetime()
            ON MATCH SET e.type = $entity_type, e.name = $name
            RETURN e.id AS id
            """,
            {
                "composite_key": composite_key,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "name": name,
            },
        )
        if records and records[0].get("id"):
            return str(records[0]["id"])
        return entity_id

    def link_memory_to_entity(self, memory_id: str, entity_id: str) -> None:
        """Create CONTAINS_ENTITY relationship."""
        self._run_write(
            """
            MATCH (m:Memory {id: $memory_id}), (e:Entity {id: $entity_id})
            MERGE (m)-[:CONTAINS_ENTITY]->(e)
            """,
            {"memory_id": memory_id, "entity_id": entity_id},
        )

    def create_entity_relationship(
        self,
        from_entity_id: str,
        to_entity_id: str,
        rel_type: str = "related_to",
        value: Optional[str] = None,
        confidence: float = 1.0,
        source_memory_ids: Optional[List[str]] = None,
    ) -> None:
        """Create RELATED_TO relationship between entities."""
        self._run_write(
            """
            MATCH (a:Entity {id: $from_id}), (b:Entity {id: $to_id})
            MERGE (a)-[r:RELATED_TO]->(b)
            SET r.type = $rel_type,
                r.value = $value,
                r.confidence = $confidence,
                r.source_memory_ids = $source_memory_ids
            """,
            {
                "from_id": from_entity_id,
                "to_id": to_entity_id,
                "rel_type": rel_type,
                "value": value or "",
                "confidence": confidence,
                "source_memory_ids": source_memory_ids or [],
            },
        )

    def create_user_entity_relationship(
        self,
        user_id: str,
        entity_id: str,
        rel_type: str,  # LIVES_IN, WORKS_AT, KNOWS, PREFERS
        source_memory_ids: Optional[List[str]] = None,
    ) -> None:
        """Create user-centric relationship: User -[:rel_type]-> Entity."""
        if rel_type not in ("LIVES_IN", "WORKS_AT", "KNOWS", "PREFERS"):
            log_error(f"Invalid user-entity rel type: {rel_type}")
            return
        self._run_write(
            f"""
            MATCH (u:User {{user_id: $user_id}}), (e:Entity {{id: $entity_id}})
            MERGE (u)-[r:{rel_type}]->(e)
            SET r.source_memory_ids = $source_memory_ids
            """,
            {
                "user_id": user_id,
                "entity_id": entity_id,
                "source_memory_ids": source_memory_ids or [],
            },
        )

    def ingest_memory(
        self,
        memory_id: str,
        text: str,
        user_id: str,
        session_id: str,
        category: str = "general",
        source: str = "manual",
        entities: Optional[List[Dict[str, Any]]] = None,
        entity_relationships: Optional[List[Dict[str, Any]]] = None,
        user_facts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Full ingestion: create Memory, extract/link entities, relationships, user facts.
        Returns dict with entity_ids (for Neo4j link) and entity_labels (type, name for Qdrant payload).
        """
        empty_result: Dict[str, Any] = {"entity_ids": [], "entity_labels": []}
        if not self._enabled:
            return empty_result
        self.create_memory(memory_id, user_id, session_id, category, source)
        entity_ids: List[str] = []
        entity_labels: List[Dict[str, str]] = []  # [{type, name}] same order as entity_ids
        entity_map: Dict[str, str] = {}  # (type, name) -> entity_id

        # Create entities and link to memory
        for ent in entities or []:
            etype = ent.get("type", "Concept")
            name = ent.get("name", "").strip()
            if not name:
                continue
            key = (etype, name)
            if key not in entity_map:
                entity_map[key] = self.get_or_create_entity(etype, name)
            eid = entity_map[key]
            entity_ids.append(eid)
            entity_labels.append({"type": etype, "name": name})
            self.link_memory_to_entity(memory_id, eid)

        # Entity-entity relationships
        for rel in entity_relationships or []:
            from_key = (rel.get("from_type", "Entity"), rel.get("from_name", ""))
            to_key = (rel.get("to_type", "Entity"), rel.get("to_name", ""))
            from_id = entity_map.get(from_key)
            to_id = entity_map.get(to_key)
            if from_id and to_id:
                self.create_entity_relationship(
                    from_id,
                    to_id,
                    rel_type=rel.get("type", "related_to"),
                    value=rel.get("value"),
                    confidence=rel.get("confidence", 1.0),
                    source_memory_ids=[memory_id],
                )

        # User-centric facts
        for fact in user_facts or []:
            rel_type = fact.get("rel_type", "KNOWS")
            name = fact.get("name", "").strip()
            etype = fact.get("type", "Concept")
            if not name:
                continue
            key = (etype, name)
            if key not in entity_map:
                entity_map[key] = self.get_or_create_entity(etype, name)
            self.create_user_entity_relationship(
                user_id,
                entity_map[key],
                rel_type,
                source_memory_ids=[memory_id],
            )

        # Dedupe entity_ids while preserving order; keep corresponding labels (first occurrence)
        seen: Set[str] = set()
        deduped_ids: List[str] = []
        deduped_labels: List[Dict[str, str]] = []
        for eid, label in zip(entity_ids, entity_labels):
            if eid not in seen:
                seen.add(eid)
                deduped_ids.append(eid)
                deduped_labels.append(label)
        return {"entity_ids": deduped_ids, "entity_labels": deduped_labels}

    def get_entities_for_memory(self, memory_id: str) -> List[Dict[str, Any]]:
        """Get entities linked to a memory."""
        records = self._run_query(
            """
            MATCH (m:Memory {id: $memory_id})-[:CONTAINS_ENTITY]->(e:Entity)
            RETURN e.id AS id, e.type AS type, e.name AS name
            """,
            {"memory_id": memory_id},
        )
        return records

    def delete_memory(self, memory_id: str) -> None:
        """
        Remove the Memory node and all its relationships from the graph.
        Called when a memory is deleted from Qdrant so the knowledge graph stays in sync.
        Entity nodes are left in place (they may be referenced by other memories).
        """
        if not self._enabled or not memory_id:
            return
        self._run_write(
            """
            MATCH (m:Memory {id: $memory_id})
            DETACH DELETE m
            """,
            {"memory_id": memory_id},
        )

    def expand_from_entities(
        self,
        entity_ids: List[str],
        user_id: Optional[str] = None,
        depth: int = 2,
    ) -> Dict[str, Any]:
        """
        Traverse graph from given entity ids. Returns related entities, memories, user context.
        Used for retrieval: Qdrant returns memory_ids → Neo4j expands with graph context.
        """
        if not self._enabled or not entity_ids:
            return {"entities": [], "memories": [], "user_facts": []}
        # Simplified: get entities and their RELATED_TO neighbors
        placeholders = ", ".join([f"$id{i}" for i in range(len(entity_ids))])
        params = {f"id{i}": eid for i, eid in enumerate(entity_ids)}
        params["user_id"] = user_id or ""
        query = f"""
            MATCH (e:Entity)
            WHERE e.id IN [{placeholders}]
            OPTIONAL MATCH (e)-[:RELATED_TO]-(other:Entity)
            OPTIONAL MATCH (m:Memory)-[:CONTAINS_ENTITY]->(e)
            WITH e, collect(DISTINCT other) AS related, collect(DISTINCT m) AS mems
            RETURN e.id AS id, e.type AS type, e.name AS name,
                   [x IN related WHERE x IS NOT NULL | {{id: x.id, type: x.type, name: x.name}}] AS related_entities,
                   [m IN mems WHERE m IS NOT NULL | m.id] AS memory_ids
            """
        records = self._run_query(query, params)
        entities = []
        memory_ids = set()
        for r in records:
            entities.append({
                "id": r.get("id"),
                "type": r.get("type"),
                "name": r.get("name"),
                "related": r.get("related_entities", []),
            })
            memory_ids.update(r.get("memory_ids") or [])
        user_facts = []
        if user_id:
            uf = self._run_query(
                """
                MATCH (u:User {user_id: $user_id})-[r:LIVES_IN|WORKS_AT|KNOWS|PREFERS]->(e:Entity)
                RETURN type(r) AS rel_type, e.id AS entity_id, e.name AS name, e.type AS type
                """,
                {"user_id": user_id},
            )
            user_facts = uf
        return {
            "entities": entities,
            "memory_ids": list(memory_ids),
            "user_facts": user_facts,
        }

    def get_entities_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all entities in the user's graph (from their memories)."""
        if not self._enabled or not user_id:
            return []
        records = self._run_query(
            """
            MATCH (u:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory)-[:CONTAINS_ENTITY]->(e:Entity)
            RETURN DISTINCT e.id AS id, e.type AS type, e.name AS name
            """,
            {"user_id": user_id},
        )
        return records

    def resolve_entity_candidates(
        self,
        user_id: str,
        candidates: List[Dict[str, str]],
        fuzzy_threshold: float = 0.85,
    ) -> List[str]:
        """
        Resolve NER-extracted candidates against the graph.
        Lookup order: exact match (type+name), then fuzzy (threshold default 0.85).
        Returns list of entity ids for matched candidates.
        """
        if not self._enabled or not user_id or not candidates:
            return []
        graph_entities = self.get_entities_for_user(user_id)
        if not graph_entities:
            return []
        # Build lookup: (type_lower, name_lower) -> entity_id
        exact_map: Dict[Tuple[str, str], str] = {}
        by_type: Dict[str, List[Tuple[str, str]]] = {}  # type -> [(name, id)]
        for e in graph_entities:
            eid = e.get("id")
            etype = (e.get("type") or "").strip().lower()
            ename = (e.get("name") or "").strip().lower()
            if not eid or not ename:
                continue
            exact_map[(etype, ename)] = eid
            by_type.setdefault(etype, []).append((ename, eid))
        # Also index generic "entity" / "concept" etc. for cross-type fallback
        all_names: List[Tuple[str, str]] = [(e.get("name", "").lower().strip(), e.get("id", "")) for e in graph_entities if e.get("name") and e.get("id")]

        resolved: List[str] = []
        try:
            from rapidfuzz import fuzz
        except ImportError:
            # Fallback: exact only
            for c in candidates:
                ctype = (c.get("type") or "").strip().lower() or "concept"
                cname = (c.get("name") or "").strip().lower()
                if not cname:
                    continue
                eid = exact_map.get((ctype, cname))
                if not eid:
                    eid = exact_map.get(("concept", cname))
                if eid and eid not in resolved:
                    resolved.append(eid)
            return resolved

        threshold_int = int(fuzzy_threshold * 100)
        for c in candidates:
            ctype = (c.get("type") or "").strip().lower() or "concept"
            cname = (c.get("name") or "").strip().lower()
            if not cname:
                continue
            # 1. Exact match
            eid = exact_map.get((ctype, cname))
            if not eid:
                eid = exact_map.get(("concept", cname))
            if eid:
                if eid not in resolved:
                    resolved.append(eid)
                continue
            # 2. Fuzzy match
            best_score = 0
            best_id: Optional[str] = None
            candidates_fuzzy = by_type.get(ctype, []) + ([] if ctype in by_type else all_names)
            for ename, eid in candidates_fuzzy:
                if not ename:
                    continue
                score = fuzz.ratio(cname, ename)
                if score >= threshold_int and score > best_score:
                    best_score = score
                    best_id = eid
            if best_id and best_id not in resolved:
                resolved.append(best_id)
        return resolved

    def get_memory_ids_for_entity_names(
        self,
        user_id: str,
        names: List[str],
    ) -> List[str]:
        """
        Fallback: find memory ids by raw name tokens (stop-word style).
        Use resolve_entity_candidates + expand_from_entities for NER-based retrieval.
        """
        if not self._enabled or not names:
            return []
        names_lower = [n.strip().lower() for n in names if n and n.strip()]
        if not names_lower:
            return []
        records = self._run_query(
            """
            MATCH (u:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory)-[:CONTAINS_ENTITY]->(e:Entity)
            WHERE ANY(n IN $names_lower WHERE toLower(e.name) = n OR toLower(e.name) CONTAINS n)
            RETURN DISTINCT m.id AS memory_id
            """,
            {"user_id": user_id, "names_lower": names_lower},
        )
        return [r["memory_id"] for r in records if r.get("memory_id")]


# Singleton for app use
_kg: Optional[KnowledgeGraph] = None


def get_knowledge_graph() -> Optional[KnowledgeGraph]:
    """Get or create KnowledgeGraph singleton. Returns None if Neo4j disabled."""
    global _kg
    if _kg is None:
        _kg = KnowledgeGraph()
    return _kg if _kg.enabled else None
