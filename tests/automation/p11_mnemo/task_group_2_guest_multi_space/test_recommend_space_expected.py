"""
TG2 — Recommend-space: assert EXPECTED space_id is recommended, not just any.
Validates Qdrant search and space-count logic.

Note: These tests may fail when Qdrant contains memories from other runs (shared DB).
Run against an isolated/empty Qdrant for deterministic assertions.
"""

import pytest

pytestmark = [pytest.mark.p11_automation, pytest.mark.integration]

from tests.automation.p11_mnemo.conftest import requires_qdrant_neo4j
from tests.automation.p11_mnemo.helpers import wait_for_condition


@requires_qdrant_neo4j
class TestRecommendSpaceExpected:
    """Recommend-space must return the space that contains semantically similar memories."""

    @pytest.fixture(autouse=True)
    def _setup_spaces_and_memories(self, client):
        """Create Cat and Home Decor spaces, add distinctive memories."""
        # Create spaces (use create response for space_id)
        r1 = client.post("/api/remme/spaces", json={"name": "Cat", "description": "Cat", "sync_policy": "local_only"})
        r2 = client.post("/api/remme/spaces", json={"name": "HomeDecor", "description": "Decor", "sync_policy": "local_only"})
        assert r1.status_code in (200, 201), r1.text
        assert r2.status_code in (200, 201), r2.text
        cat_id = r1.json().get("space_id")
        decor_id = r2.json().get("space_id")
        if not cat_id or not decor_id:
            pytest.skip("Space create did not return space_id")
        # Add Luna memory in Cat
        client.post("/api/remme/add", json={"text": "My cat Luna loves tuna", "category": "general", "space_id": cat_id})
        # Add decor memory in HomeDecor
        client.post(
            "/api/remme/add",
            json={"text": "Planning to repaint the living room blue", "category": "general", "space_id": decor_id},
        )
        # Wait for Qdrant to index so recommend-space can find the new memories
        wait_for_condition(
            lambda: client.get("/api/remme/recommend-space", params={"text": "Luna"}).json().get("recommended_space_id") == cat_id,
            timeout_sec=5.0,
        )
        yield {"cat_space_id": cat_id, "decor_space_id": decor_id}

    def test_recommend_luna_returns_cat(self, client, _setup_spaces_and_memories):
        """text='Luna' MUST recommend Cat space (Luna memory is in Cat)."""
        cat_id = _setup_spaces_and_memories["cat_space_id"]
        r = client.get("/api/remme/recommend-space", params={"text": "Luna", "current_space_id": "__global__"})
        assert r.status_code == 200
        body = r.json()
        rec = body.get("recommended_space_id")
        assert rec == cat_id, f"Expected recommended_space_id={cat_id} (Cat), got {rec}. Reason: {body.get('reason')}"

    def test_recommend_living_room_returns_home_decor(self, client, _setup_spaces_and_memories):
        """text='living room' MUST recommend HomeDecor (living room memory is there)."""
        decor_id = _setup_spaces_and_memories["decor_space_id"]
        r = client.get("/api/remme/recommend-space", params={"text": "living room paint", "current_space_id": "__global__"})
        assert r.status_code == 200
        body = r.json()
        rec = body.get("recommended_space_id")
        assert rec == decor_id, f"Expected recommended_space_id={decor_id} (HomeDecor), got {rec}"

    def test_recommend_tuna_returns_cat(self, client, _setup_spaces_and_memories):
        """text='tuna' (Luna loves tuna) MUST recommend Cat."""
        cat_id = _setup_spaces_and_memories["cat_space_id"]
        r = client.get("/api/remme/recommend-space", params={"text": "tuna", "current_space_id": "__global__"})
        assert r.status_code == 200
        rec = r.json().get("recommended_space_id")
        assert rec == cat_id, f"Expected Cat for 'tuna', got {rec}"
