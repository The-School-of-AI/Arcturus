"""
P11 Mnemo automation test suite — conftest.

Mocks all LLM calls (get_embedding, UnifiedExtractor, EntityExtractor) so tests
run without Gemini/Ollama and do not block. Uses real Qdrant + Neo4j when available.
"""

import os
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

# Ensure project root in path
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(project_root))

# Guest user for auth
AUTH_HEADERS = {"X-User-Id": "00000000-0000-0000-0000-000000000001"}

# Deterministic embedding: same text -> same vector (768 dim for nomic)
DIM = 768


def _fake_embedding(text: str, task_type: str = "search_document"):
    """Deterministic embedding from text hash. No LLM/API calls. Different texts => different vectors."""
    h = hashlib.sha256((task_type + ":" + (text or "")).encode()).hexdigest()
    np.random.seed(int(h[:8], 16) % (2**32))
    vec = np.random.randn(DIM).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def _word_overlap_embedding(text: str, task_type: str = "search_document"):
    """Word-overlap embedding: texts sharing words get high cosine similarity.
    Enables recommend-space and retrieval tests to assert EXPECTED results."""
    import re
    tokens = set(re.findall(r"\b\w+\b", (text or "").lower()))
    vec = np.zeros(DIM, dtype=np.float32)
    for t in tokens:
        idx = int(hashlib.md5(t.encode()).hexdigest(), 16) % DIM
        vec[idx] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    else:
        vec = np.zeros(DIM, dtype=np.float32)
        vec[0] = 1.0  # avoid zero vector
    return vec


def _get_semantic_embedding(text: str, task_type: str = "search_document"):
    """Use word-overlap when SEMANTIC_EMBEDDING=true (for recommend-space, retrieval assertions)."""
    if os.environ.get("SEMANTIC_EMBEDDING", "").lower() == "true":
        return _word_overlap_embedding(text, task_type)
    return _fake_embedding(text, task_type)


def _mock_unified_extraction(text: str) -> dict:
    """Return mock UnifiedExtractionResult-compatible dict from memory text. No LLM."""
    text_lower = (text or "").lower()
    memories = [{"action": "add", "text": text[:500], "id": None}]
    entities = []
    entity_relationships = []
    facts = []
    evidence = [{"source_type": "extraction", "source_ref": "", "timestamp": None}]

    # Raleigh / location
    if "raleigh" in text_lower or "moved" in text_lower and "nc" in text_lower:
        entities.extend([{"type": "City", "name": "Raleigh"}, {"type": "City", "name": "New Jersey"}])
        facts.append({
            "field_id": "location",
            "value_type": "text",
            "value_text": "Raleigh, NC",
            "entity_ref": None,
        })

    # Jon, Google, Durham
    if "jon" in text_lower:
        entities.append({"type": "Person", "name": "Jon"})
    if "google" in text_lower:
        entities.append({"type": "Company", "name": "Google"})
    if "durham" in text_lower:
        entities.append({"type": "City", "name": "Durham"})
    if "jon" in text_lower and "google" in text_lower:
        entity_relationships.append({
            "from_type": "Person", "from_name": "Jon",
            "to_type": "Company", "to_name": "Google",
            "type": "works_at", "value": None, "confidence": 1.0,
        })
    if "jon" in text_lower and "durham" in text_lower:
        entity_relationships.append({
            "from_type": "Person", "from_name": "Jon",
            "to_type": "City", "to_name": "Durham",
            "type": "located_in", "value": None, "confidence": 1.0,
        })

    # Luna (cat)
    if "luna" in text_lower:
        entities.append({"type": "Concept", "name": "Luna"})
    if "tuna" in text_lower and "luna" in text_lower:
        entity_relationships.append({
            "from_type": "Concept", "from_name": "Luna",
            "to_type": "Concept", "to_name": "tuna",
            "type": "related_to", "value": "loves", "confidence": 1.0,
        })

    return {
        "source": "memory",
        "memories": memories,
        "entities": entities,
        "entity_relationships": entity_relationships,
        "facts": facts,
        "evidence_events": evidence,
    }


