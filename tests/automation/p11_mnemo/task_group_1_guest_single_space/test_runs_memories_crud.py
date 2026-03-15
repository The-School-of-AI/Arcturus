"""
TG1 — Guest User, Single Space: Runs, memories, delete. No LLM (mocked).
"""

import pytest

pytestmark = [
    pytest.mark.p11_automation,
    pytest.mark.integration,
]

from tests.automation.p11_mnemo.conftest import requires_qdrant_neo4j


@requires_qdrant_neo4j
def test_tg1_01_add_memory_global(client):
    """TG1-02: Add memory (Raleigh). Memory stored, status success."""
    res = client.post(
        "/api/remme/add",
        json={
            "text": "I moved from New Jersey to Raleigh, NC last year. I am loving it here as the weather is really great",
            "category": "general",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("status") == "success"
    mem = body.get("memory", body)
    assert "id" in mem
    assert mem.get("text", "").startswith("I moved from")


@requires_qdrant_neo4j
def test_tg1_02_add_memory_jon_google(client):
    """TG1-04: Add memory (Jon, Google, Durham). Memory stored."""
    res = client.post(
        "/api/remme/add",
        json={
            "text": "My friend Jon recently moved from California to Durham. He works at Google. He may need help settling down",
            "category": "general",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("status") == "success"


@requires_qdrant_neo4j
def test_tg1_03_list_memories_global(client):
    """TG1: List memories in global space."""
    res = client.get("/api/remme/memories")
    assert res.status_code == 200, res.text
    data = res.json()
    items = data if isinstance(data, list) else data.get("memories", data.get("items", []))
    assert isinstance(items, list)
    # At least the ones we added
    texts = [m.get("text", "") for m in items if isinstance(m, dict)]
    assert any("Raleigh" in t for t in texts) or any("Jon" in t for t in texts)


@requires_qdrant_neo4j
def test_tg1_04_create_run(client):
    """TG1-01: Create run via dry_run. Returns immediately without calling agent."""
    res = client.post(
        "/api/runs",
        json={
            "query": "Planning to go for a run, can you check current weather",
            "stream": False,
            "dry_run": True,
        },
    )
    assert res.status_code in (200, 201, 202), res.text
    body = res.json()
    assert "id" in body
    assert body.get("status") in ("completed", "starting")
    run_id = body.get("id")
    assert run_id
    # Verify list_runs includes it
    list_res = client.get("/api/runs")
    assert list_res.status_code == 200
    runs = list_res.json()
    ids = [r.get("id") for r in runs]
    assert run_id in ids


@requires_qdrant_neo4j
def test_tg1_05_delete_memory(client):
    """TG1-12: Delete memory. Memory removed from store."""
    # First add one
    add_res = client.post(
        "/api/remme/add",
        json={"text": "Test memory to delete", "category": "general"},
    )
    assert add_res.status_code == 200, add_res.text
    mem = add_res.json().get("memory", add_res.json())
    mem_id = mem.get("id")
    if not mem_id:
        pytest.skip("Add did not return id")
    res = client.delete(f"/api/remme/memories/{mem_id}")
    # Some APIs use 204 or 200
    assert res.status_code in (200, 204), res.text
    # Verify not in list
    list_res = client.get("/api/remme/memories")
    if list_res.status_code == 200:
        items = list_res.json() if isinstance(list_res.json(), list) else list_res.json().get("memories", [])
        ids = [m.get("id") for m in items if isinstance(m, dict)]
        assert mem_id not in ids


@requires_qdrant_neo4j
def test_tg1_06_add_memory_meet_jon(client):
    """TG1-07: Add memory 'I met Jon today at his office'."""
    res = client.post(
        "/api/remme/add",
        json={
            "text": "I met Jon today at his office and had a good chat about local food and weather",
            "category": "general",
        },
    )
    assert res.status_code == 200, res.text
