"""
NetworkX Knowledge Graph — Drop-in replacement for Neo4j KnowledgeGraph.

Pure Python, zero infrastructure. Persists to a JSON file on disk.
Provides the same public interface so the graph router, Qdrant store,
and memory retriever work without Neo4j installed.

Enable via NEO4J_ENABLED=true (uses NX automatically when Neo4j is unreachable).
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from memory.space_constants import SPACE_ID_GLOBAL

# Entity-to-entity relationship types (same as Neo4j version)
ENTITY_REL_TYPES = frozenset({
    "WORKS_AT", "LOCATED_IN", "MET", "MET_AT", "OWNS", "PART_OF",
    "MEMBER_OF", "KNOWS", "EMPLOYED_BY", "LIVES_IN", "BASED_IN",
})

USER_ENTITY_REL_TYPES = frozenset({"LIVES_IN", "WORKS_AT", "KNOWS", "PREFERS"})

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

_DATA_DIR = Path(__file__).parent.parent / "data"
_GRAPH_FILE = _DATA_DIR / "knowledge_graph_nx.json"


def _canonical_name(name: str) -> str:
    if not name or not isinstance(name, str):
        return ""
    return name.strip().lower()


def _normalize_rel_type(raw: str) -> str:
    upper = raw.strip().upper().replace(" ", "_")
    return upper if upper in ENTITY_REL_TYPES else "RELATED_TO"


class NetworkXKnowledgeGraph:
    """
    NetworkX-backed knowledge graph with JSON persistence.
    API-compatible with KnowledgeGraph (Neo4j version).
    """

    def __init__(self) -> None:
        self._graph = nx.MultiDiGraph()
        self._lock = threading.Lock()
        self._enabled = True
        # composite_key -> entity_id for dedup
        self._entity_index: Dict[str, str] = {}
        self._load()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def close(self) -> None:
        self._save()

    # ── Persistence ──────────────────────────────────────────────

    def _load(self) -> None:
        if not _GRAPH_FILE.exists():
            return
        try:
            with open(_GRAPH_FILE) as f:
                data = json.load(f)
            g = self._graph
            for n in data.get("nodes", []):
                nid = n.pop("id")
                g.add_node(nid, **n)
            for e in data.get("edges", []):
                g.add_edge(e["source"], e["target"], key=e.get("key", 0), **{
                    k: v for k, v in e.items() if k not in ("source", "target", "key")
                })
            self._entity_index = data.get("entity_index", {})
        except Exception:
            pass  # start fresh if corrupt

    def _save(self) -> None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        g = self._graph
        nodes = []
        for nid, attrs in g.nodes(data=True):
            nodes.append({"id": nid, **attrs})
        edges = []
        for u, v, k, attrs in g.edges(data=True, keys=True):
            edges.append({"source": u, "target": v, "key": k, **attrs})
        with open(_GRAPH_FILE, "w") as f:
            json.dump({
                "nodes": nodes,
                "edges": edges,
                "entity_index": self._entity_index,
            }, f, default=str)

    def _auto_save(self) -> None:
        """Save after mutations (debounced by caller if needed)."""
        self._save()

    # ── Node helpers ─────────────────────────────────────────────

    def _ensure_user(self, user_id: str) -> None:
        if user_id and not self._graph.has_node(user_id):
            self._graph.add_node(user_id, kind="User", user_id=user_id)

    def _ensure_session(self, session_id: str) -> None:
        if session_id and not self._graph.has_node(session_id):
            self._graph.add_node(session_id, kind="Session", session_id=session_id)

    def _ensure_space(self, space_id: str) -> None:
        if space_id and space_id != SPACE_ID_GLOBAL:
            sid = f"space::{space_id}"
            if not self._graph.has_node(sid):
                self._graph.add_node(sid, kind="Space", space_id=space_id)

    # ── Public API (compatible with Neo4j KnowledgeGraph) ────────

    def get_or_create_entity(self, entity_type: str, name: str) -> str:
        etype = (entity_type or "Concept").strip()
        canonical = _canonical_name(name)
        composite_key = f"{etype.lower()}::{canonical}"
        if composite_key in self._entity_index:
            return self._entity_index[composite_key]
        eid = str(uuid.uuid4())
        self._entity_index[composite_key] = eid
        self._graph.add_node(eid, kind="Entity", type=etype, name=name.strip(),
                             canonical_name=canonical, composite_key=composite_key)
        return eid

    def link_memory_to_entity(self, memory_id: str, entity_id: str) -> None:
        if self._graph.has_node(memory_id) and self._graph.has_node(entity_id):
            # Avoid duplicate edges
            for _, _, d in self._graph.edges(memory_id, data=True):
                if d.get("rel_type") == "CONTAINS_ENTITY" and _ == entity_id:
                    return
            self._graph.add_edge(memory_id, entity_id, rel_type="CONTAINS_ENTITY")

    def get_entities_for_memory(self, memory_id: str) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        result = []
        for _, target, data in self._graph.edges(memory_id, data=True):
            if data.get("rel_type") == "CONTAINS_ENTITY":
                nd = self._graph.nodes.get(target, {})
                if nd.get("kind") == "Entity":
                    result.append({"id": target, "type": nd.get("type", ""), "name": nd.get("name", "")})
        return result

    def create_memory(
        self,
        memory_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        category: str = "general",
        source: str = "manual",
        space_id: Optional[str] = None,
    ) -> None:
        if not self._enabled:
            return
        self._graph.add_node(memory_id, kind="Memory", category=category, source=source,
                             created_at=datetime.now(timezone.utc).isoformat())
        if user_id:
            self._ensure_user(user_id)
            self._graph.add_edge(user_id, memory_id, rel_type="HAS_MEMORY")
        if session_id:
            self._ensure_session(session_id)
            self._graph.add_edge(memory_id, session_id, rel_type="FROM_SESSION")
        if space_id and space_id != SPACE_ID_GLOBAL:
            self._ensure_space(space_id)
            self._graph.add_edge(memory_id, f"space::{space_id}", rel_type="IN_SPACE")

    def create_entity_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str = "RELATED_TO",
        value: Any = None,
        confidence: float = 1.0,
        source_memory_ids: Optional[List[str]] = None,
    ) -> None:
        if not self._enabled:
            return
        rt = _normalize_rel_type(rel_type)
        self._graph.add_edge(from_id, to_id, rel_type=rt, value=value,
                             confidence=confidence, source_memory_ids=source_memory_ids or [])

    def create_user_entity_relationship(
        self,
        user_id: str,
        entity_id: str,
        rel_type: str = "KNOWS",
        confidence: float = 1.0,
        source_memory_ids: Optional[List[str]] = None,
    ) -> None:
        if not self._enabled:
            return
        rt = rel_type.upper() if rel_type.upper() in USER_ENTITY_REL_TYPES else "KNOWS"
        self._ensure_user(user_id)
        self._graph.add_edge(user_id, entity_id, rel_type=rt, confidence=confidence,
                             source_memory_ids=source_memory_ids or [])

    def delete_memory(self, memory_id: str) -> None:
        if not self._enabled or not memory_id or not self._graph.has_node(memory_id):
            return
        with self._lock:
            # Find entities only linked to this memory
            entity_ids = [t for _, t, d in self._graph.edges(memory_id, data=True)
                          if d.get("rel_type") == "CONTAINS_ENTITY"]
            self._graph.remove_node(memory_id)
            # Remove orphan entities
            for eid in entity_ids:
                if not self._graph.has_node(eid):
                    continue
                has_other = any(
                    d.get("rel_type") == "CONTAINS_ENTITY"
                    for _, _, d in self._graph.in_edges(eid, data=True)
                )
                if not has_other:
                    ck = self._graph.nodes[eid].get("composite_key")
                    if ck and ck in self._entity_index:
                        del self._entity_index[ck]
                    self._graph.remove_node(eid)
            self._auto_save()

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
        empty_result: Dict[str, Any] = {"entity_ids": [], "entity_labels": []}
        if not self._enabled or not user_id:
            return empty_result

        with self._lock:
            self.create_memory(memory_id, user_id, session_id, category, source, space_id=space_id)
            entity_ids: List[str] = []
            entity_labels: List[Dict[str, str]] = []
            entity_map: Dict[Tuple[str, str], str] = {}

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
                        from_id, to_id,
                        rel_type=rel.get("type", "related_to"),
                        value=rel.get("value"),
                        confidence=rel.get("confidence", 1.0),
                        source_memory_ids=[memory_id],
                    )

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
                    user_id, entity_map[key], rel_type, source_memory_ids=[memory_id],
                )

            # Fact nodes (simplified — store as node attributes)
            for f in facts or []:
                ns = f.get("namespace", "")
                k = f.get("key", "")
                if not ns or not k:
                    continue
                fact_id = f"fact::{user_id}::{ns}::{k}"
                fact_space = space_id if space_id and space_id != SPACE_ID_GLOBAL else None
                self._graph.add_node(fact_id, kind="Fact", namespace=ns, key=k,
                                     value_type=f.get("value_type", "text"),
                                     value_text=f.get("value_text") or str(f.get("value", "")),
                                     confidence=f.get("confidence", 0.8),
                                     space_id=fact_space,
                                     updated_at=datetime.now(timezone.utc).isoformat())
                self._graph.add_edge(user_id, fact_id, rel_type="HAS_FACT")

                # Derive user-entity edge from fact
                entity_ref = f.get("entity_ref")
                if entity_ref:
                    ref_key = ("concept", _canonical_name(entity_ref))
                    ref_eid = entity_map.get(ref_key)
                    if ref_eid:
                        self._graph.add_edge(fact_id, ref_eid, rel_type="REFERS_TO")
                        # Derive user-entity relationship
                        for prefix, kp, rt in FACT_DERIVATION_TABLE:
                            if ns.startswith(prefix) and (kp == "*" or kp == k):
                                self.create_user_entity_relationship(
                                    user_id, ref_eid, rt, source_memory_ids=[memory_id],
                                )
                                break

            self._auto_save()

        return {"entity_ids": entity_ids, "entity_labels": entity_labels}

    def get_subgraph_for_explore(
        self,
        user_id: str,
        space_id: Optional[str] = None,
        limit: int = 150,
    ) -> Dict[str, Any]:
        if not self._enabled or not user_id:
            return {"nodes": [], "edges": []}

        g = self._graph

        # Resolve effective user_id — if the given user has no memories,
        # fall back to the first (only) User node in the graph.
        # This handles guest_id mismatches in single-user local deployments.
        effective_uid = user_id
        if not g.has_node(user_id) or not any(
            d.get("rel_type") == "HAS_MEMORY"
            for _, _, d in g.edges(user_id, data=True)
        ):
            for nid, nd in g.nodes(data=True):
                if nd.get("kind") == "User":
                    effective_uid = nid
                    break

        # Find user's memory ids
        memory_ids: List[str] = []
        for _, target, data in g.edges(effective_uid, data=True):
            if data.get("rel_type") == "HAS_MEMORY":
                nd = g.nodes.get(target, {})
                if nd.get("kind") == "Memory" and not nd.get("deleted"):
                    # Space filter
                    if space_id and space_id != SPACE_ID_GLOBAL:
                        in_space = any(
                            d.get("rel_type") == "IN_SPACE"
                            for _, t, d in g.edges(target, data=True)
                            if g.nodes.get(t, {}).get("space_id") == space_id
                        )
                        if not in_space:
                            continue
                    memory_ids.append(target)

        # Collect entities from those memories
        entity_ids: Set[str] = set()
        mem_entity_edges: List[Tuple[str, str]] = []
        for mid in memory_ids:
            for _, target, data in g.edges(mid, data=True):
                if data.get("rel_type") == "CONTAINS_ENTITY":
                    entity_ids.add(target)
                    mem_entity_edges.append((mid, target))
                    if len(entity_ids) >= limit:
                        break
            if len(entity_ids) >= limit:
                break

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        # 1. Entity nodes
        for eid in entity_ids:
            nd = g.nodes.get(eid, {})
            nodes.append({
                "id": eid,
                "label": nd.get("name") or eid,
                "type": nd.get("type") or "Entity",
                "nodeKind": "entity",
            })

        # 2. User node
        nodes.append({"id": "__user__", "label": "You", "type": "User", "nodeKind": "user"})

        if not entity_ids:
            return {"nodes": nodes, "edges": []}

        # 3. Entity-Entity edges (no self-loops)
        for eid in entity_ids:
            for _, target, data in g.edges(eid, data=True):
                rt = data.get("rel_type", "")
                if target in entity_ids and target != eid and (rt in ENTITY_REL_TYPES or rt == "RELATED_TO"):
                    edges.append({"source": eid, "target": target, "type": rt})

        # 4. User-Entity edges
        for _, target, data in g.edges(effective_uid, data=True):
            rt = data.get("rel_type", "")
            if target in entity_ids and rt in USER_ENTITY_REL_TYPES:
                edges.append({"source": "__user__", "target": target, "type": rt})

        # 5. Memory nodes + Memory-Entity edges (limited)
        mem_limit = min(80, limit)
        seen_mems: Set[str] = set()
        for mid, eid in mem_entity_edges:
            if mid in seen_mems:
                # Still add edge
                if eid in entity_ids:
                    edges.append({"source": mid, "target": eid, "type": "CONTAINS_ENTITY"})
                continue
            if len(seen_mems) >= mem_limit:
                continue
            seen_mems.add(mid)
            short_id = mid[:8] + "…" if len(mid) > 8 else mid
            nodes.append({
                "id": mid,
                "label": f"Mem {short_id}",
                "type": "Memory",
                "nodeKind": "memory",
            })
            if eid in entity_ids:
                edges.append({"source": mid, "target": eid, "type": "CONTAINS_ENTITY"})

        return {"nodes": nodes, "edges": edges}

    def expand_from_entities(
        self,
        entity_ids: List[str],
        user_id: Optional[str] = None,
        depth: int = 1,
        space_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not self._enabled or not entity_ids:
            return {"entities": [], "memories": [], "user_facts": []}

        g = self._graph
        related_entities: List[Dict[str, Any]] = []
        memory_ids: Set[str] = set()
        eid_set = set(entity_ids)

        for eid in entity_ids:
            if not g.has_node(eid):
                continue
            nd = g.nodes[eid]
            related_entities.append({"id": eid, "type": nd.get("type", ""), "name": nd.get("name", "")})

            # Find neighbors
            for _, target, data in g.edges(eid, data=True):
                tnd = g.nodes.get(target, {})
                rt = data.get("rel_type", "")
                if tnd.get("kind") == "Entity" and target not in eid_set:
                    related_entities.append({"id": target, "type": tnd.get("type", ""), "name": tnd.get("name", "")})
                    eid_set.add(target)

            # Find memories containing this entity (reverse edges)
            for source, _, data in g.in_edges(eid, data=True):
                if data.get("rel_type") == "CONTAINS_ENTITY":
                    snd = g.nodes.get(source, {})
                    if snd.get("kind") == "Memory" and not snd.get("deleted"):
                        if space_ids:
                            in_scope = any(
                                g.nodes.get(t, {}).get("space_id") in space_ids
                                for _, t, d in g.edges(source, data=True)
                                if d.get("rel_type") == "IN_SPACE"
                            ) or not any(
                                d.get("rel_type") == "IN_SPACE"
                                for _, _, d in g.edges(source, data=True)
                            )
                            if not in_scope:
                                continue
                        memory_ids.add(source)

        memories = [{"id": mid} for mid in memory_ids]
        user_facts = self.get_user_facts_for_retrieval(user_id) if user_id else []

        return {"entities": related_entities, "memories": memories, "user_facts": user_facts}

    def get_user_facts_for_retrieval(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._enabled or not user_id:
            return []
        g = self._graph
        facts = []
        for _, target, data in g.edges(user_id, data=True):
            rt = data.get("rel_type", "")
            if rt in USER_ENTITY_REL_TYPES:
                nd = g.nodes.get(target, {})
                if nd.get("kind") == "Entity":
                    facts.append({"rel_type": rt, "name": nd.get("name", ""), "type": nd.get("type", "")})
        return facts

    def get_facts_for_user(
        self,
        user_id: str,
        space_id: Optional[str] = None,
        space_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not self._enabled or not user_id:
            return []
        g = self._graph
        result = []
        all_spaces = set(space_ids or [])
        if space_id:
            all_spaces.add(space_id)

        for _, target, data in g.edges(user_id, data=True):
            if data.get("rel_type") == "HAS_FACT":
                nd = g.nodes.get(target, {})
                if nd.get("kind") != "Fact":
                    continue
                fact_space = nd.get("space_id")
                if all_spaces:
                    # Include global facts (no space) + facts in requested spaces
                    if fact_space and fact_space not in all_spaces:
                        continue
                result.append({
                    "namespace": nd.get("namespace", ""),
                    "key": nd.get("key", ""),
                    "value_type": nd.get("value_type", "text"),
                    "value_text": nd.get("value_text"),
                    "confidence": nd.get("confidence", 0.8),
                    "space_id": fact_space,
                })
        return result

    def resolve_entity_candidates(
        self,
        user_id: str,
        candidates: List[Dict[str, str]],
        fuzzy_threshold: float = 0.85,
    ) -> List[str]:
        if not self._enabled or not candidates:
            return []
        g = self._graph
        # Collect all user's entities
        user_entities: Dict[str, Dict[str, Any]] = {}
        for _, target, data in g.edges(user_id, data=True):
            if data.get("rel_type") == "HAS_MEMORY":
                for _, eid, ed in g.edges(target, data=True):
                    if ed.get("rel_type") == "CONTAINS_ENTITY":
                        nd = g.nodes.get(eid, {})
                        if nd.get("kind") == "Entity":
                            user_entities[eid] = nd

        matched: List[str] = []
        for cand in candidates:
            cname = _canonical_name(cand.get("name", ""))
            ctype = (cand.get("type") or "").strip().lower()
            if not cname:
                continue
            # Exact match
            for eid, nd in user_entities.items():
                if nd.get("canonical_name") == cname:
                    if not ctype or nd.get("type", "").lower() == ctype:
                        matched.append(eid)
                        break
            else:
                # Fuzzy match
                for eid, nd in user_entities.items():
                    ratio = SequenceMatcher(None, cname, nd.get("canonical_name", "")).ratio()
                    if ratio >= fuzzy_threshold:
                        matched.append(eid)
                        break
        return matched

    def get_memory_ids_for_entity_names(
        self,
        user_id: str,
        names: List[str],
        space_ids: Optional[List[str]] = None,
    ) -> List[str]:
        if not self._enabled or not names:
            return []
        g = self._graph
        canonical_names = {_canonical_name(n) for n in names if n}
        # Find entities matching names
        matching_eids: Set[str] = set()
        for nid, nd in g.nodes(data=True):
            if nd.get("kind") == "Entity" and nd.get("canonical_name") in canonical_names:
                matching_eids.add(nid)

        # Find memories containing those entities
        memory_ids: Set[str] = set()
        for eid in matching_eids:
            for source, _, data in g.in_edges(eid, data=True):
                if data.get("rel_type") == "CONTAINS_ENTITY":
                    snd = g.nodes.get(source, {})
                    if snd.get("kind") == "Memory" and not snd.get("deleted"):
                        # Verify memory belongs to user
                        for u, _, ud in g.in_edges(source, data=True):
                            if ud.get("rel_type") == "HAS_MEMORY" and g.nodes.get(u, {}).get("user_id") == user_id:
                                if space_ids:
                                    in_scope = any(
                                        g.nodes.get(t, {}).get("space_id") in space_ids
                                        for _, t, d in g.edges(source, data=True)
                                        if d.get("rel_type") == "IN_SPACE"
                                    ) or not any(
                                        d.get("rel_type") == "IN_SPACE"
                                        for _, _, d in g.edges(source, data=True)
                                    )
                                    if not in_scope:
                                        continue
                                memory_ids.add(source)
        return list(memory_ids)

    def get_entities_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        if not self._enabled or not user_id:
            return []
        g = self._graph
        entity_set: Set[str] = set()
        result = []
        for _, mid, data in g.edges(user_id, data=True):
            if data.get("rel_type") != "HAS_MEMORY":
                continue
            for _, eid, ed in g.edges(mid, data=True):
                if ed.get("rel_type") == "CONTAINS_ENTITY" and eid not in entity_set:
                    entity_set.add(eid)
                    nd = g.nodes.get(eid, {})
                    result.append({"id": eid, "type": nd.get("type", ""), "name": nd.get("name", "")})
        return result

    def get_evidence_count_for_user(self, user_id: str) -> Dict[str, Any]:
        """Stub for NetworkX fallback — no Evidence nodes in the in-memory graph."""
        return {"total_events": 0, "events_by_source": {}, "events_by_type": {}}

    # Space management (lightweight)
    def create_space(self, space_id: str, **kwargs: Any) -> None:
        self._ensure_space(space_id)
        self._auto_save()

    def delete_space(self, space_id: str) -> None:
        sid = f"space::{space_id}"
        if self._graph.has_node(sid):
            self._graph.remove_node(sid)
            self._auto_save()

    def get_spaces(self, user_id: str) -> List[Dict[str, Any]]:
        result = []
        for nid, nd in self._graph.nodes(data=True):
            if nd.get("kind") == "Space":
                result.append({"space_id": nd.get("space_id", ""), "label": nd.get("label", "")})
        return result
