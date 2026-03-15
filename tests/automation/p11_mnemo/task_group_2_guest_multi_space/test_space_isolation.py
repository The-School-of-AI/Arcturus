"""
TG2 — Guest, Multiple Spaces: Space isolation, recommend-space. No LLM (mocked).
"""

import pytest

pytestmark = [
    pytest.mark.p11_automation,
    pytest.mark.integration,
]

from tests.automation.p11_mnemo.conftest import requires_qdrant_neo4j


@requires_qdrant_neo4j
def test_tg2_01_create_space_cat(client):
    """TG2: Create Cat space."""
    res = client.post(
        "/api/remme/spaces",
        json={"name": "Cat", "description": "Cat related", "sync_policy": "local_only"},
    )
    assert res.status_code in (200, 201), res.text
    body = res.json()
    space = body.get("space", body)
    assert space.get("name") == "Cat" or "id" in body or "space_id" in body


@requires_qdrant_neo4j
def test_tg2_02_create_space_home_decor(client):
    """TG2: Create Home Decor space."""
    res = client.post(
        "/api/remme/spaces",
        json={"name": "Home Decor", "description": "Home decor", "sync_policy": "local_only"},
    )
    assert res.status_code in (200, 201), res.text


@requires_qdrant_neo4j
def test_tg2_03_add_memory_in_cat_space(client):
    """TG2-01: Add memory in Cat space."""
    spaces_res = client.get("/api/remme/spaces")
    assert spaces_res.status_code == 200
    spaces = spaces_res.json() if isinstance(spaces_res.json(), list) else spaces_res.json().get("spaces", [])
    cat = next((s for s in spaces if s.get("name") == "Cat"), None)
    space_id = cat.get("space_id") or cat.get("id") if cat else None
    if not space_id:
        pytest.skip("Cat space not found")
    res = client.post(
        "/api/remme/add",
        json={
            "text": "My cat Luna loves tuna",
            "category": "general",
            "space_id": space_id,
        },
    )
    assert res.status_code == 200, res.text


@requires_qdrant_neo4j
def test_tg2_04_add_memory_in_home_decor(client):
    """TG2-02: Add memory in Home Decor space."""
    spaces_res = client.get("/api/remme/spaces")
    assert spaces_res.status_code == 200
    spaces = spaces_res.json() if isinstance(spaces_res.json(), list) else spaces_res.json().get("spaces", [])
    hd = next((s for s in spaces if s.get("name") == "Home Decor"), None)
    space_id = hd.get("space_id") or hd.get("id") if hd else None
    if not space_id:
        pytest.skip("Home Decor space not found")
    res = client.post(
        "/api/remme/add",
        json={
            "text": "Planning to repaint the living room blue",
            "category": "general",
            "space_id": space_id,
        },
    )
    assert res.status_code == 200, res.text


@requires_qdrant_neo4j
def test_tg2_05_list_memories_by_space(client):
    """TG2-08: List memories filtered by space."""
    spaces_res = client.get("/api/remme/spaces")
    assert spaces_res.status_code == 200
    spaces = spaces_res.json() if isinstance(spaces_res.json(), list) else spaces_res.json().get("spaces", [])
    cat = next((s for s in spaces if s.get("name") == "Cat"), None)
    space_id = cat.get("space_id") or cat.get("id") if cat else None
    if not space_id:
        pytest.skip("Cat space not found")
    res = client.get(f"/api/remme/memories?space_id={space_id}")
    assert res.status_code == 200
    data = res.json()
    mems = data.get("memories", data) if isinstance(data, dict) else data
    assert isinstance(mems, list)
    for m in mems:
        assert m.get("space_id") == space_id or m.get("space_id") == "__global__"  # allow legacy


@requires_qdrant_neo4j
def test_tg2_06_recommend_space(client):
    """TG2-06: GET recommend-space returns suggestion."""
    res = client.get("/api/remme/recommend-space", params={"text": "Luna", "current_space_id": "__global__"})
    assert res.status_code == 200
    body = res.json()
    assert "recommended_space_id" in body
    assert "reason" in body
