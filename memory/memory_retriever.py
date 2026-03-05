"""
Memory Retriever — Orchestrates semantic recall, entity recall, graph expansion, and merge.

Keeps process_run() clean: process_run() → memory_retriever.retrieve(query)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core.utils import log_error
import pdb


def _store_get_many(store: Any, ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Best-effort batch fetch for Qdrant-backed store wrappers.
    Falls back to N+1 get() if no batch API is available.
    Returns {id: memory_dict}.
    """
    ids = [i for i in ids if i]
    if not store or not ids:
        return {}
    try:
        if hasattr(store, "get_many"):
            # Preferred: custom wrapper method
            items = store.get_many(ids)
            if isinstance(items, dict):
                return items
            if isinstance(items, list):
                out: Dict[str, Dict[str, Any]] = {}
                for it in items:
                    if isinstance(it, dict) and it.get("id"):
                        out[it["id"]] = it
                return out
        if hasattr(store, "get_batch"):
            items = store.get_batch(ids)
            if isinstance(items, dict):
                return items
            if isinstance(items, list):
                out: Dict[str, Dict[str, Any]] = {}
                for it in items:
                    if isinstance(it, dict) and it.get("id"):
                        out[it["id"]] = it
                return out
    except Exception:
        # Fall back below
        pass

    out: Dict[str, Dict[str, Any]] = {}
    for mid in ids:
        try:
            m = store.get(mid)
            if m:
                out[mid] = m
        except Exception:
            continue
    return out


# Default stop words for fallback entity token extraction
_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "do", "does", "did",
    "you", "your", "have", "has", "had", "any", "about", "of", "our",
    "to", "what", "we", "in", "with", "from", "for", "and", "or", "but",
    "so", "how", "when", "where", "why", "this", "that", "these", "those",
    "can", "could", "would", "should", "me", "my", "at", "next", "week",
}


