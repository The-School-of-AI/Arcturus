"""
P11 automation helpers — retrieve context, Neo4j queries, shared assertions.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from tests.automation.p11_mnemo.conftest import AUTH_HEADERS


def wait_for_condition(
    callback: Callable[[], bool],
    timeout_sec: float = 5.0,
    interval_sec: float = 0.15,
) -> bool:
    """
    Poll callback until it returns True or timeout. Use instead of fixed time.sleep()
    when asserting on async state (e.g. Neo4j ingest, Qdrant index).
    Returns True if condition became true, False on timeout.
    """
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if callback():
            return True
        time.sleep(interval_sec)
    return False


def call_retrieve(
    query: str,
    user_id: Optional[str] = None,
    space_id: Optional[str] = None,
) -> tuple[str, List[Dict[str, Any]]]:
    """Call memory_retriever.retrieve with optional user/space scope. Sets auth context so store tenant filter matches."""
    from memory.memory_retriever import retrieve
    from memory.user_id import get_user_id
    from core.auth.context import set_current_user_id
    uid = user_id or AUTH_HEADERS.get("X-User-Id")
    if uid:
        set_current_user_id(uid)
    else:
        uid = get_user_id()
    return retrieve(query, user_id=uid, space_id=space_id)


def assert_context_contains(
    context: str,
    *expected: str,
    msg: str = "",
) -> None:
    """Assert context string contains all expected substrings (case-insensitive)."""
    ctx_lower = (context or "").lower()
    for e in expected:
        assert e.lower() in ctx_lower, f"Expected '{e}' in context. {msg}\nContext:\n{context}"


def assert_context_excludes(context: str, *forbidden: str, msg: str = "") -> None:
    """Assert context does NOT contain any forbidden substring."""
    ctx_lower = (context or "").lower()
    for f in forbidden:
        assert f.lower() not in ctx_lower, f"Context must NOT contain '{f}'. {msg}"


def _neo4j_run(query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run Cypher and return list of record dicts."""
    try:
        from neo4j import GraphDatabase
        import os
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "")
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as s:
            r = s.run(query, params)
            out = [dict(rec) for rec in r]
        driver.close()
        return out
    except Exception:
        return []


def neo4j_get_entities(user_id: str) -> List[Dict[str, Any]]:
    """Query Neo4j for Entity nodes linked to user's memories."""
    return _neo4j_run(
        """
        MATCH (u:User {user_id: $user_id})-[:HAS_MEMORY]->(m:Memory)-[:CONTAINS_ENTITY]->(e:Entity)
        RETURN DISTINCT e.name AS name, e.type AS type
        """,
        {"user_id": user_id},
    )


def neo4j_get_facts(user_id: str, space_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Query Neo4j for Fact nodes for user."""
    try:
        from memory.knowledge_graph import get_knowledge_graph
        kg = get_knowledge_graph()
        if not kg or not kg.enabled or not hasattr(kg, "get_facts_for_user"):
            return []
        facts = kg.get_facts_for_user(user_id, space_id=space_id)
        return [{"namespace": f.get("namespace"), "key": f.get("key"), "value_text": f.get("value_text")} for f in facts]
    except Exception:
        return []


def neo4j_has_entity(user_id: str, name: str, etype: Optional[str] = None) -> bool:
    """Check if user has a memory with entity of given name (and optional type)."""
    entities = neo4j_get_entities(user_id)
    for e in entities:
        if e.get("name", "").lower() == name.lower():
            if etype is None or (e.get("type") or "").lower() == etype.lower():
                return True
    return False


def neo4j_has_fact(user_id: str, key: str, value_substr: Optional[str] = None) -> bool:
    """Check if user has fact with given key (and optional value substring)."""
    facts = neo4j_get_facts(user_id)
    for f in facts:
        if (f.get("key") or "").lower() == key.lower():
            if value_substr is None:
                return True
            val = (f.get("value_text") or "").lower()
            if value_substr.lower() in val:
                return True
    return False