def _mock_entity_extract_query(query: str) -> list:
    """Return mock entities from query for NER. No LLM."""
    q = (query or "").lower()
    out = []
    if "jon" in q:
        out.append({"name": "Jon", "type": "Person"})
    if "luna" in q:
        out.append({"name": "Luna", "type": "Concept"})
    if "raleigh" in q:
        out.append({"name": "Raleigh", "type": "City"})
    if "durham" in q:
        out.append({"name": "Durham", "type": "City"})
    return out if out else [{"name": "placeholder", "type": "Concept"}]


# Set Mnemo env before any test loads shared state (no monkeypatch needed for env)
def _ensure_p11_env():
    os.environ.setdefault("VECTOR_STORE_PROVIDER", "qdrant")
    os.environ.setdefault("RAG_VECTOR_STORE_PROVIDER", "qdrant")
    os.environ.setdefault("EPISODIC_STORE_PROVIDER", "qdrant")
    os.environ.setdefault("NEO4J_ENABLED", "true")
    os.environ.setdefault("MNEMO_ENABLED", "true")
    os.environ.setdefault("ASYNC_KG_INGEST", "false")
    os.environ.setdefault("SYNC_ENGINE_ENABLED", "true")
    os.environ.setdefault("SYNC_SERVER_URL", "http://localhost:8000/api")
    os.environ.setdefault("SEMANTIC_EMBEDDING", "true")  # word-overlap for recommend-space/retrieval assertions


_ensure_p11_env()


@pytest.fixture(scope="module")
def p11_llm_mocks():
    """Patch all LLM calls so Gemini/Ollama are never invoked."""
    patches = [
        patch("remme.utils.get_embedding", side_effect=_fake_embedding),
        patch("routers.remme.get_embedding", side_effect=_fake_embedding),
        patch("routers.runs.get_embedding", side_effect=_fake_embedding),
        patch("memory.memory_retriever.get_embedding", side_effect=lambda t, **kw: _fake_embedding(t, kw.get("task_type", "search_query"))),
    ]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture(scope="module")
def p11_full_mocks():
    """Patch all LLM calls: embedding, unified extractor, entity extractor."""
    from memory.unified_extraction_schema import UnifiedExtractionResult

    def _extract_memory_text(text: str):
        return UnifiedExtractionResult(**_mock_unified_extraction(text))

    def _extract_session(query, hist, existing):
        combined = query + " " + " ".join(
            str(m.get("content", "")) for m in (hist or [])[-5:]
        )
        return UnifiedExtractionResult(**_mock_unified_extraction(combined))

    mock_unified = MagicMock()
    mock_unified.extract_from_memory_text = _extract_memory_text
    mock_unified.extract_from_session = _extract_session

    mock_entity_inst = MagicMock()
    mock_entity_inst.extract_from_query = _mock_entity_extract_query

    def _embed(text, task_type="search_document"):
        return _get_semantic_embedding(text, task_type)

    # memory_retriever imports get_embedding from remme.utils inside its function; patching remme.utils suffices
    patches = [
        patch("remme.utils.get_embedding", side_effect=_embed),
        patch("routers.remme.get_embedding", side_effect=_embed),
        patch("routers.runs.get_embedding", side_effect=_embed),
        patch("shared.state.get_unified_extractor", return_value=mock_unified),
        patch("memory.entity_extractor.EntityExtractor", return_value=mock_entity_inst),
    ]
    for p in patches:
        p.start()
    yield
    for p in reversed(patches):
        p.stop()


@pytest.fixture
def client(p11_full_mocks):
    """TestClient with auth headers and LLM mocks."""
    from fastapi.testclient import TestClient
    from api import app
    return TestClient(app, headers=AUTH_HEADERS)


def _qdrant_available() -> bool:
    try:
        from qdrant_client import QdrantClient
        from memory.qdrant_config import get_qdrant_url, get_qdrant_api_key
        QdrantClient(url=get_qdrant_url(), api_key=get_qdrant_api_key(), timeout=2)
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
    """Skip if Qdrant or Neo4j not available."""
    return pytest.mark.skipif(
        not _qdrant_available() or not _neo4j_available(),
        reason="Qdrant and/or Neo4j not available (start services to run automation)",
    )(f)
