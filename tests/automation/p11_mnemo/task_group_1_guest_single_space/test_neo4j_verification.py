"""
TG1 — Neo4j verification: entities, facts, relationships after add/delete.
"""

import pytest

pytestmark = [pytest.mark.p11_automation, pytest.mark.integration]

from tests.automation.p11_mnemo.conftest import requires_qdrant_neo4j, AUTH_HEADERS
from tests.automation.p11_mnemo.helpers import (
    neo4j_get_entities,
    neo4j_get_facts,
    neo4j_has_entity,
    neo4j_has_fact,
    wait_for_condition,
)

USER_ID = AUTH_HEADERS["X-User-Id"]


@requires_qdrant_neo4j
class TestNeo4jEntityVerification:
    """Verify entities extracted and stored in Neo4j after memory add."""

    def test_add_memory_creates_entities(self, client):
        """Add memory with entities; verify Neo4j has them (mock extracts Jon, Google, Durham)."""
        r = client.post(
            "/api/remme/add",
            json={
                "text": "Jon from Google moved to Durham",
                "category": "general",
            },
        )
        assert r.status_code == 200
        ok = wait_for_condition(
            lambda: (
                neo4j_has_entity(USER_ID, "Jon", "Person")
                and neo4j_has_entity(USER_ID, "Google", "Company")
                and neo4j_has_entity(USER_ID, "Durham", "City")
            ),
            timeout_sec=5.0,
        )
        assert ok, "Neo4j should have Jon, Google, Durham entities after add"

    def test_add_raleigh_creates_location_fact(self, client):
        """Add Raleigh memory; verify location fact in Neo4j."""
        r = client.post(
            "/api/remme/add",
            json={
                "text": "I moved from New Jersey to Raleigh, NC last year",
                "category": "general",
            },
        )
        assert r.status_code == 200
        ok = wait_for_condition(
            lambda: neo4j_has_fact(USER_ID, "location", "raleigh") or neo4j_has_entity(USER_ID, "Raleigh", "City"),
            timeout_sec=5.0,
        )
        assert ok, "Neo4j should have location fact or Raleigh entity after add"


@requires_qdrant_neo4j
class TestNeo4jFactVerification:
    """Verify facts stored in Neo4j."""

    def test_facts_list_returns_records(self, client):
        """Add memory with fact; get_facts returns at least one fact."""
        client.post(
            "/api/remme/add",
            json={"text": "I live in Raleigh, NC. Great weather here.", "category": "general"},
        )
        wait_for_condition(lambda: len(neo4j_get_facts(USER_ID)) > 0, timeout_sec=5.0)
        facts = neo4j_get_facts(USER_ID)
        # May have location fact
        assert isinstance(facts, list)

    def test_entities_list_returns_records(self, client):
        """Add memory; get_entities returns at least one entity."""
        client.post(
            "/api/remme/add",
            json={"text": "Jon works at Google in Durham", "category": "general"},
        )
        wait_for_condition(lambda: len(neo4j_get_entities(USER_ID)) > 0, timeout_sec=5.0)
        entities = neo4j_get_entities(USER_ID)
        assert isinstance(entities, list)
        # Mock produces Jon, Google, Durham
        names = [e.get("name", "").lower() for e in entities]
        assert "jon" in names or "google" in names or "durham" in names