def retrieve(
    query: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    store: Optional[Any] = None,
    top_for_context: int = 3,
    semantic_k: int = 10,
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Retrieve and merge memories for a query, optionally scoped by user and session.

    Session/user scoping supports memory-backed session routing (e.g. Nexus): when
    session_id (and optionally user_id) are provided, vector search and entity recall
    are limited to that scope so each conversation gets isolated memory context.

    Flow (entity recall runs INDEPENDENTLY of semantic — rescues when vector search returns 0):
    1. Semantic recall (Qdrant vector search) — may return []
    2. Entity recall (NER → resolve → expand) — always runs when kg enabled, regardless of semantic
    3. Graph expansion (from semantic results' entity_ids) — only when semantic had entity_ids
    4. Merge + return formatted context

    Returns (memory_context: str, semantic_results: List) for agent injection and extraction.
    semantic_results: top-k from vector search (used by extractor for existing_memories).
    """
    if not query or not query.strip():
        return "", []

    store = store or _get_store()
    user_id = user_id or _get_user_id() or ""
    result_ids: set = set()
    memory_context = ""

    # pdb.set_trace()
    # Build filter for session-scoped retrieval (memory-backed session routing)
    filter_metadata: Optional[Dict[str, Any]] = None
    if session_id:
        filter_metadata = {"session_id": session_id} # TODO GG: This need to be reviewed further to ensure it doesn't limit the recall of memories

    # 1. Semantic recall (may return 0 — graph recall will still run)
    semantic_results = _semantic_recall(query, store, k=semantic_k, filter_metadata=filter_metadata)
    if semantic_results:
        top = semantic_results[:top_for_context]
        # Dedupe set across ALL recall paths (semantic k + entity + graph)
        result_ids = {r["id"] for r in semantic_results if r.get("id")}
        memory_str = "\n".join(
            [f"- {r['text']} (Confidence: {r.get('score', 0):.2f})" for r in top]
        )
        memory_context = f"PREVIOUS MEMORIES ABOUT USER:\n{memory_str}\n"

    # 2. Entity recall — INDEPENDENT of semantic. Runs whenever kg enabled, even if semantic returned 0.
    kg = _get_knowledge_graph()
    if kg and kg.enabled:
        entity_recall_ids = _entity_recall(query, user_id, kg)
        if entity_recall_ids:
            memory_context = _append_entity_memories(memory_context, entity_recall_ids, store, result_ids)

        # 3. Graph expansion from semantic entity_ids (only when semantic had results with entity_ids)
        entity_ids_from_semantic = []
        for r in semantic_results:
            entity_ids_from_semantic.extend(r.get("entity_ids") or [])
        if entity_ids_from_semantic:
            expanded = kg.expand_from_entities(entity_ids_from_semantic, user_id=user_id)
            memory_context = _append_graph_expansion(memory_context, expanded, store, result_ids)

    return memory_context, semantic_results


def _get_store():
    try:
        from shared.state import get_remme_store
        return get_remme_store()
    except Exception as e:
        log_error(f"MemoryRetriever: failed to get store: {e}")
        return None


def _get_user_id() -> Optional[str]:
    try:
        from memory.user_id import get_user_id
        return get_user_id()
    except Exception:
        return None


def _get_knowledge_graph():
    try:
        from memory.knowledge_graph import get_knowledge_graph
        return get_knowledge_graph()
    except Exception as e:
        log_error(f"MemoryRetriever: failed to get knowledge graph: {e}")
        return None


def _semantic_recall(
    query: str,
    store: Any,
    k: int,
    filter_metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Vector search on Qdrant, optionally filtered by session_id / user_id."""
    if not store:
        return []
    try:
        from remme.utils import get_embedding
        emb = get_embedding(query, task_type="search_query")
        return store.search(
            emb,
            query_text=query,
            k=k,
            filter_metadata=filter_metadata,
        )
    except Exception as e:
        log_error(f"MemoryRetriever: semantic recall failed: {e}")
        return []


def _entity_recall(query: str, user_id: str, kg: Any) -> List[str]:
    """NER on query → resolve against graph → expand → memory_ids."""
    if not kg or not user_id:
        return []
    try:
        from memory.entity_extractor import EntityExtractor
        entities = EntityExtractor().extract_from_query(query)
        # pdb.set_trace()
        if entities:
            resolved = kg.resolve_entity_candidates(user_id, entities, fuzzy_threshold=0.85)
            if resolved:
                expanded = kg.expand_from_entities(resolved, user_id=user_id, depth=1)
                return expanded.get("memory_ids", [])
        # Fallback: stop-word heuristic
        tokens = [w for w in re.findall(r"\b\w+\b", query) if w.lower() not in _STOP_WORDS and len(w) > 1]
        if tokens:
            return kg.get_memory_ids_for_entity_names(user_id, tokens)
    except Exception as e:
        log_error(f"MemoryRetriever: entity recall failed: {e}")
    return []


def _append_graph_expansion(
    memory_context: str,
    expanded: Dict[str, Any],
    store: Any,
    result_ids: set,
) -> str:
    """Append graph-expanded entities, memories, user facts."""
    if not store:
        return memory_context
    # Related entities
    if expanded.get("entities"):
        ent_parts = []
        for e in expanded["entities"][:6]:
            name = e.get("name", "")
            etype = e.get("type", "Entity")
            related = e.get("related", [])[:3]
            if name:
                if related:
                    rel_names = [r.get("name", "") for r in related if r.get("name")]
                    ent_parts.append(f"  {name} ({etype}) -> {', '.join(rel_names)}")
                else:
                    ent_parts.append(f"  {name} ({etype})")
        if ent_parts:
            memory_context += "\nRELATED ENTITIES (from knowledge graph):\n" + "\n".join(ent_parts) + "\n"
    # Extra memories from graph
    extra_ids = [mid for mid in expanded.get("memory_ids", []) if mid not in result_ids]
    if extra_ids:
        # Show up to 3 additional memories; batch-fetch for performance
        to_show = extra_ids[:3]
        batch = _store_get_many(store, to_show)
        extra_texts = []
        for mid in to_show:
            m = batch.get(mid)
            if m and m.get("text"):
                extra_texts.append(f"- {m['text']} (graph-expanded)")
                result_ids.add(mid)
        if extra_texts:
            memory_context += "\nADDITIONAL RELEVANT MEMORIES (from graph):\n" + "\n".join(extra_texts) + "\n"
    # User facts
    if expanded.get("user_facts"):
        facts_str = ", ".join(
            f"{f.get('rel_type', '')}({f.get('name', '')})" for f in expanded["user_facts"][:5]
        )
        memory_context += f"\nUSER FACTS (from knowledge graph): {facts_str}\n"
    return memory_context


def _append_entity_memories(
    memory_context: str,
    entity_first_ids: List[str],
    store: Any,
    result_ids: set,
) -> str:
    """Append entity-matched memories (from entity recall path)."""
    if not store or not entity_first_ids:
        return memory_context
    texts = []
    # Show up to 3 entity-matched memories; batch-fetch for performance
    to_consider = [mid for mid in entity_first_ids[:5] if mid and mid not in result_ids]
    batch = _store_get_many(store, to_consider)
    for mid in to_consider:
        m = batch.get(mid)
        if m and m.get("text"):
            texts.append(f"- {m['text']} (entity-matched)")
            result_ids.add(mid)
        if len(texts) >= 3:
            break
    if texts:
        memory_context += "\nMEMORIES BY ENTITY (from knowledge graph):\n" + "\n".join(texts) + "\n"
    return memory_context
