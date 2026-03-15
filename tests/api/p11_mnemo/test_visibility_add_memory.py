from fastapi.testclient import TestClient

from api import app

# Test user ID (valid UUID) for AuthMiddleware on protected /api/remme routes
AUTH_HEADERS = {"X-User-Id": "00000000-0000-0000-0000-000000000001"}
client = TestClient(app, headers=AUTH_HEADERS)


def test_add_memory_rejects_invalid_visibility(monkeypatch):
    # Patch get_embedding in the router (add endpoint calls it before validation)
    def fake_embedding(text, task_type=None):
        return [0.0, 0.0, 0.0]

    import routers.remme as remme_router

    monkeypatch.setattr(remme_router, "get_embedding", fake_embedding)

    # Patch remme_store.add so we don't hit real vector store
    import routers.remme as remme_router

    class DummyStore:
        def add(self, text, embedding, **kwargs):
            raise AssertionError("add should not be called for invalid visibility")

    remme_router.remme_store = DummyStore()

    res = client.post(
        "/api/remme/add",
        json={"text": "hello", "category": "general", "visibility": "not-valid"},
    )
    assert res.status_code == 400
    assert "Invalid visibility" in res.json()["detail"]


def test_add_memory_accepts_valid_visibility(monkeypatch):
    # Ensure we can pass a valid visibility and it flows into add() kwargs
    import routers.remme as remme_router

    def fake_embedding(text, task_type=None):
        return [0.0, 0.0, 0.0]

    monkeypatch.setattr(remme_router, "get_embedding", fake_embedding)

    calls = {}

    class DummyStore:
        def add(self, text, embedding, **kwargs):
            calls["kwargs"] = kwargs
            # Simulate stored memory shape
            return {"id": "mem-1", "text": text, **kwargs}

    remme_router.remme_store = DummyStore()

    res = client.post("/api/remme/add", json={"text": "hello", "category": "general", "visibility": "private"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    # Verify visibility propagated into add kwargs
    assert calls["kwargs"]["metadata"]["visibility"] == "private"


def test_add_memory_in_space_defaults_to_space_visibility(monkeypatch):
    # When space_id is provided and visibility omitted, default should be "space"
    import routers.remme as remme_router

    def fake_embedding(text, task_type=None):
        return [0.0, 0.0, 0.0]

    monkeypatch.setattr(remme_router, "get_embedding", fake_embedding)
    # Mock space access check - disabled KG skips can_user_access_space
    monkeypatch.setattr(
        "memory.knowledge_graph.get_knowledge_graph",
        lambda: type("MockKG", (), {"enabled": False})(),
    )

    calls = {}

    class DummyStore:
        def add(self, text, embedding, **kwargs):
            calls["kwargs"] = kwargs
            return {"id": "mem-2", "text": text, **kwargs}

    remme_router.remme_store = DummyStore()

    res = client.post(
        "/api/remme/add",
        json={"text": "space note", "category": "general", "space_id": "space-123"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert calls["kwargs"]["metadata"]["visibility"] == "space"


def test_add_memory_global_defaults_to_private(monkeypatch):
    # When no space_id and no visibility, default should be "private"
    import routers.remme as remme_router

    def fake_embedding(text, task_type=None):
        return [0.0, 0.0, 0.0]

    monkeypatch.setattr(remme_router, "get_embedding", fake_embedding)

    calls = {}

    class DummyStore:
        def add(self, text, embedding, **kwargs):
            calls["kwargs"] = kwargs
            return {"id": "mem-3", "text": text, **kwargs}

    remme_router.remme_store = DummyStore()

    res = client.post(
        "/api/remme/add",
        json={"text": "global note", "category": "general"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert calls["kwargs"]["metadata"]["visibility"] == "private"


def test_add_memory_rejects_space_visibility_without_space(monkeypatch):
    # Patch get_embedding in the router so we reach visibility validation
    def fake_embedding(text, task_type=None):
        return [0.0, 0.0, 0.0]

    import routers.remme as remme_router

    monkeypatch.setattr(remme_router, "get_embedding", fake_embedding)

    # visibility="space" requires a concrete non-global space_id
    res = client.post(
        "/api/remme/add",
        json={"text": "bad combo", "category": "general", "visibility": "space"},
    )
    assert res.status_code == 400
    assert "requires a non-global space_id" in res.json()["detail"]

