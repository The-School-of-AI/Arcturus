from typing import Any, Dict, List

import pytest

from memory.knowledge_graph import KnowledgeGraph


class DummyKG(KnowledgeGraph):
    """
    Small test double that intercepts _run_write calls so we can assert on the
    contradiction Cypher without talking to a real Neo4j instance.
    """

    def __init__(self) -> None:
        # Bypass real driver init
        self._driver = None
        self._enabled = True
        self._writes: List[Dict[str, Any]] = []

    def _run_write(self, query: str, params: Dict[str, Any]) -> None:  # type: ignore[override]
        self._writes.append({"query": query, "params": params})


def test_upsert_fact_triggers_contradiction_update():
    kg = DummyKG()

    # First upsert should call upsert_fact and then _update_fact_contradictions
    kg.upsert_fact(
        namespace="identity.food",
        key="dietary_style",
        user_id="user-1",
        value_type="text",
        value_text="vegetarian",
    )

    # We expect two writes: the MERGE for Fact, and the CONTRADICTS maintenance query
    write_queries = [w["query"] for w in kg._writes]
    assert any("MERGE (f:Fact" in q for q in write_queries)
    assert any("CONTRADICTS" in q for q in write_queries)

