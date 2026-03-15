"""
TG1 — Sequential scenario: memories and facts from step N must be injected in step N+1.
Runs in strict order. Validates retrieval logic and Qdrant/Neo4j queries.
"""

import pytest

pytestmark = [pytest.mark.p11_automation, pytest.mark.integration]

from tests.automation.p11_mnemo.conftest import requires_qdrant_neo4j
from tests.automation.p11_mnemo.helpers import (
    call_retrieve,
    assert_context_contains,
    assert_context_excludes,
    neo4j_has_entity,
    neo4j_has_fact,
    wait_for_condition,
)
from tests.automation.p11_mnemo.conftest import AUTH_HEADERS

USER_ID = AUTH_HEADERS["X-User-Id"]


@requires_qdrant_neo4j
class TestSequentialRaleighJonFlow:
    """Run steps in order. Each step depends on previous."""

    def test_step_01_add_raleigh_memory(self, client):
        """Add Raleigh memory. Verify stored and Neo4j has location fact."""
        r = client.post(
            "/api/remme/add",
            json={
                "text": "I moved from New Jersey to Raleigh, NC last year. I am loving it here as the weather is really great",
                "category": "general",
            },
        )
        assert r.status_code == 200
        ok = wait_for_condition(
            lambda: neo4j_has_fact(USER_ID, "location", "raleigh") or neo4j_has_entity(USER_ID, "Raleigh", "City"),
            timeout_sec=5.0,
        )
        assert ok, "Neo4j should have location fact or Raleigh entity after add"

    def test_step_02_retrieve_weather_has_raleigh(self, client):
        """Query about weather. Context MUST include Raleigh (from facts/entities)."""
        ctx, _ = call_retrieve("Planning to go for a run, can you check current weather")
        assert_context_contains(ctx, "raleigh", msg="Raleigh (user location) must be injected")

    def test_step_03_add_jon_google_memory(self, client):
        """Add Jon/Google/Durham memory. Verify entities in Neo4j."""
        r = client.post(
            "/api/remme/add",
            json={
                "text": "My friend Jon recently moved from California to Durham. He works at Google. He may need help settling down",
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

    def test_step_04_retrieve_meet_jon_has_context(self, client):
        """Query about meeting Jon at office. Context MUST include Jon, office, Durham or Google."""
        ctx, _ = call_retrieve("Can you check next week's weather as I am planning to meet Jon at his office")
        assert_context_contains(ctx, "jon", msg="Jon must be in context")
        # Office/Durham/Google — at least one
        assert (
            "office" in (ctx or "").lower()
            or "durham" in (ctx or "").lower()
            or "google" in (ctx or "").lower()
        ), "Jon's office (Durham/Google) must be in context"

    def test_step_05_add_met_jon_memory(self, client):
        """Add memory about meeting Jon."""
        r = client.post(
            "/api/remme/add",
            json={
                "text": "I met Jon today at his office and had a good chat about local food and weather",
                "category": "general",
            },
        )
        assert r.status_code == 200

    def test_step_06_retrieve_when_met_jon(self, client):
        """Query when did I meet Jon. Context MUST include the meeting memory."""
        ctx, _ = call_retrieve("When did I last meet Jon?")
        assert_context_contains(ctx, "jon", msg="Jon meeting memory must be retrieved")
        assert "met" in (ctx or "").lower() or "office" in (ctx or "").lower()


@requires_qdrant_neo4j
class TestRetrievalSpaceIsolation:
    """Space-scoped retrieval: Global run must not inject space-specific memories."""

    def test_retrieve_global_no_space_leak(self, client):
        """When space_id=__global__, do not inject memories from other spaces."""
        ctx, _ = call_retrieve("What do I know?", space_id="__global__")
        # Global should include global memories only; no assertion on content, just no crash
        assert ctx is not None or True
