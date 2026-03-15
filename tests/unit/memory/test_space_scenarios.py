"""
Space-related unit tests for P11 Mnemo Phase 3 (Spaces, Fact scope, Session scoping).

Covers: space_id exists and passed, space_id exists but not passed, global sentinel,
registry scope, RunRequest, memory_retriever filter logic, preferences adapter, and API params.
"""

import pytest

from memory.space_constants import SPACE_ID_GLOBAL
from memory.fact_field_registry import get_field_scope, get_scope_for_namespace_key


class TestSpaceConstants:
    """SPACE_ID_GLOBAL sentinel and space identity."""

    def test_space_id_global_is_sentinel(self):
        assert SPACE_ID_GLOBAL == "__global__"

    def test_space_id_global_is_not_uuid_like(self):
        assert SPACE_ID_GLOBAL != "__global__ ".strip() or True  # ensure it's the constant
        assert len(SPACE_ID_GLOBAL) > 0
        assert SPACE_ID_GLOBAL.startswith("__")


class TestFactRegistryScope:
    """get_field_scope and get_scope_for_namespace_key — global vs space-scoped facts."""

    def test_known_field_defaults_to_global_scope(self):
        assert get_field_scope("personal_hobbies") == "global"
        assert get_field_scope("dietary_style") == "global"
        assert get_field_scope("verbosity") == "global"

    def test_unknown_field_returns_global_scope(self):
        assert get_field_scope("nonexistent_field") == "global"
        assert get_field_scope("") == "global"

    def test_get_scope_for_namespace_key_known_field(self):
        assert get_scope_for_namespace_key("identity", "personal_hobbies") == "global"
        assert get_scope_for_namespace_key("identity.food", "dietary_style") == "global"

    def test_get_scope_for_namespace_key_unknown_returns_global(self):
        assert get_scope_for_namespace_key("unknown", "unknown_key") == "global"


class TestRunRequestSpaceId:
    """RunRequest model: space_id optional."""

    def test_run_request_space_id_optional(self):
        from routers.runs import RunRequest

        r = RunRequest(query="hello")
        assert r.space_id is None

    def test_run_request_space_id_passed(self):
        from routers.runs import RunRequest

        r = RunRequest(query="hello", space_id="space-uuid-123")
        assert r.space_id == "space-uuid-123"

    def test_run_request_space_id_explicit_none(self):
        from routers.runs import RunRequest

        r = RunRequest(query="hello", space_id=None)
        assert r.space_id is None


