import os
import re
import hashlib
import pytest
from typing import Generator
from unittest.mock import patch
import json
import numpy as np

from qdrant_client import QdrantClient
from neo4j import GraphDatabase

# Embedding dimension (nomic default)
_DIM = 768


def _word_overlap_embedding(text: str, task_type: str = "search_document"):
    """Word-overlap embedding so retrieval/recommend-space tests get deterministic, query-relevant results."""
    tokens = set(re.findall(r"\b\w+\b", (text or "").lower()))
    vec = np.zeros(_DIM, dtype=np.float32)
    for t in tokens:
        idx = int(hashlib.md5(t.encode()).hexdigest(), 16) % _DIM
        vec[idx] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    else:
        vec[0] = 1.0
    return vec

# Guest user for auth (used by client fixture and helpers)
AUTH_HEADERS = {"X-User-Id": "00000000-0000-0000-0000-000000000001"}


def _qdrant_available() -> bool:
    try:
        url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        QdrantClient(url=url, timeout=2)
        return True
    except Exception:
        return False


def _neo4j_available() -> bool:
    try:
        from memory.knowledge_graph import get_knowledge_graph
        kg = get_knowledge_graph()
        return kg is not None and getattr(kg, "enabled", False)
    except Exception:
        return False


def requires_qdrant_neo4j(f):
    """Skip if Qdrant or Neo4j not available (e.g. default pytest run without test services)."""
    return pytest.mark.skipif(
        not _qdrant_available() or not _neo4j_available(),
        reason="Qdrant and/or Neo4j not available (start services to run automation)",
    )(f)


@pytest.fixture(scope="session", autouse=True)
def p11_embedding_mock():
    """Patch get_embedding so retrieval and recommend-space work without real LLM; word-overlap for relevance."""
    with patch("remme.utils.get_embedding", side_effect=_word_overlap_embedding), \
         patch("routers.remme.get_embedding", side_effect=_word_overlap_embedding):
        yield


# Ensure we're running with the right test DBs
@pytest.fixture(scope="session", autouse=True)
def verify_test_environment():
    """Fail fast if not running against the isolated test ports."""
    qdrant_url = os.environ.get("QDRANT_URL", "")
    neo4j_uri = os.environ.get("NEO4J_URI", "")
    
    if "6335" not in qdrant_url:
        pytest.skip("Skipping automation test: QDRANT_URL does not point to test port 6335")
    if "7688" not in neo4j_uri:
        pytest.skip("Skipping automation test: NEO4J_URI does not point to test port 7688")

@pytest.fixture(scope="session")
def qdrant_test_client() -> QdrantClient:
    url = os.environ.get("QDRANT_URL", "http://localhost:6335")
    return QdrantClient(url=url)

@pytest.fixture(scope="session")
def neo4j_test_driver():
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7688")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "test-password")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    yield driver
    driver.close()

@pytest.fixture(autouse=True)
def clean_databases(qdrant_test_client, neo4j_test_driver, request):
    """Clean Neo4j and Qdrant before each test. Skip for TestSequentialRaleighJonFlow so steps share state."""
    # Sequential scenario tests depend on prior steps; do not clean between them
    parent_name = getattr(request.node.parent, "name", "") if request.node.parent else ""
    if "TestSequentialRaleighJonFlow" in parent_name:
        yield
        return
    # Clean Neo4j
    with neo4j_test_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
        
    # Clean Qdrant points instead of entire collection which breaks the cached store
    from qdrant_client.http import models as qmodels
    try:
        collections = qdrant_test_client.get_collections().collections
        for c in collections:
            qdrant_test_client.delete(c.name, points_selector=qmodels.Filter())
    except Exception as e:
        print(f"Warning: Failed to clean Qdrant collections: {e}")
        
    # Reset all shared state singletons to force re-initialization with correct env vars (MNEMO_ENABLED, etc.)
    import shared.state
    shared.state._remme_store = None
    shared.state._remme_extractor = None
    shared.state._unified_extractor = None
    
    # Also reset knowledge_graph singleton
    import memory.knowledge_graph
    memory.knowledge_graph._kg = None

    yield

@pytest.fixture
def mock_llm_extractor(monkeypatch):
    """
    Mocks the UnifiedExtractor to return deterministic results without hitting the LLM.
    Tests can override the `mock_result` attribute on this fixture to customize.
    """
    from memory.unified_extractor import UnifiedExtractor
    from memory.unified_extraction_schema import UnifiedExtractionResult

    class MockExtractor:
        def __init__(self):
            self.mock_result = UnifiedExtractionResult(source="memory")

        def mock_call_llm(self, user_content: str, source: str) -> dict:
            # We can parse the input and return specific things if we want,
            # but usually the test will just configure `self.mock_result` before the action.
            self.mock_result.source = source
            return self.mock_result

    m = MockExtractor()
    monkeypatch.setattr(UnifiedExtractor, "_call_llm", m.mock_call_llm)
    return m


@pytest.fixture
def client():
    """TestClient with auth headers for RemMe/API tests."""
    from fastapi.testclient import TestClient
    from api import app
    return TestClient(app, headers=AUTH_HEADERS)
