"""
Neo4j Knowledge Graph — Stores extracted entities and relationships from Remme memories.

Ties to Qdrant via memory_id (Qdrant point id) and entity_ids (Neo4j entity ids in Qdrant payload).

Schema — Nodes:
  User, Memory, Session, Entity, Fact, Evidence

Schema — Relationships:
  User─HAS_MEMORY→Memory, Memory─FROM_SESSION→Session,
  Memory─CONTAINS_ENTITY→Entity, Entity─(RELATED_TO|first-class)→Entity,
  User─(LIVES_IN|WORKS_AT|KNOWS|PREFERS)→Entity (derived from Fact+REFERS_TO in ingestion; see step 3),
  User─HAS_FACT→Fact, Fact─SUPPORTED_BY→Evidence,
  Evidence─FROM_MEMORY→Memory, Evidence─FROM_SESSION→Session,
  Fact─REFERS_TO→Entity, Fact─SUPERSEDES→Fact

Fact node: user_id, namespace, key, value_type, value_text|value_number|value_bool|value_json,
  confidence, source_mode, status, first_seen_at, last_seen_at, last_confirmed_at, editability.
Evidence node (minimal): id, source_type, source_ref, timestamp.

Future: space_id / Space dimension (Mnemo Spaces/Collections). When added, constrain
retrieval and ingestion by space_id. See P11 design §9.4.

Enable via NEO4J_ENABLED=true and NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from core.utils import log_error, log_step

logger = logging.getLogger(__name__)
from memory.space_constants import SPACE_ID_GLOBAL, SYNC_POLICY_SYNC, SYNC_POLICY_SHARED
from memory.user_id import get_user_id

# Optional Neo4j dependency
try:
    import logging
    from neo4j import GraphDatabase

    # Suppress "Received notification from DBMS server" logs (Neo4j 5+ status notifications)
    logging.getLogger("neo4j.notifications").setLevel(logging.CRITICAL)
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


def _canonical_name(name: str) -> str:
    """Normalize entity name for dedupe: lowercase, stripped. Used for composite_key."""
    if not name or not isinstance(name, str):
        return ""
    return name.strip().lower()


# Entity-to-entity relationship types promoted as first-class Neo4j relationship types.
# Extractor may send lowercase (e.g. works_at); we normalize to this set. Unknown types → RELATED_TO.
ENTITY_REL_TYPES = frozenset({
    "WORKS_AT", "LOCATED_IN", "MET", "MET_AT", "OWNS", "PART_OF", "MEMBER_OF", "KNOWS",
    "EMPLOYED_BY", "LIVES_IN", "BASED_IN",
})

# User–Entity relationship types. These edges are derived from Fact+REFERS_TO during ingestion
# (step 3); existing code may also create them from legacy user_facts. Optional confidence
# and source_memory_ids on these edges support backward compatibility during migration.
USER_ENTITY_REL_TYPES = frozenset({"LIVES_IN", "WORKS_AT", "KNOWS", "PREFERS"})

# Derivation table: (namespace_prefix, key_pattern, rel_type). A fact with entity_ref
# matches when namespace.startswith(prefix) and (key == key_pattern or key_pattern == "*").
# First match wins; put more specific rules first. Used to create User–Entity edges from Fact+REFERS_TO.
FACT_DERIVATION_TABLE: List[Tuple[str, str, str]] = [
    ("identity.work", "company", "WORKS_AT"),
    ("identity.work", "*", "WORKS_AT"),
    ("identity.location", "*", "LIVES_IN"),
    ("operating.environment", "location", "LIVES_IN"),
    ("preferences", "*", "PREFERS"),
    ("identity.food", "*", "PREFERS"),
    ("identity.hobby", "*", "PREFERS"),
    ("identity.", "*", "KNOWS"),
]


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
                kwargs = {"uri": self.uri, "auth": (self.user, self.password)}
                try:
                    from neo4j import NotificationMinimumSeverity
                    kwargs["warn_notification_severity"] = NotificationMinimumSeverity.OFF
                except (ImportError, AttributeError):
                    pass
                self._driver = GraphDatabase.driver(**kwargs)
                self._driver.verify_connectivity()
                self._ensure_schema()
                log_step("✅ KnowledgeGraph (Neo4j) initialized", symbol="🔧")
            except Exception as e:
                logger.debug("Neo4j connection failed (will use NetworkX fallback): %s", e)
                self._enabled = False
        elif self._enabled and not self.password:
            logger.debug("NEO4J_PASSWORD not set — Neo4j disabled, using NetworkX fallback")
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None

    def _session(self):
        """Create a session with notification warnings suppressed (e.g. 'relationship type does not exist')."""
        return self._driver.session(warn_notification_severity="OFF")

    def _ensure_schema(self) -> None:
        """Create constraints and indexes if they don't exist."""
        with self._session() as session:
            # Unique constraints for idempotent upserts
            for q in [
                "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
                "CREATE CONSTRAINT space_id IF NOT EXISTS FOR (sp:Space) REQUIRE sp.space_id IS UNIQUE",
                "CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE",
                "CREATE CONSTRAINT session_id IF NOT EXISTS FOR (s:Session) REQUIRE s.session_id IS UNIQUE",
                "CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.composite_key IS UNIQUE",
                # Evidence: unique id
                "CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (ev:Evidence) REQUIRE ev.id IS UNIQUE",
            ]:
                try:
                    session.run(q)
                except Exception:
                    pass  # constraint may already exist
            # Phase 3B: Fact unique on (user_id, namespace, key, space_id). space_id null = global.
            try:
                session.run("DROP CONSTRAINT fact_user_ns_key IF EXISTS")
            except Exception:
                pass
            try:
                session.run(
                    "CREATE CONSTRAINT fact_user_ns_space IF NOT EXISTS FOR (f:Fact) "
                    "REQUIRE (f.user_id, f.namespace, f.key, f.space_id) IS UNIQUE"
                )
            except Exception:
                pass
            session.run(
                "CREATE INDEX entity_name_type IF NOT EXISTS FOR (e:Entity) ON (e.name, e.type)"
            )
            # Ensure IN_SPACE relationship type exists so Neo4j 5+ does not emit
            # "relationship type does not exist" warnings on every query that references it.
            try:
                session.run(
                    """
                    MERGE (s:Session {session_id: $sid})
                    ON CREATE SET s.id = $sid, s.original_query = '', s.created_at = datetime()
                    WITH s
                    MERGE (sp:Space {space_id: $sid})
                    ON CREATE SET sp.name = '', sp.description = '', sp.created_at = datetime()
                    WITH s, sp
                    MERGE (s)-[:IN_SPACE]->(sp)
                    """,
                    {"sid": "__schema_init__"},
                )
            except Exception:
                pass

    def _run_query(self, query: str, parameters: Optional[Dict] = None) -> List[Dict]:
        """Execute a read query and return records as list of dicts."""
        if not self._enabled or not self._driver:
            return []
        try:
            with self._session() as session:
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
            with self._session() as session:
                session.run(query, parameters or {})
        except Exception as e:
            log_error(f"Neo4j write failed: {e}")

    def get_or_create_user(self, user_id: Optional[str] = None) -> str:
        """Get or create User node. Returns Neo4j internal id (we use user_id as identifier)."""
        uid = user_id or get_user_id()
        if not uid:
            return ""
        self._run_write(
            """
            MERGE (u:User {user_id: $user_id})
            ON CREATE SET u.id = $user_id, u.created_at = datetime()
            RETURN u.user_id
            """,
            {"user_id": uid},
        )
        return uid

    def get_or_create_session(
        self,
        session_id: str,
        original_query: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> str:
        """
        Get or create Session node. Phase 3C: optional space_id links (Session)-[:IN_SPACE]->(Space).
        When space_id provided (and not __global__), session belongs to that space.
        """
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
        use_space = space_id and space_id != SPACE_ID_GLOBAL
        if use_space:
            self._run_write(
                """
                MATCH (s:Session {session_id: $session_id}), (sp:Space {space_id: $space_id})
                MERGE (s)-[:IN_SPACE]->(sp)
                """,
                {"session_id": session_id, "space_id": space_id},
            )
        return session_id

    def get_space_for_session(self, session_id: str) -> Optional[str]:
        """
        Return space_id for session if it has (Session)-[:IN_SPACE]->(Space). Else None.
        Phase 3C. Uses OPTIONAL MATCH to avoid Neo4j "relationship type does not exist"
        warnings when no IN_SPACE relationships exist in the graph yet.
        """
        if not self._enabled or not session_id:
            return None
        records = self._run_query(
            """
            MATCH (s:Session {session_id: $session_id})
            OPTIONAL MATCH (s)-[:IN_SPACE]->(sp:Space)
            RETURN sp.space_id AS space_id
            LIMIT 1
            """,
            {"session_id": session_id},
        )
        if records and records[0].get("space_id"):
            return records[0]["space_id"]
        return None

    def create_space(
        self,
        user_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        sync_policy: Optional[str] = None,
    ) -> str:
        """
        Create a Space node for a user. Returns system-generated space_id (UUID).
        Spaces are first-class; must be created explicitly (no implicit creation).
        Creates (User)-[:OWNS_SPACE]->(Space).
        Phase 4: sync_policy (sync|local_only), version, device_id, updated_at.
        """
        uid = user_id or get_user_id()
        if not self._enabled or not uid:
            return ""
        space_id = str(uuid.uuid4())
        raw = (sync_policy or SYNC_POLICY_SYNC).strip() or SYNC_POLICY_SYNC
        policy = raw if raw in ("sync", "local_only", "shared") else SYNC_POLICY_SYNC
        now_ts = datetime.now().isoformat()
        device_id = ""
        try:
            from memory.sync_config import get_device_id
            device_id = get_device_id()
        except Exception:
            pass
        self.get_or_create_user(uid)
        self._run_write(
            """
            MATCH (u:User {user_id: $user_id})
            CREATE (sp:Space {
                space_id: $space_id, name: $name, description: $description,
                sync_policy: $sync_policy, version: 1, device_id: $device_id,
                updated_at: $updated_at, created_at: datetime()
            })
            CREATE (u)-[:OWNS_SPACE]->(sp)
            """,
            {
                "user_id": uid,
                "space_id": space_id,
                "name": (name or "").strip() or "",
                "description": (description or "").strip() or "",
                "sync_policy": policy,
                "device_id": device_id,
                "updated_at": now_ts,
            },
        )
        return space_id

    def get_spaces_for_user(self, user_id: Optional[str] = None, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """List spaces owned by user. Returns [{space_id, name, description, sync_policy, version, ...}]."""
        uid = user_id or get_user_id()
        if not self._enabled or not uid:
            return []
        records = self._run_query(
            """
            MATCH (u:User {user_id: $user_id})-[:OWNS_SPACE]->(sp:Space)
            WHERE $include_deleted OR sp.deleted IS NULL OR sp.deleted = false
            RETURN sp.space_id AS space_id, sp.name AS name, sp.description AS description,
                   sp.sync_policy AS sync_policy, sp.version AS version,
                   sp.device_id AS device_id, sp.updated_at AS updated_at
            ORDER BY sp.created_at ASC
            """,
            {"user_id": uid, "include_deleted": include_deleted},
        )
        out = []
        for r in records:
            if not r.get("space_id"):
                continue
            rec = {
                "space_id": r["space_id"],
                "name": r.get("name") or "",
                "description": r.get("description") or "",
                "sync_policy": r.get("sync_policy") or SYNC_POLICY_SYNC,
                "version": r.get("version") or 1,
                "device_id": r.get("device_id") or "",
                "updated_at": str(r.get("updated_at", "")) if r.get("updated_at") else "",
            }
            out.append(rec)
        return out

    def get_spaces_shared_with_user(self, user_id: Optional[str] = None, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """List spaces shared with this user (not owned). Returns same shape as get_spaces_for_user, with is_shared=True."""
        uid = user_id or get_user_id()
        if not self._enabled or not uid:
            return []
        records = self._run_query(
            """
            MATCH (sp:Space)-[:SHARED_WITH]->(u:User {user_id: $user_id})
            WHERE $include_deleted OR sp.deleted IS NULL OR sp.deleted = false
            RETURN sp.space_id AS space_id, sp.name AS name, sp.description AS description,
                   sp.sync_policy AS sync_policy, sp.version AS version,
                   sp.device_id AS device_id, sp.updated_at AS updated_at
            ORDER BY sp.name ASC
            """,
            {"user_id": uid, "include_deleted": include_deleted},
        )
        out = []
        for r in records:
            if not r.get("space_id"):
                continue
            rec = {
                "space_id": r["space_id"],
                "name": r.get("name") or "",
                "description": r.get("description") or "",
                "sync_policy": r.get("sync_policy") or SYNC_POLICY_SYNC,
                "version": r.get("version") or 1,
                "device_id": r.get("device_id") or "",
                "updated_at": str(r.get("updated_at", "")) if r.get("updated_at") else "",
                "is_shared": True,
            }
            out.append(rec)
        return out

    def get_all_spaces_for_user(self, user_id: Optional[str] = None, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """List spaces owned by user plus spaces shared with user. Owned first, then shared; each has is_shared True only if shared."""
        owned = self.get_spaces_for_user(user_id=user_id, include_deleted=include_deleted)
        shared = self.get_spaces_shared_with_user(user_id=user_id, include_deleted=include_deleted)
        seen = {s["space_id"] for s in owned}
        for s in shared:
            if s["space_id"] not in seen:
                seen.add(s["space_id"])
                owned.append(s)
        return owned

    def share_space_with(
        self,
        space_id: str,
        shared_with_user_id: str,
        owner_user_id: Optional[str] = None,
    ) -> bool:
        """Share a space with another user. Caller must own the space. Creates (Space)-[:SHARED_WITH]->(User)."""
        uid = owner_user_id or get_user_id()
        if not self._enabled or not space_id or not shared_with_user_id or not uid:
            return False
        if uid == shared_with_user_id:
            return True  # no-op: owner already has access
        # Verify owner
        check = self._run_query(
            "MATCH (u:User {user_id: $owner})-[:OWNS_SPACE]->(sp:Space {space_id: $space_id}) RETURN 1 AS x LIMIT 1",
            {"owner": uid, "space_id": space_id},
        )
        if not check:
            return False
        self.get_or_create_user(shared_with_user_id)
        self._run_write(
            """
            MATCH (sp:Space {space_id: $space_id})
            MATCH (u:User {user_id: $user_id})
            MERGE (sp)-[:SHARED_WITH]->(u)
            """,
            {"space_id": space_id, "user_id": shared_with_user_id},
        )
        return True

    def unshare_space(self, space_id: str, user_id_to_remove: str, owner_user_id: Optional[str] = None) -> bool:
        """Remove a user from a space's shared list. Caller must own the space."""
        uid = owner_user_id or get_user_id()
        if not self._enabled or not space_id or not user_id_to_remove or not uid:
            return False
        check = self._run_query(
            "MATCH (u:User {user_id: $owner})-[:OWNS_SPACE]->(sp:Space {space_id: $space_id}) RETURN 1 AS x LIMIT 1",
            {"owner": uid, "space_id": space_id},
        )
        if not check:
            return False
        self._run_write(
            """
            MATCH (sp:Space {space_id: $space_id})-[r:SHARED_WITH]->(u:User {user_id: $user_id})
            DELETE r
            """,
            {"space_id": space_id, "user_id": user_id_to_remove},
        )
        return True

    def can_user_access_space(self, user_id: Optional[str], space_id: Optional[str]) -> bool:
        """Return True if user is owner of the space or space is shared with them. Global space always allowed."""
        if not space_id or space_id == SPACE_ID_GLOBAL:
            return True
        uid = user_id or get_user_id()
        if not self._enabled or not uid:
            return False
        r = self._run_query(
            """
            MATCH (sp:Space {space_id: $space_id})
            OPTIONAL MATCH (u:User {user_id: $user_id})-[:OWNS_SPACE]->(sp)
            OPTIONAL MATCH (sp)-[:SHARED_WITH]->(u2:User {user_id: $user_id})
            RETURN (u IS NOT NULL OR u2 IS NOT NULL) AS can_access
            """,
            {"space_id": space_id, "user_id": uid},
        )
        return bool(r and r[0].get("can_access"))

    def upsert_space(
        self,
        space_id: str,
        user_id: Optional[str] = None,
        name: str = "",
        description: str = "",
        sync_policy: str = SYNC_POLICY_SYNC,
        version: int = 1,
        device_id: str = "",
        updated_at: str = "",
    ) -> bool:
        """
        Phase 4 Sync: create or update Space node (for applying pulled space changes).
        If space exists: update name, description, sync_policy, version, device_id, updated_at.
        If not: create with user_id (required for create).
        """
        if not self._enabled or not space_id:
            return False
        now_ts = updated_at or datetime.now().isoformat()
        exists = self._run_query(
            "MATCH (sp:Space {space_id: $space_id}) RETURN 1 AS x LIMIT 1",
            {"space_id": space_id},
        )
        if exists:
            self._run_write(
                """
                MATCH (sp:Space {space_id: $space_id})
                SET sp.name = $name, sp.description = $description,
                    sp.sync_policy = $sync_policy, sp.version = $version,
                    sp.device_id = $device_id, sp.updated_at = $updated_at
                """,
                {
                    "space_id": space_id,
                    "name": (name or "").strip(),
                    "description": (description or "").strip(),
                    "sync_policy": (sync_policy or SYNC_POLICY_SYNC).strip(),
                    "version": version,
                    "device_id": device_id or "",
                    "updated_at": now_ts,
                },
            )
            return True
        uid = user_id or get_user_id()
        if uid:
            self.get_or_create_user(uid)
            self._run_write(
                """
                MATCH (u:User {user_id: $user_id})
                CREATE (sp:Space {
                    space_id: $space_id, name: $name, description: $description,
                    sync_policy: $sync_policy, version: $version, device_id: $device_id,
                    updated_at: $updated_at, created_at: datetime()
                })
                CREATE (u)-[:OWNS_SPACE]->(sp)
                """,
                {
                    "user_id": uid,
                    "space_id": space_id,
                    "name": (name or "").strip(),
                    "description": (description or "").strip(),
                    "sync_policy": (sync_policy or SYNC_POLICY_SYNC).strip(),
                    "version": version,
                    "device_id": device_id or "",
                    "updated_at": now_ts,
                },
            )
            return True
        return False

    def delete_space(self, space_id: str) -> None:
        """Phase 4 Sync: Soft delete Space node (for pulled deleted space)."""
        if not self._enabled or not space_id:
            return
        self._run_write(
            """
            MATCH (sp:Space {space_id: $space_id})
            SET sp.deleted = true,
                sp.updated_at = $now,
                sp.version = COALESCE(sp.version, 1) + 1
            """,
            {"space_id": space_id, "now": datetime.now().isoformat()},
        )

    def hard_delete_space(self, space_id: str) -> None:
        """Actually delete Space node."""
        if not self._enabled or not space_id:
            return
        self._run_write(
            "MATCH (sp:Space {space_id: $space_id}) DETACH DELETE sp",
            {"space_id": space_id},
        )

    def move_memory_to_space(
        self,
        memory_id: str,
        target_space_id: Optional[str],
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Move a memory to a different space. Updates (Memory)-[:IN_SPACE]->(Space).
        - target_space_id None or __global__: remove IN_SPACE (memory becomes global).
        - target_space_id: link to that Space. Space must exist; use can_user_access_space first.
        Returns True if the graph was updated (Memory existed); False if Memory not in graph.
        """
        if not self._enabled or not memory_id:
            return False
        use_space = target_space_id and target_space_id != SPACE_ID_GLOBAL

        # Remove any existing IN_SPACE relationship
        self._run_write(
            """
            MATCH (m:Memory {id: $memory_id})
            OPTIONAL MATCH (m)-[r:IN_SPACE]->()
            DELETE r
            RETURN m AS m
            """,
            {"memory_id": memory_id},
        )
        # _run_write returns result of last statement; we need to check if m was matched
        check = self._run_query(
            "MATCH (m:Memory {id: $memory_id}) RETURN 1 AS x LIMIT 1",
            {"memory_id": memory_id},
        )
        if not check:
            return False

        if use_space:
            # Add IN_SPACE to target space (Space must exist)
            self._run_write(
                """
                MATCH (m:Memory {id: $memory_id})
                MATCH (sp:Space {space_id: $space_id})
                MERGE (m)-[:IN_SPACE]->(sp)
                """,
                {"memory_id": memory_id, "space_id": target_space_id},
            )
        return True

    def create_memory(
        self,
        memory_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        category: str = "general",
        source: str = "manual",
        space_id: Optional[str] = None,
    ) -> None:
        """
        Create Memory node and link to User and Session.
        Optional space_id: when provided (and not __global__), link (Memory)-[:IN_SPACE]->(Space).
        When None or __global__, memory is global (no IN_SPACE edge). Space must exist (create_space).
        """
        uid = user_id or get_user_id()
        if not uid or not session_id:
            return
        self.get_or_create_user(uid)
        self.get_or_create_session(session_id, space_id=space_id)
        use_space = space_id and space_id != SPACE_ID_GLOBAL
        self._run_write(
            """
            MERGE (m:Memory {id: $mid})
            ON CREATE SET m.category = $category, m.source = $source, m.created_at = datetime()
            ON MATCH SET m.category = $category, m.source = $source
            WITH m
            MATCH (u:User {user_id: $user_id})
            MERGE (u)-[:HAS_MEMORY]->(m)
            WITH m
            MATCH (s:Session {session_id: $session_id})
            MERGE (m)-[:FROM_SESSION]->(s)
            """
            + (
                """
            WITH m
            MATCH (sp:Space {space_id: $space_id})
            MERGE (m)-[:IN_SPACE]->(sp)
            """
                if use_space
                else ""
            ),
            {
                "mid": memory_id,
                "user_id": uid,
                "session_id": session_id,
                "category": category,
                "source": source,
                **({"space_id": space_id} if use_space else {}),
            },
        )

    def get_or_create_entity(self, entity_type: str, name: str) -> str:
        """
        Get or create Entity node. Returns entity id (uuid).
        Deduplicates by composite_key = type::canonical_name so "Google" and "google" merge.
        Keeps name as display, canonical_name (lowercase, stripped) for key/dedupe.
        """
        display_name = (name or "").strip()
        canonical = _canonical_name(name)
        type_normalized = (entity_type or "Concept").strip().lower()
        composite_key = f"{type_normalized}::{canonical}"
        if not canonical:
            return str(uuid.uuid4())  # no valid name
        entity_id = str(uuid.uuid4())
        records = self._run_query(
            """
            MERGE (e:Entity {composite_key: $composite_key})
            ON CREATE SET
                e.id = $entity_id,
                e.type = $entity_type,
                e.name = $name,
                e.canonical_name = $canonical_name,
                e.created_at = datetime()
            ON MATCH SET
                e.type = $entity_type,
                e.name = $name,
                e.canonical_name = $canonical_name
            RETURN e.id AS id
            """,
            {
                "composite_key": composite_key,
                "entity_id": entity_id,
                "entity_type": entity_type.strip() or "Concept",
                "name": display_name or canonical,
                "canonical_name": canonical,
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
        """
        Create entity-to-entity relationship. Uses first-class Neo4j relationship type
        when rel_type is in ENTITY_REL_TYPES (e.g. WORKS_AT, LOCATED_IN, MET, OWNS);
        otherwise creates RELATED_TO and stores the type in r.type for fallback.
        """
        raw = (rel_type or "related_to").strip()
        rel_type_upper = raw.upper().replace("-", "_").replace(" ", "_")
        params = {
            "from_id": from_entity_id,
            "to_id": to_entity_id,
            "value": value or "",
            "confidence": confidence,
            "source_memory_ids": source_memory_ids or [],
        }
        if rel_type_upper in ENTITY_REL_TYPES:
            # First-class relationship type (indexable, expressive queries)
            self._run_write(
                f"""
                MATCH (a:Entity {{id: $from_id}}), (b:Entity {{id: $to_id}})
                MERGE (a)-[r:{rel_type_upper}]->(b)
                SET r.value = $value,
                    r.confidence = $confidence,
                    r.source_memory_ids = $source_memory_ids
                """,
                params,
            )
        else:
            # Fallback: RELATED_TO with type stored as property
            self._run_write(
                """
                MATCH (a:Entity {id: $from_id}), (b:Entity {id: $to_id})
                MERGE (a)-[r:RELATED_TO]->(b)
                SET r.type = $rel_type,
                    r.value = $value,
                    r.confidence = $confidence,
                    r.source_memory_ids = $source_memory_ids
                """,
                {**params, "rel_type": raw},
            )

    def create_user_entity_relationship(
        self,
        user_id: str,
        entity_id: str,
        rel_type: str,  # LIVES_IN, WORKS_AT, KNOWS, PREFERS (USER_ENTITY_REL_TYPES)
        source_memory_ids: Optional[List[str]] = None,
        confidence: Optional[float] = None,
    ) -> None:
        """
        Create user-centric relationship: User -[:rel_type]-> Entity.
        These edges may be derived from Fact+REFERS_TO in the unified ingestion (step 3).
        Optional confidence and source_memory_ids support backward compatibility during migration.
        """
        if rel_type not in USER_ENTITY_REL_TYPES:
            log_error(f"Invalid user-entity rel type: {rel_type}")
            return
        set_clauses = ["r.source_memory_ids = $source_memory_ids"]
        params: Dict[str, Any] = {
            "user_id": user_id,
            "entity_id": entity_id,
            "source_memory_ids": source_memory_ids or [],
        }
        if confidence is not None:
            set_clauses.append("r.confidence = $confidence")
            params["confidence"] = confidence
        self._run_write(
            f"""
            MATCH (u:User {{user_id: $user_id}}), (e:Entity {{id: $entity_id}})
            MERGE (u)-[r:{rel_type}]->(e)
            SET {", ".join(set_clauses)}
            """,
            params,
        )

    def upsert_fact(
        self,
        namespace: str,
        key: str,
        user_id: Optional[str] = None,
        value_type: str = "text",
        value_text: Optional[str] = None,
        value_number: Optional[float] = None,
        value_bool: Optional[bool] = None,
        value_json: Optional[Any] = None,
        confidence: float = 0.8,
        source_mode: str = "extraction",
        entity_ref: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create or update a Fact node. Idempotent by (user_id, namespace, key, space_id).
        Phase 3B: space_id null = global; when provided, link (Fact)-[:IN_SPACE]->(Space).
        Returns fact id (Neo4j node id or internal id) or None.
        For source_mode=ui_edit, sets last_confirmed_at.
        """
        uid = user_id or get_user_id()
        if not self._enabled or not namespace or not key or not uid:
            return None
        fact_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        is_ui_edit = (source_mode or "extraction") == "ui_edit"
        confirmed_clause = ", f.last_confirmed_at = $now" if is_ui_edit else ""
        use_space = space_id and space_id != SPACE_ID_GLOBAL
        # value_preview: short string for Neo4j Graph UI display (set for all Fact nodes so caption can use it)
        preview: Optional[str] = None
        vt = (value_type or "text").lower()
        if vt == "text" and value_text is not None:
            preview = str(value_text)[:200]
        elif vt == "number" and value_number is not None:
            preview = str(value_number)
        elif vt == "bool" and value_bool is not None:
            preview = str(value_bool)
        elif vt == "json" and isinstance(value_json, list) and value_json:
            strs_ = [str(x) for x in value_json[:10] if x is not None and str(x).strip().lower() != "null"]
            preview = ", ".join(strs_)[:200] if strs_ else None
        elif vt == "json" and isinstance(value_json, dict):
            preview = json.dumps(value_json)[:200]
        # fallback: derive from any value field so value_preview is always set when there's data
        if preview is None:
            if value_text is not None and str(value_text).strip():
                preview = str(value_text)[:200]
            elif value_number is not None:
                preview = str(value_number)
            elif value_bool is not None:
                preview = str(value_bool)
            elif value_json is not None:
                preview = (json.dumps(value_json) if isinstance(value_json, (list, dict)) else str(value_json))[:200]
        params: Dict[str, Any] = {
            "user_id": uid,
            "namespace": namespace,
            "key": key,
            "fact_id": fact_id,
            "value_type": vt,
            "value_text": value_text,
            "value_number": value_number,
            "value_bool": value_bool,
            # Pass list/dict directly so Neo4j stores native list/map
            "value_json": value_json if isinstance(value_json, (dict, list)) else (str(value_json) if value_json is not None else None),
            "value_preview": preview,
            "confidence": confidence,
            "source_mode": source_mode or "extraction",
            "now": now,
            "space_id": space_id if use_space else SPACE_ID_GLOBAL,
        }
        self._run_write(
            """
            MERGE (u:User {user_id: $user_id})
            WITH u
            MERGE (f:Fact {user_id: $user_id, namespace: $namespace, key: $key, space_id: $space_id})
            ON CREATE SET
                f.id = $fact_id,
                f.value_type = $value_type,
                f.value_text = $value_text,
                f.value_number = $value_number,
                f.value_bool = $value_bool,
                f.value_json = $value_json,
                f.value_preview = $value_preview,
                f.confidence = $confidence,
                f.source_mode = $source_mode,
                f.first_seen_at = $now,
                f.last_seen_at = $now
                """ + confirmed_clause + """
            ON MATCH SET
                f.value_type = $value_type,
                f.value_text = $value_text,
                f.value_number = $value_number,
                f.value_bool = $value_bool,
                f.value_json = $value_json,
                f.value_preview = $value_preview,
                f.confidence = $confidence,
                f.source_mode = $source_mode,
                f.last_seen_at = $now
                """ + confirmed_clause + """
            WITH f, u
            MERGE (u)-[:HAS_FACT]->(f)
            """
            + ("""
            WITH f
            MATCH (sp:Space {space_id: $space_id})
            MERGE (f)-[:IN_SPACE]->(sp)
            """ if use_space else ""),
            params,
        )
        # Phase 5: update CONTRADICTS relationships between Facts that disagree on value
        try:
            self._update_fact_contradictions(uid, namespace, key)
        except Exception as e:
            log_error(f"KnowledgeGraph: failed to update fact contradictions for {namespace}.{key}: {e}")
        if entity_ref:
            # Resolve entity_ref (composite_key "Type::name" or entity id) and create Fact-REFERS_TO-Entity
            eid = self._resolve_entity_ref_for_fact(entity_ref, uid)
            if eid:
                self._run_write(
                    """
                    MATCH (f:Fact {user_id: $user_id, namespace: $namespace, key: $key}), (e:Entity {id: $entity_id})
                    MERGE (f)-[:REFERS_TO]->(e)
                    """,
                    {"user_id": uid, "namespace": namespace, "key": key, "entity_id": eid},
                )
        return fact_id

    def _update_fact_contradictions(self, user_id: str, namespace: str, key: str) -> None:
        """
        Phase 5: Detect conflicting Facts for the same (user, namespace, key) across spaces and
        link them with CONTRADICTS relationships.

        We consider two Facts contradictory when:
        - They share user_id, namespace, key.
        - They have the same value_type.
        - Their concrete value fields differ.

        This is conservative and only compares simple value equality; more nuanced
        semantic contradiction remains future work.
        """
        if not self._enabled or not user_id or not namespace or not key:
            return
        self._run_write(
            """
            MATCH (f:Fact {user_id: $user_id, namespace: $namespace, key: $key})
            WITH collect(f) AS facts
            UNWIND facts AS a
            UNWIND facts AS b
            WITH a, b
            WHERE id(a) < id(b)
              AND a.value_type = b.value_type
              AND (
                (a.value_type = 'bool'   AND a.value_bool   IS NOT NULL AND b.value_bool   IS NOT NULL AND a.value_bool   <> b.value_bool) OR
                (a.value_type = 'number' AND a.value_number IS NOT NULL AND b.value_number IS NOT NULL AND a.value_number <> b.value_number) OR
                (a.value_type = 'text'   AND a.value_text   IS NOT NULL AND b.value_text   IS NOT NULL AND a.value_text   <> b.value_text) OR
                (a.value_type = 'json'   AND a.value_json   IS NOT NULL AND b.value_json   IS NOT NULL AND a.value_json   <> b.value_json)
              )
            MERGE (a)-[:CONTRADICTS]->(b)
            MERGE (b)-[:CONTRADICTS]->(a)
            """,
            {"user_id": user_id, "namespace": namespace, "key": key},
        )

    def _resolve_entity_ref_for_fact(self, entity_ref: str, user_id: str) -> Optional[str]:
        """Resolve entity_ref (composite_key 'Type::name' or entity id) to entity id. Create entity if composite key."""
        ref = (entity_ref or "").strip()
        if not ref:
            return None
        if "::" in ref:
            parts = ref.split("::", 1)
            etype = (parts[0] or "Concept").strip()
            name = (parts[1] or "").strip()
            if name:
                return self.get_or_create_entity(etype, name)
        # Assume it's an entity id
        records = self._run_query("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": ref})
        if records and records[0].get("id"):
            return records[0]["id"]
        return None

    def merge_list_fact(
        self,
        namespace: str,
        key: str,
        values: List[Any],
        user_id: Optional[str] = None,
        confidence: float = 0.8,
        space_id: Optional[str] = None,
    ) -> bool:
        """
        Merge values into an existing list-valued Fact, or create it if missing.
        Phase 3B: optional space_id for space-scoped facts.
        """
        uid = user_id or get_user_id()
        if not self._enabled or not uid or not namespace or not key:
            return False
        valid: List[Any] = []
        for v in values or []:
            s = str(v).strip() if v is not None else ""
            if s and s.lower() != "null" and s not in [str(x).strip() for x in valid]:
                valid.append(s)
        if not valid:
            return False
        use_space = space_id and space_id != SPACE_ID_GLOBAL
        params: Dict[str, Any] = {"user_id": uid, "ns": namespace, "key": key, "space_id": space_id if use_space else SPACE_ID_GLOBAL}
        records = self._run_query(
            """
            MATCH (u:User {user_id: $user_id})-[:HAS_FACT]->(f:Fact {namespace: $ns, key: $key, space_id: $space_id})
            RETURN properties(f) AS props
            """,
            params,
        )
        if records:
            p = records[0].get("props") or {}
            current = p.get("value_json")
            if isinstance(current, list):
                for v in valid:
                    if v not in current:
                        current = list(current) + [v]
            else:
                current = list(valid)
        else:
            current = list(valid)
        self.upsert_fact(
            user_id=uid,
            namespace=namespace,
            key=key,
            value_type="json",
            value_json=current,
            confidence=confidence,
            source_mode="extraction",
            space_id=space_id,
        )
        return True

    def create_evidence(
        self,
        evidence_id: str,
        source_type: str,
        source_ref: str,
        namespace: str,
        key: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        memory_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> None:
        """
        Create Evidence node and link to Fact (SUPPORTED_BY) by (user_id, namespace, key, space_id).
        Phase 3B: space_id null = global Fact. Evidence is append-only.
        """
        uid = user_id or get_user_id()
        if not self._enabled or not evidence_id or not uid or not namespace or not key:
            return
        ts = timestamp or (datetime.utcnow().isoformat() + "Z")
        use_space = space_id and space_id != SPACE_ID_GLOBAL
        params: Dict[str, Any] = {
            "evidence_id": evidence_id,
            "source_type": source_type or "extraction",
            "source_ref": source_ref,
            "timestamp": ts,
            "user_id": uid,
            "namespace": namespace,
            "key": key,
            "space_id": space_id if use_space else SPACE_ID_GLOBAL,
        }
        self._run_write(
            """
            MERGE (ev:Evidence {id: $evidence_id})
            ON CREATE SET ev.source_type = $source_type, ev.source_ref = $source_ref, ev.timestamp = $timestamp
            WITH ev
            MATCH (f:Fact {user_id: $user_id, namespace: $namespace, key: $key, space_id: $space_id})
            MERGE (f)-[:SUPPORTED_BY]->(ev)
            """,
            params,
        )
        if session_id:
            self._run_write(
                """
                MATCH (ev:Evidence {id: $evidence_id}), (s:Session {session_id: $session_id})
                MERGE (ev)-[:FROM_SESSION]->(s)
                """,
                {"evidence_id": evidence_id, "session_id": session_id},
            )
        if memory_id:
            self._run_write(
                """
                MATCH (ev:Evidence {id: $evidence_id}), (m:Memory {id: $memory_id})
                MERGE (ev)-[:FROM_MEMORY]->(m)
                """,
                {"evidence_id": evidence_id, "memory_id": memory_id},
            )

    def upsert_fact_from_ui(
        self,
        namespace: str,
        key: str,
        user_id: Optional[str] = None,
        value_type: str = "text",
        value: Optional[Any] = None,
        value_text: Optional[str] = None,
        value_number: Optional[float] = None,
        value_bool: Optional[bool] = None,
        value_json: Optional[Any] = None,
        entity_ref: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        UI-driven fact edit (step 7): upsert Fact, create Evidence with source_type=ui_edit,
        set source_mode=ui_edit, confidence=1.0, last_confirmed_at, and re-run derivation.
        Value can be provided as `value` (single field) or as value_text/value_number/value_bool/value_json.
        Returns fact id or None.
        """
        uid = user_id or get_user_id()
        if not self._enabled or not namespace or not key or not uid:
            return None
        vt = (value_type or "text").lower()
        v = value
        vt_text = value_text
        vt_num = value_number
        vt_bool = value_bool
        vt_json = value_json
        if v is not None:
            if vt == "text":
                vt_text = str(v)
            elif vt == "number":
                vt_num = float(v) if isinstance(v, (int, float)) else None
            elif vt == "bool":
                vt_bool = bool(v)
            elif vt == "json":
                vt_json = v if isinstance(v, (dict, list)) else None
        fid = self.upsert_fact(
            user_id=uid,
            namespace=namespace,
            key=key,
            value_type=vt or "text",
            value_text=vt_text,
            value_number=vt_num,
            value_bool=vt_bool,
            value_json=vt_json,
            confidence=1.0,
            source_mode="ui_edit",
            entity_ref=entity_ref,
            space_id=space_id,
        )
        if not fid:
            return None
        ev_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        self.create_evidence(
            evidence_id=ev_id,
            source_type="ui_edit",
            source_ref="ui_edit",
            user_id=uid,
            namespace=namespace,
            key=key,
            timestamp=now,
            space_id=space_id,
        )
        fact_dict = {
            "namespace": namespace,
            "key": key,
            "entity_ref": entity_ref,
        }
        self._derive_user_entity_from_facts(uid, [fact_dict], {})
        return fid

    def _derive_user_entity_from_facts(
        self,
        user_id: str,
        facts: List[Any],
        entity_map: Dict[Tuple[str, str], str],
        source_memory_ids: Optional[List[str]] = None,
    ) -> None:
        """
        For each fact with entity_ref, resolve entity and create User–Entity edge from derivation table.
        facts: list of dict-like with namespace, key, entity_ref (e.g. FactItem or dict).
        entity_map: (type_normalized, canonical_name) -> entity_id from current ingestion.
        """
        for f in facts:
            entity_ref = f.get("entity_ref") if isinstance(f, dict) else getattr(f, "entity_ref", None)
            if not entity_ref:
                continue
            namespace = (f.get("namespace") or "") if isinstance(f, dict) else (getattr(f, "namespace", None) or "")
            key = (f.get("key") or "") if isinstance(f, dict) else (getattr(f, "key", None) or "")
            rel_type = "PREFERS"
            for prefix, key_pat, rt in FACT_DERIVATION_TABLE:
                if namespace.startswith(prefix) and (key_pat == "*" or key == key_pat):
                    rel_type = rt
                    break
            if rel_type not in USER_ENTITY_REL_TYPES:
                rel_type = "PREFERS"
            eid = None
            ref = str(entity_ref).strip()
            if "::" in ref:
                parts = ref.split("::", 1)
                etype = (parts[0] or "Concept").strip().lower()
                name = (parts[1] or "").strip()
                if name:
                    canonical = _canonical_name(name)
                    eid = entity_map.get((etype, canonical))
                    if not eid:
                        eid = self.get_or_create_entity(etype or "Concept", name)
            else:
                eid = ref
            if eid:
                self.create_user_entity_relationship(
                    user_id,
                    eid,
                    rel_type,
                    source_memory_ids=source_memory_ids or [],
                )

    def ingest_memory(
        self,
        memory_id: str,
        text: str,
        session_id: str,
        user_id: Optional[str] = None,
        category: str = "general",
        source: str = "manual",
        space_id: Optional[str] = None,
        entities: Optional[List[Dict[str, Any]]] = None,
        entity_relationships: Optional[List[Dict[str, Any]]] = None,
        user_facts: Optional[List[Dict[str, Any]]] = None,
        facts: Optional[List[Any]] = None,
        evidence_events: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """
        Full ingestion: create Memory, extract/link entities, relationships, user facts.
        Optional space_id: link (Memory)-[:IN_SPACE]->(Space) when provided (not __global__).
        When facts/evidence_events are provided (unified extraction), also upsert Fact nodes,
        create Evidence, and derive User–Entity edges.
        Returns dict with entity_ids (for Neo4j link) and entity_labels (type, name for Qdrant payload).
        """
        uid = user_id or get_user_id()
        empty_result: Dict[str, Any] = {"entity_ids": [], "entity_labels": []}
        if not self._enabled or not uid:
            return empty_result
        self.create_memory(memory_id, uid, session_id, category, source, space_id=space_id)
        entity_ids: List[str] = []
        entity_labels: List[Dict[str, str]] = []  # [{type, name}] same order as entity_ids
        entity_map: Dict[Tuple[str, str], str] = {}  # (type_normalized, canonical_name) -> entity_id

        # Create entities and link to memory (dedupe by canonical key so "Google" and "google" merge)
        for ent in entities or []:
            etype = ent.get("type", "Concept")
            name = ent.get("name", "").strip()
            if not name:
                continue
            canonical = _canonical_name(name)
            type_norm = (etype or "Concept").strip().lower()
            key = (type_norm, canonical)
            if key not in entity_map:
                entity_map[key] = self.get_or_create_entity(etype, name)
            eid = entity_map[key]
            entity_ids.append(eid)
            entity_labels.append({"type": etype, "name": name})
            self.link_memory_to_entity(memory_id, eid)

        # Entity-entity relationships (resolve by canonical key)
        for rel in entity_relationships or []:
            from_key = (
                (rel.get("from_type") or "Entity").strip().lower(),
                _canonical_name(rel.get("from_name", "")),
            )
            to_key = (
                (rel.get("to_type") or "Entity").strip().lower(),
                _canonical_name(rel.get("to_name", "")),
            )
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

        # User-centric facts (resolve by canonical key)
        for fact in user_facts or []:
            rel_type = fact.get("rel_type", "KNOWS")
            name = fact.get("name", "").strip()
            etype = fact.get("type", "Concept")
            if not name:
                continue
            key = ((etype or "Concept").strip().lower(), _canonical_name(name))
            if key not in entity_map:
                entity_map[key] = self.get_or_create_entity(etype, name)
            self.create_user_entity_relationship(
                uid,
                entity_map[key],
                rel_type,
                source_memory_ids=[memory_id],
            )

        # Fact + Evidence (unified extraction path): normalize, upsert facts, create evidence
        if facts:
            from memory.fact_normalizer import normalize_facts
            from memory.fact_field_registry import get_scope_for_namespace_key

            facts = normalize_facts(facts)
            for f in facts:
                ns = f.get("namespace", "")
                k = f.get("key", "")
                if not ns or not k:
                    continue
                # Phase 3B: pass space_id only for space-scoped facts
                fact_space_id = space_id if (get_scope_for_namespace_key(ns, k) == "space" and space_id) else None
                vt = f.get("value_type", "text")
                val = f.get("value")
                vt_text = f.get("value_text")
                vt_num = f.get("value_number")
                vt_bool = f.get("value_bool")
                vt_json = f.get("value_json")
                if vt_text is None and val is not None and vt == "text":
                    vt_text = str(val)
                if vt_num is None and val is not None and vt == "number":
                    vt_num = float(val) if isinstance(val, (int, float)) else None
                if vt_bool is None and val is not None and vt == "bool":
                    vt_bool = bool(val)
                if vt_json is None and val is not None and vt == "json":
                    vt_json = val
                entity_ref = f.get("entity_ref")
                append = f.get("append", False)

                # List-valued facts: merge into existing, create evidence
                if append:
                    vals = f.get("value_json") or (f.get("value") if isinstance(f.get("value"), list) else [f.get("value")] if f.get("value") is not None else [])
                    if vals and self.merge_list_fact(uid, ns, k, vals, confidence=0.8, space_id=fact_space_id):
                        ev_id = str(uuid.uuid4())
                        ev_source_ref = memory_id
                        ev_source_type = "extraction"
                        if evidence_events:
                            first_ev = evidence_events[0]
                            ev_source_ref = first_ev.get("source_ref", memory_id) if isinstance(first_ev, dict) else getattr(first_ev, "source_ref", memory_id)
                            ev_source_type = first_ev.get("source_type", "extraction") if isinstance(first_ev, dict) else getattr(first_ev, "source_type", "extraction")
                        self.create_evidence(
                            evidence_id=ev_id, source_type=ev_source_type, source_ref=ev_source_ref or memory_id,
                            user_id=uid, namespace=ns, key=k,
                            session_id=session_id, memory_id=memory_id,
                            space_id=fact_space_id,
                        )
                    continue

                self.upsert_fact(
                    user_id=uid,
                    namespace=ns,
                    key=k,
                    value_type=vt,
                    value_text=vt_text,
                    value_number=vt_num,
                    value_bool=vt_bool,
                    value_json=vt_json,
                    confidence=0.8,
                    source_mode="extraction",
                    entity_ref=entity_ref,
                    space_id=fact_space_id,
                )
                ev_id = str(uuid.uuid4())
                ev_source_ref = memory_id
                ev_source_type = "extraction"
                if evidence_events:
                    first_ev = evidence_events[0]
                    if isinstance(first_ev, dict):
                        ev_source_ref = first_ev.get("source_ref") or memory_id
                        ev_source_type = first_ev.get("source_type", "extraction")
                    else:
                        ev_source_ref = getattr(first_ev, "source_ref", None) or memory_id
                        ev_source_type = getattr(first_ev, "source_type", "extraction")
                self.create_evidence(
                    evidence_id=ev_id,
                    source_type=ev_source_type,
                    source_ref=ev_source_ref or memory_id,
                    user_id=uid,
                    namespace=ns,
                    key=k,
                    session_id=session_id,
                    memory_id=memory_id,
                    space_id=fact_space_id,
                )
            self._derive_user_entity_from_facts(
                uid,
                facts,
                entity_map,
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

    def ingest_from_unified_extraction(
        self,
        user_id: str,
        session_id: str,
        memory_ids: List[str],
        extraction: Any,
        category: str = "derived",
        source: str = "session",
        space_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Session pipeline: write Memory nodes, entities, relationships, facts, evidence from
        a UnifiedExtractionResult. Creates User, Session; one Memory per memory_id; entities
        and entity_relationships; upserts facts and evidence; derives User–Entity edges.
        Returns {"entity_ids": [...], "entity_labels": [...]} for Qdrant payload update
        (entities from full session context; all session memories share these).
        """
        if not self._enabled or not user_id or not session_id or not memory_ids:
            return {}
        self.get_or_create_user(user_id)
        self.get_or_create_session(session_id, space_id=space_id)
        entity_map: Dict[Tuple[str, str], str] = {}
        entities = getattr(extraction, "entities", None) or (extraction.get("entities", []) if isinstance(extraction, dict) else [])
        entity_relationships = getattr(extraction, "entity_relationships", None) or (extraction.get("entity_relationships", []) if isinstance(extraction, dict) else [])
        facts = getattr(extraction, "facts", None) or (extraction.get("facts", []) if isinstance(extraction, dict) else [])
        evidence_events = getattr(extraction, "evidence_events", None) or (extraction.get("evidence_events", []) if isinstance(extraction, dict) else [])

        for memory_id in memory_ids:
            self.create_memory(memory_id, user_id, session_id, category=category, source=source, space_id=space_id)
        for ent in entities:
            etype = getattr(ent, "type", None) or (ent.get("type", "Concept") if isinstance(ent, dict) else "Concept")
            name = getattr(ent, "name", None) or (ent.get("name", "") if isinstance(ent, dict) else "")
            if not name:
                continue
            canonical = _canonical_name(name)
            type_norm = (str(etype) or "Concept").strip().lower()
            key = (type_norm, canonical)
            if key not in entity_map:
                entity_map[key] = self.get_or_create_entity(etype, name)
            for memory_id in memory_ids:
                self.link_memory_to_entity(memory_id, entity_map[key])
        for rel in entity_relationships:
            from_type = getattr(rel, "from_type", "Entity") or (rel.get("from_type", "Entity") if isinstance(rel, dict) else "Entity")
            from_name = getattr(rel, "from_name", "") or (rel.get("from_name", "") if isinstance(rel, dict) else "")
            to_type = getattr(rel, "to_type", "Entity") or (rel.get("to_type", "Entity") if isinstance(rel, dict) else "Entity")
            to_name = getattr(rel, "to_name", "") or (rel.get("to_name", "") if isinstance(rel, dict) else "")
            from_key = (str(from_type).strip().lower(), _canonical_name(from_name))
            to_key = (str(to_type).strip().lower(), _canonical_name(to_name))
            from_id = entity_map.get(from_key)
            to_id = entity_map.get(to_key)
            if from_id and to_id:
                rtype = getattr(rel, "type", "related_to") or (rel.get("type", "related_to") if isinstance(rel, dict) else "related_to")
                self.create_entity_relationship(
                    from_id, to_id,
                    rel_type=rtype,
                    value=rel.get("value") if isinstance(rel, dict) else getattr(rel, "value", None),
                    confidence=float(rel.get("confidence", 1.0)) if isinstance(rel, dict) else getattr(rel, "confidence", 1.0),
                    source_memory_ids=memory_ids,
                )
        from memory.fact_normalizer import normalize_facts
        from memory.fact_field_registry import get_scope_for_namespace_key

        facts = normalize_facts(facts)
        for f in facts:
            ns = f.get("namespace", "")
            k = f.get("key", "")
            if not ns or not k:
                continue
            # Phase 3B: pass space_id only for space-scoped facts
            fact_space_id = space_id if (get_scope_for_namespace_key(ns, k) == "space" and space_id) else None
            vt = f.get("value_type", "text")
            val = f.get("value")
            vt_text = f.get("value_text")
            vt_num = f.get("value_number")
            vt_bool = f.get("value_bool")
            vt_json = f.get("value_json")
            if vt_text is None and val is not None and vt == "text":
                vt_text = str(val)
            if vt_num is None and val is not None and vt == "number":
                vt_num = float(val) if isinstance(val, (int, float)) else None
            if vt_bool is None and val is not None and vt == "bool":
                vt_bool = bool(val)
            if vt_json is None and val is not None and vt == "json":
                vt_json = val
            entity_ref = f.get("entity_ref")
            append = f.get("append", False)
            if append:
                vals = f.get("value_json") or (f.get("value") if isinstance(f.get("value"), list) else [f.get("value")] if f.get("value") is not None else [])
                if vals and self.merge_list_fact(user_id, ns, k, vals, confidence=0.8, space_id=fact_space_id):
                    ev_id = str(uuid.uuid4())
                    ev_source_ref = session_id
                    ev_source_type = "extraction"
                    if evidence_events:
                        first_ev = evidence_events[0]
                        ev_source_ref = first_ev.get("source_ref", session_id) if isinstance(first_ev, dict) else getattr(first_ev, "source_ref", session_id)
                        ev_source_type = first_ev.get("source_type", "extraction") if isinstance(first_ev, dict) else getattr(first_ev, "source_type", "extraction")
                    self.create_evidence(
                        evidence_id=ev_id, source_type=ev_source_type, source_ref=ev_source_ref or session_id,
                        user_id=user_id, namespace=ns, key=k,
                        session_id=session_id, memory_id=memory_ids[0] if memory_ids else None,
                        space_id=fact_space_id,
                    )
                continue
            self.upsert_fact(
                user_id=user_id,
                namespace=ns,
                key=k,
                value_type=vt,
                value_text=vt_text,
                value_number=vt_num,
                value_bool=vt_bool,
                value_json=vt_json,
                confidence=0.8,
                source_mode="extraction",
                entity_ref=entity_ref,
                space_id=fact_space_id,
            )
            ev_id = str(uuid.uuid4())
            ev_source_ref = session_id
            ev_source_type = "extraction"
            if evidence_events:
                first_ev = evidence_events[0]
                ev_source_ref = (first_ev.get("source_ref") if isinstance(first_ev, dict) else getattr(first_ev, "source_ref", None)) or session_id
                ev_source_type = (first_ev.get("source_type", "extraction") if isinstance(first_ev, dict) else getattr(first_ev, "source_type", "extraction"))
            self.create_evidence(
                evidence_id=ev_id,
                source_type=ev_source_type,
                source_ref=ev_source_ref,
                user_id=user_id,
                namespace=ns,
                key=k,
                session_id=session_id,
                memory_id=memory_ids[0] if memory_ids else None,
                timestamp=None,
                space_id=fact_space_id,
            )
        if facts:
            self._derive_user_entity_from_facts(user_id, facts, entity_map, source_memory_ids=memory_ids)

        # Return entity_ids and entity_labels for Qdrant payload update (session-level)
        deduped_ids = list(dict.fromkeys(entity_map.values()))
        entity_labels = []
        for ent in entities:
            etype = getattr(ent, "type", None) or (ent.get("type", "Concept") if isinstance(ent, dict) else "Concept")
            name = getattr(ent, "name", None) or (ent.get("name", "") if isinstance(ent, dict) else "")
            if name:
                entity_labels.append({"type": str(etype), "name": str(name)})
        return {"entity_ids": deduped_ids, "entity_labels": entity_labels}

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
        Entity nodes that were only referenced by this memory (orphans) are also removed,
        along with their entity-entity and user-entity relationships, to avoid dead data.
        """
        if not self._enabled or not memory_id:
            return
        # Collect entity ids linked to this memory before we delete it
        records = self._run_query(
            """
            MATCH (m:Memory {id: $memory_id})-[:CONTAINS_ENTITY]->(e:Entity)
            RETURN collect(e.id) AS entity_ids
            """,
            {"memory_id": memory_id},
        )
        entity_ids: List[str] = []
        if records and records[0].get("entity_ids"):
            entity_ids = [eid for eid in records[0]["entity_ids"] if eid]

        # Remove the memory and its relationships (Soft Delete Version)
        self._run_write(
            """
            MATCH (m:Memory {id: $memory_id})
            SET m.deleted = true, m.updated_at = $now
            """,
            {"memory_id": memory_id, "now": datetime.now().isoformat()},
        )

    def hard_delete_memory(self, memory_id: str) -> None:
        """Actually remove Memory node and its relationships from the graph."""
        if not self._enabled or not memory_id:
            return
        self._run_write(
            "MATCH (m:Memory {id: $memory_id}) DETACH DELETE m",
            {"memory_id": memory_id},
        )

        # Delete orphan entities: no other Memory has CONTAINS_ENTITY to them
        if not entity_ids:
            return
        placeholders = ", ".join([f"$id{i}" for i in range(len(entity_ids))])
        params = {f"id{i}": eid for i, eid in enumerate(entity_ids)}
        self._run_write(
            f"""
            MATCH (e:Entity)
            WHERE e.id IN [{placeholders}]
              AND NOT (e)<-[:CONTAINS_ENTITY]-(:Memory)
            DETACH DELETE e
            """,
            params,
        )

    def expand_from_entities(
        self,
        entity_ids: List[str],
        user_id: Optional[str] = None,
        depth: int = 1,
        space_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Traverse graph from given entity ids. Returns related entities, memories, user context.
        Used for retrieval: Qdrant returns memory_ids → Neo4j expands with graph context.
        Optional space_ids: filter memories to global (no IN_SPACE) or IN_SPACE to one of space_ids.
        When None, no space filter (return all user-visible memories).

        TODO: depth is not yet used; traversal is currently one hop only.
        """
        if not self._enabled or not entity_ids:
            return {"entities": [], "memories": [], "user_facts": []}
        rel_types = "|".join(sorted(ENTITY_REL_TYPES) + ["RELATED_TO"])
        placeholders = ", ".join([f"$id{i}" for i in range(len(entity_ids))])
        params = {f"id{i}": eid for i, eid in enumerate(entity_ids)}
        params["user_id"] = user_id or ""

        if user_id:
            memory_match = "OPTIONAL MATCH (u:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory)-[:CONTAINS_ENTITY]->(e) WHERE m.deleted IS NULL OR m.deleted = false"
        else:
            memory_match = "OPTIONAL MATCH (m:Memory)-[:CONTAINS_ENTITY]->(e) WHERE m.deleted IS NULL OR m.deleted = false"

        space_filter = ""
        if space_ids:
            params["space_ids"] = space_ids
            space_filter = """
            OPTIONAL MATCH (m)-[:IN_SPACE]->(sp:Space)
            WITH e, related, m, sp
            WHERE m IS NULL OR sp IS NULL OR sp.space_id IN $space_ids
            WITH e, related, m
            """

        query = f"""
            MATCH (e:Entity)
            WHERE e.id IN [{placeholders}]
            OPTIONAL MATCH (e)-[:{rel_types}]-(other:Entity)
            WITH e, collect(DISTINCT other) AS related
            {memory_match}
            {space_filter}
            WITH e, related, m
            ORDER BY m.created_at DESC
            WITH e, related, collect(m.id) AS memory_ids_raw
            RETURN e.id AS id, e.type AS type, e.name AS name,
                   [x IN related WHERE x IS NOT NULL | {{id: x.id, type: x.type, name: x.name}}] AS related_entities,
                   [mid IN memory_ids_raw WHERE mid IS NOT NULL] AS memory_ids
            """
        records = self._run_query(query, params)

        # Preserve entity order to keep results stable across runs.
        input_order = {eid: idx for idx, eid in enumerate(entity_ids)}
        records.sort(key=lambda r: input_order.get(r.get("id"), 10**9))

        entities: List[Dict[str, Any]] = []
        ordered_memory_ids: List[str] = []
        seen_mem: Set[str] = set()

        for r in records:
            entities.append({
                "id": r.get("id"),
                "type": r.get("type"),
                "name": r.get("name"),
                "related": r.get("related_entities", []),
            })
            for mid in (r.get("memory_ids") or []):
                if mid and mid not in seen_mem:
                    seen_mem.add(mid)
                    ordered_memory_ids.append(mid)

        user_facts: List[Dict[str, Any]] = []
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
            "memory_ids": ordered_memory_ids,
            "user_facts": user_facts,
        }

    def get_user_facts_for_retrieval(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Return all user–entity facts (LIVES_IN, WORKS_AT, KNOWS, PREFERS) for the user.
        Used to always include user facts in memory context when KG is enabled.
        """
        if not self._enabled or not user_id:
            return []
        return self._run_query(
            """
            MATCH (u:User {user_id: $user_id})-[r:LIVES_IN|WORKS_AT|KNOWS|PREFERS]->(e:Entity)
            RETURN type(r) AS rel_type, e.id AS entity_id, e.name AS name, e.type AS type
            """,
            {"user_id": user_id},
        )

    def get_entities_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all entities in the user's graph (from their memories)."""
        if not self._enabled or not user_id:
            return []
        records = self._run_query(
            """
            MATCH (u:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory)-[:CONTAINS_ENTITY]->(e:Entity)
            WHERE m.deleted IS NULL OR m.deleted = false
            RETURN DISTINCT e.id AS id, e.type AS type, e.name AS name
            """,
            {"user_id": user_id},
        )
        return records

    def get_facts_for_user(
        self,
        user_id: str,
        space_id: Optional[str] = None,
        space_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get Facts for a user. Phase 3B: optional space filter.
        When space_id/space_ids provided: return global facts (space_id null) + facts in requested space(s).
        When None: return all facts (backward compat).
        """
        if not self._enabled or not user_id:
            return []
        space_filter = ""
        params: Dict[str, Any] = {"user_id": user_id}
        if space_ids:
            params["space_ids"] = [s for s in space_ids if s and s != SPACE_ID_GLOBAL]
            params["global_sentinel"] = SPACE_ID_GLOBAL
            if params["space_ids"]:
                space_filter = """
                WHERE (f.space_id IS NULL OR f.space_id = $global_sentinel OR f.space_id IN $space_ids)
                """
        elif space_id and space_id != SPACE_ID_GLOBAL:
            params["space_ids"] = [space_id]
            params["global_sentinel"] = SPACE_ID_GLOBAL
            space_filter = """
            WHERE (f.space_id IS NULL OR f.space_id = $global_sentinel OR f.space_id IN $space_ids)
            """
        records = self._run_query(
            """
            MATCH (u:User {user_id: $user_id})-[:HAS_FACT]->(f:Fact)
            """ + space_filter + """
            RETURN properties(f) AS props
            """,
            params,
        )
        out = []
        for r in records:
            p = r.get("props") or {}
            vt = (p.get("value_type") or "text").lower()
            if vt == "number":
                val = p.get("value_number")
            elif vt == "bool":
                val = p.get("value_bool")
            elif vt == "json" and p.get("value_json") is not None:
                try:
                    vj = p["value_json"]
                    val = json.loads(vj) if isinstance(vj, str) else vj
                except Exception:
                    val = p.get("value_json")
            else:
                val = p.get("value_text")
            out.append({
                "namespace": p.get("namespace") or "",
                "key": p.get("key") or "",
                "value_type": p.get("value_type") or "text",
                "value_text": p.get("value_text"),
                "value_number": p.get("value_number"),
                "value_bool": p.get("value_bool"),
                "value_json": val if vt == "json" else None,
                "value": val,
                "confidence": float(p.get("confidence") or 0),
                "last_seen_at": p.get("last_seen_at"),
            })
        return out

    def backfill_value_preview_for_user(self, user_id: str) -> int:
        """
        Set value_preview on Facts that lack it (e.g. created before value_preview existed).
        Returns count of Facts updated.
        """
        if not self._enabled or not user_id:
            return 0
        records = self._run_query(
            """
            MATCH (u:User {user_id: $user_id})-[:HAS_FACT]->(f:Fact)
            WHERE f.value_preview IS NULL
            RETURN properties(f) AS props
            """,
            {"user_id": user_id},
        )
        updated = 0
        for r in records:
            p = r.get("props") or {}
            ns = p.get("namespace") or ""
            key = p.get("key") or ""
            if not ns or not key:
                continue
            vt = (p.get("value_type") or "text").lower()
            if vt == "number":
                val = p.get("value_number")
            elif vt == "bool":
                val = p.get("value_bool")
            elif vt == "json" and p.get("value_json") is not None:
                try:
                    vj = p["value_json"]
                    val = json.loads(vj) if isinstance(vj, str) else vj
                except Exception:
                    val = p.get("value_json")
            else:
                val = p.get("value_text")
            if val is None:
                continue
            preview: Optional[str] = None
            if vt == "text":
                preview = str(val)[:200]
            elif vt == "number":
                preview = str(val)
            elif vt == "bool":
                preview = str(val)
            elif vt == "json" and isinstance(val, list) and val:
                strs_ = [str(x) for x in val[:10] if x is not None and str(x).strip().lower() != "null"]
                preview = ", ".join(strs_)[:200] if strs_ else None
            elif vt == "json" and isinstance(val, dict):
                preview = json.dumps(val)[:200]
            if not preview:
                continue
            self._run_write(
                """
                MATCH (f:Fact {user_id: $user_id, namespace: $namespace, key: $key})
                SET f.value_preview = $preview
                """,
                {"user_id": user_id, "namespace": ns, "key": key, "preview": preview},
            )
            updated += 1
        return updated

    def get_evidence_count_for_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get evidence summary for a user (counts of Evidence linked to user's Facts).
        Returns dict with total_events, events_by_source, events_by_type for adapter.
        """
        if not self._enabled or not user_id:
            return {"total_events": 0, "events_by_source": {}, "events_by_type": {}}
        records = self._run_query(
            """
            MATCH (u:User {user_id: $user_id})-[:HAS_FACT]->(f:Fact)-[:SUPPORTED_BY]->(ev:Evidence)
            RETURN ev.source_type AS source_type, count(ev) AS cnt
            """,
            {"user_id": user_id},
        )
        total = sum(r.get("cnt", 0) for r in records)
        by_type = {r.get("source_type") or "unknown": r.get("cnt", 0) for r in records}
        return {
            "total_events": total,
            "events_by_source": {},
            "events_by_type": by_type,
        }

    def resolve_entity_candidates(
        self,
        user_id: str,
        candidates: List[Dict[str, str]],
        fuzzy_threshold: float = 0.85,
    ) -> List[str]:
        """
        Resolve NER-extracted candidates against the graph.
        Lookup order: exact match (type+name), then fuzzy (threshold default 0.85).
        Fuzzy stage: try within-type first, then global fallback so wrong NER type
        (e.g. "John" as Concept when graph has Person) can still match.
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
            # 2. Fuzzy match: within-type first, then global fallback (cross-type)
            best_score = 0
            best_id: Optional[str] = None
            candidates_fuzzy = by_type.get(ctype, []) + all_names
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
        space_ids: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Fallback: find memory ids by raw name tokens.
        Optional space_ids: filter to global or in-space memories.
        """
        if not self._enabled or not names:
            return []
        names_lower = [n.strip().lower() for n in names if n and n.strip()]
        if not names_lower:
            return []
        if space_ids:
            records = self._run_query(
                """
                MATCH (u:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory)-[:CONTAINS_ENTITY]->(e:Entity)
                OPTIONAL MATCH (m)-[:IN_SPACE]->(sp:Space)
                WHERE (ANY(n IN $names_lower WHERE toLower(e.name) = n OR toLower(e.name) CONTAINS n))
                  AND (sp IS NULL OR sp.space_id IN $space_ids)
                  AND (m.deleted IS NULL OR m.deleted = false)
                RETURN DISTINCT m.id AS memory_id
                """,
                {"user_id": user_id, "names_lower": names_lower, "space_ids": space_ids},
            )
        else:
            records = self._run_query(
                """
                MATCH (u:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory)-[:CONTAINS_ENTITY]->(e:Entity)
                WHERE (ANY(n IN $names_lower WHERE toLower(e.name) = n OR toLower(e.name) CONTAINS n))
                  AND (m.deleted IS NULL OR m.deleted = false)
                RETURN DISTINCT m.id AS memory_id
                """,
                {"user_id": user_id, "names_lower": names_lower},
            )
        return [r["memory_id"] for r in records if r.get("memory_id")]

    def get_subgraph_for_explore(
        self,
        user_id: str,
        space_id: Optional[str] = None,
        limit: int = 150,
    ) -> Dict[str, Any]:
        """
        Return nodes and edges for the knowledge graph explorer UI.
        Includes: Entity nodes, User node, Memory nodes;
        Entity-Entity (no self-loops), User-Entity, Memory-Entity edges.
        Scoped by user's memories; optionally filtered by space_id.
        Returns { "nodes": [ { id, label, type, nodeKind } ], "edges": [ { source, target, type } ] }.
        """
        if not self._enabled or not user_id:
            return {"nodes": [], "edges": []}

        # Build space filter: when space_id is set and not global, restrict to that space
        space_filter = ""
        params: Dict[str, Any] = {"user_id": user_id, "limit": limit}
        if space_id and space_id != SPACE_ID_GLOBAL:
            params["space_id"] = space_id
            space_filter = """
            MATCH (m)-[:IN_SPACE]->(sp:Space {space_id: $space_id})
            """

        rel_types = "|".join(sorted(ENTITY_REL_TYPES) + ["RELATED_TO"])

        entity_query = f"""
            MATCH (u:User {{user_id: $user_id}})-[:HAS_MEMORY]->(m:Memory)
            WHERE m.deleted IS NULL OR m.deleted = false
            {space_filter}
            MATCH (m)-[:CONTAINS_ENTITY]->(e:Entity)
            WITH DISTINCT e
            LIMIT $limit
            RETURN e.id AS id, e.type AS type, e.name AS name
            """
        entities = self._run_query(entity_query, params)
        entity_ids = [e["id"] for e in entities if e.get("id")]

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        # 1. Entity nodes
        for e in entities:
            nodes.append({
                "id": e["id"],
                "label": e.get("name") or e["id"],
                "type": e.get("type") or "Entity",
                "nodeKind": "entity",
            })

        if not entity_ids:
            # Still add User node for empty graph
            nodes.append({"id": "__user__", "label": "You", "type": "User", "nodeKind": "user"})
            return {"nodes": nodes, "edges": []}

        placeholders = ", ".join([f"$id{i}" for i in range(len(entity_ids))])
        params2 = {f"id{i}": eid for i, eid in enumerate(entity_ids)}
        params2["user_id"] = user_id
        params2["rel_list"] = rel_types.split("|")
        params2["user_rel_list"] = list(USER_ENTITY_REL_TYPES)

        # 2. Entity-Entity edges (exclude self-loops)
        ee_query = f"""
            MATCH (a:Entity)-[r]->(b:Entity)
            WHERE a.id IN [{placeholders}] AND b.id IN [{placeholders}]
              AND a.id <> b.id
              AND type(r) IN $rel_list
            RETURN a.id AS source, b.id AS target, type(r) AS type
            """
        for r in self._run_query(ee_query, params2):
            if r.get("source") and r.get("target"):
                edges.append({"source": r["source"], "target": r["target"], "type": r.get("type") or "RELATED_TO"})

        # 3. User node + User-Entity edges
        nodes.append({"id": "__user__", "label": "You", "type": "User", "nodeKind": "user"})
        ue_query = f"""
            MATCH (u:User {{user_id: $user_id}})-[r]->(e:Entity)
            WHERE e.id IN [{placeholders}] AND type(r) IN $user_rel_list
            RETURN e.id AS target, type(r) AS type
            """
        for r in self._run_query(ue_query, params2):
            if r.get("target"):
                edges.append({"source": "__user__", "target": r["target"], "type": r.get("type") or "KNOWS"})

        # 4. Memory nodes + Memory-Entity (CONTAINS_ENTITY) edges
        params3: Dict[str, Any] = {"user_id": user_id, "mem_limit": min(80, limit)}
        mem_space_filter = ""
        if space_id and space_id != SPACE_ID_GLOBAL:
            params3["space_id"] = space_id
            mem_space_filter = "\n            MATCH (m)-[:IN_SPACE]->(sp:Space {space_id: $space_id})"
        mem_query = f"""
            MATCH (u:User {{user_id: $user_id}})-[:HAS_MEMORY]->(m:Memory)-[:CONTAINS_ENTITY]->(e:Entity)
            WHERE m.deleted IS NULL OR m.deleted = false
            {mem_space_filter}
            WITH m, e
            ORDER BY m.created_at DESC
            WITH m, collect(DISTINCT e.id) AS entity_ids
            WITH DISTINCT m
            LIMIT $mem_limit
            RETURN m.id AS id
            """
        memories = self._run_query(mem_query, params3)
        mem_ids = [r["id"] for r in memories if r.get("id")]
        seen_mem: Set[str] = set()
        for m in memories:
            mid = m.get("id")
            if mid and mid not in seen_mem:
                seen_mem.add(mid)
                short_id = str(mid)[:8] + "…" if len(str(mid)) > 8 else str(mid)
                nodes.append({
                    "id": mid,
                    "label": f"Mem {short_id}",
                    "type": "Memory",
                    "nodeKind": "memory",
                })

        if mem_ids:
            mem_ph = ", ".join([f"$mid{i}" for i in range(len(mem_ids))])
            params4 = {f"mid{i}": mid for i, mid in enumerate(mem_ids)}
            params4["eids"] = entity_ids
            me_query = f"""
                MATCH (m:Memory)-[:CONTAINS_ENTITY]->(e:Entity)
                WHERE m.id IN [{mem_ph}] AND e.id IN $eids
                  AND (m.deleted IS NULL OR m.deleted = false)
                RETURN m.id AS source, e.id AS target
                """
            for r in self._run_query(me_query, params4):
                if r.get("source") and r.get("target"):
                    edges.append({"source": r["source"], "target": r["target"], "type": "CONTAINS_ENTITY"})

        return {"nodes": nodes, "edges": edges}


# Singleton for app use
_kg: Optional[KnowledgeGraph] = None


def get_knowledge_graph():
    """Get or create KnowledgeGraph singleton.

    Tries Neo4j first.  When Neo4j is unavailable (not installed, wrong
    password, service down) falls back to a pure-Python NetworkX backend
    that persists to ``data/knowledge_graph_nx.json``.  Returns ``None``
    only when ``NEO4J_ENABLED`` is explicitly false.
    """
    global _kg
    if _kg is not None:
        return _kg if _kg.enabled else _kg  # already resolved

    # Attempt Neo4j
    _kg = KnowledgeGraph()
    if _kg.enabled:
        return _kg

    # Fallback: NetworkX backend (if Neo4j was requested but unavailable)
    if _is_neo4j_enabled():
        try:
            from memory.knowledge_graph_nx import NetworkXKnowledgeGraph
            _kg = NetworkXKnowledgeGraph()  # type: ignore[assignment]
            logger.debug("KnowledgeGraph: Using NetworkX fallback (Neo4j unreachable)")
            return _kg
        except Exception as exc:
            logger.debug("KnowledgeGraph: NetworkX fallback failed: %s", exc)

    return None