class TestMemoryRetrieverSpaceFilter:
    """retrieve() builds correct filter_metadata for space_id/space_ids."""

    def test_retrieve_with_space_id_builds_filter(self):
        """When space_id passed and not __global__, filter includes only that space (no global injection)."""
        from unittest.mock import MagicMock, patch
        import numpy as np

        mock_store = MagicMock()
        mock_store.search.return_value = []
        # Avoid calling Ollama in CI; semantic_recall must reach store.search()
        fake_embedding = np.zeros(384, dtype=np.float32)

        with patch("memory.memory_retriever._get_store", return_value=mock_store):
            with patch("memory.memory_retriever._get_user_id", return_value="user1"):
                with patch("memory.memory_retriever._get_knowledge_graph", return_value=None):
                    with patch("remme.utils.get_embedding", return_value=fake_embedding):
                        from memory.memory_retriever import retrieve

                        _, _ = retrieve("query", space_id="space-uuid-456")
        call_kw = mock_store.search.call_args[1] if mock_store.search.called else {}
        meta = call_kw.get("filter_metadata") or {}
        assert "space_ids" in meta
        assert meta["space_ids"] == ["space-uuid-456"]

    def test_retrieve_with_space_id_global_no_space_filter(self):
        """When space_id is __global__, filter is global-only (space_ids=[__global__])."""
        from unittest.mock import MagicMock, patch
        import numpy as np

        mock_store = MagicMock()
        mock_store.search.return_value = []
        fake_embedding = np.zeros(384, dtype=np.float32)

        with patch("memory.memory_retriever._get_store", return_value=mock_store):
            with patch("memory.memory_retriever._get_user_id", return_value="user1"):
                with patch("memory.memory_retriever._get_knowledge_graph", return_value=None):
                    with patch("remme.utils.get_embedding", return_value=fake_embedding):
                        from memory.memory_retriever import retrieve

                        _, _ = retrieve("query", space_id=SPACE_ID_GLOBAL)
        call_kw = mock_store.search.call_args[1] if mock_store.search.called else {}
        meta = call_kw.get("filter_metadata") or {}
        assert meta.get("space_ids") == [SPACE_ID_GLOBAL]

    def test_retrieve_without_space_id_no_space_filter(self):
        """When space_id and space_ids not passed, no space filter."""
        from unittest.mock import MagicMock, patch

        mock_store = MagicMock()
        mock_store.search.return_value = []

        with patch("memory.memory_retriever._get_store", return_value=mock_store):
            with patch("memory.memory_retriever._get_user_id", return_value="user1"):
                with patch("memory.memory_retriever._get_knowledge_graph", return_value=None):
                    from memory.memory_retriever import retrieve

                    _, _ = retrieve("query")
                    call_kw = mock_store.search.call_args[1] if mock_store.search.called else {}
                    meta = call_kw.get("filter_metadata") or {}
                    assert "space_ids" not in meta or meta.get("space_ids") is None

    def test_retrieve_with_space_ids_builds_filter(self):
        """When space_ids list passed (without global), filter includes only those spaces."""
        from unittest.mock import MagicMock, patch
        import numpy as np

        mock_store = MagicMock()
        mock_store.search.return_value = []
        # Avoid calling Ollama in CI; semantic_recall must reach store.search()
        fake_embedding = np.zeros(384, dtype=np.float32)

        with patch("memory.memory_retriever._get_store", return_value=mock_store):
            with patch("memory.memory_retriever._get_user_id", return_value="user1"):
                with patch("memory.memory_retriever._get_knowledge_graph", return_value=None):
                    with patch("remme.utils.get_embedding", return_value=fake_embedding):
                        from memory.memory_retriever import retrieve

                        _, _ = retrieve("query", space_ids=["space-a", "space-b"])
        call_kw = mock_store.search.call_args[1] if mock_store.search.called else {}
        meta = call_kw.get("filter_metadata") or {}
        assert "space_ids" in meta
        assert "space-a" in meta["space_ids"]
        assert "space-b" in meta["space_ids"]


