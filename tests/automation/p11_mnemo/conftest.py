import os
import pytest
from typing import Generator
import json

from qdrant_client import QdrantClient
from neo4j import GraphDatabase

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
def clean_databases(qdrant_test_client, neo4j_test_driver):
    """Clean Neo4j and Qdrant before each test."""
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