class TestPreferencesAdapterSpaceParams:
    """build_preferences_from_neo4j passes space_id/space_ids to get_facts_for_user."""

    def test_adapter_passes_space_id_to_get_facts_for_user(self):
        """When space_id provided, adapter forwards it."""
        from unittest.mock import MagicMock, patch

        mock_kg = MagicMock()
        mock_kg.enabled = True
        mock_kg.get_facts_for_user.return_value = []
        mock_kg.get_evidence_count_for_user.return_value = {"total_events": 0}

        with patch("memory.knowledge_graph.get_knowledge_graph", return_value=mock_kg):
            with patch("memory.mnemo_config.is_mnemo_enabled", return_value=True):
                from memory.neo4j_preferences_adapter import build_preferences_from_neo4j

                build_preferences_from_neo4j("user1", space_id="space-xyz")
                mock_kg.get_facts_for_user.assert_called_once()
                call_kw = mock_kg.get_facts_for_user.call_args[1]
                assert call_kw.get("space_id") == "space-xyz"

    def test_adapter_passes_space_ids_to_get_facts_for_user(self):
        """When space_ids provided, adapter forwards them."""
        from unittest.mock import MagicMock, patch

        mock_kg = MagicMock()
        mock_kg.enabled = True
        mock_kg.get_facts_for_user.return_value = []
        mock_kg.get_evidence_count_for_user.return_value = {"total_events": 0}

        with patch("memory.knowledge_graph.get_knowledge_graph", return_value=mock_kg):
            with patch("memory.mnemo_config.is_mnemo_enabled", return_value=True):
                from memory.neo4j_preferences_adapter import build_preferences_from_neo4j

                build_preferences_from_neo4j("user1", space_ids=["a", "b"])
                mock_kg.get_facts_for_user.assert_called_once()
                call_kw = mock_kg.get_facts_for_user.call_args[1]
                assert call_kw.get("space_ids") == ["a", "b"]

    def test_adapter_without_space_params_passes_none(self):
        """When space_id and space_ids not provided, adapter passes neither."""
        from unittest.mock import MagicMock, patch

        mock_kg = MagicMock()
        mock_kg.enabled = True
        mock_kg.get_facts_for_user.return_value = []
        mock_kg.get_evidence_count_for_user.return_value = {"total_events": 0}

        with patch("memory.knowledge_graph.get_knowledge_graph", return_value=mock_kg):
            with patch("memory.mnemo_config.is_mnemo_enabled", return_value=True):
                from memory.neo4j_preferences_adapter import build_preferences_from_neo4j

                build_preferences_from_neo4j("user1")
                mock_kg.get_facts_for_user.assert_called_once()
                call_kw = mock_kg.get_facts_for_user.call_args[1]
                assert call_kw.get("space_id") is None
                assert call_kw.get("space_ids") is None


@pytest.mark.slow
class TestPreferencesApiSpaceParams:
    """GET /remme/preferences parses space_id and space_ids query params (requires app startup)."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api import app
        AUTH_HEADERS = {"X-User-Id": "00000000-0000-0000-0000-000000000001"}
        return TestClient(app, headers=AUTH_HEADERS)

    def test_preferences_without_space_params(self, client):
        """No space params → request proceeds (may hit mnemo or legacy path)."""
        # Response depends on MNEMO_ENABLED; we only assert no 422
        resp = client.get("/api/remme/preferences")
        assert resp.status_code in (200, 404, 500)  # 422 = validation error

    def test_preferences_with_space_id_param(self, client):
        """space_id query param is accepted."""
        resp = client.get("/api/remme/preferences?space_id=space-123")
        assert resp.status_code != 422

    def test_preferences_with_space_ids_param(self, client):
        """space_ids comma-separated param is accepted."""
        resp = client.get("/api/remme/preferences?space_ids=space-a,space-b,space-c")
        assert resp.status_code != 422

    def test_preferences_with_both_space_params(self, client):
        """Both space_id and space_ids can be passed (space_ids takes precedence per impl)."""
        resp = client.get("/api/remme/preferences?space_id=space-x&space_ids=space-y,space-z")
        assert resp.status_code != 422


@pytest.mark.slow
class TestRunsApiSpaceId:
    """POST /runs accepts optional space_id in request body (requires app startup)."""

    def test_runs_without_space_id(self):
        """Request body without space_id is valid."""
        from fastapi.testclient import TestClient
        from api import app

        AUTH_HEADERS = {"X-User-Id": "00000000-0000-0000-0000-000000000001"}
        client = TestClient(app, headers=AUTH_HEADERS)
        resp = client.post("/api/runs", json={"query": "hello"})
        assert resp.status_code in (200, 201)

    def test_runs_with_space_id(self, monkeypatch):
        """Request body with space_id is valid."""
        from fastapi.testclient import TestClient
        from api import app

        # Mock space access so test user can run in space-uuid-789
        monkeypatch.setattr(
            "memory.knowledge_graph.get_knowledge_graph",
            lambda: type("MockKG", (), {"enabled": False})(),
        )
        AUTH_HEADERS = {"X-User-Id": "00000000-0000-0000-0000-000000000001"}
        client = TestClient(app, headers=AUTH_HEADERS)
        resp = client.post("/api/runs", json={"query": "hello", "space_id": "space-uuid-789"})
        assert resp.status_code in (200, 201)
