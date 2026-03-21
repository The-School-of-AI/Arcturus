"""Integration tests for RAG Qdrant flows using test_rag_chunks and test_rag_documents.

Requires Qdrant running (e.g. docker-compose up -d). Skips if QDRANT_URL unreachable.
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _qdrant_reachable() -> bool:
    try:
        from qdrant_client import QdrantClient
        from memory.qdrant_config import get_qdrant_url, get_qdrant_api_key
        url = get_qdrant_url()
        api_key = get_qdrant_api_key()
        c = QdrantClient(url=url, api_key=api_key, timeout=2.0)
        c.get_collections()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _qdrant_reachable(), reason="Qdrant not reachable")


@pytest.fixture(autouse=True)
def use_test_collections(monkeypatch):
    """Use test collections for integration tests."""
    monkeypatch.setenv("RAG_VECTOR_STORE_PROVIDER", "qdrant")
    monkeypatch.setenv("RAG_DOCUMENT_SOURCE", "qdrant")


def test_registry_upsert_and_list():
    """Test document registry upsert + list using test_rag_documents."""
    from memory.rag_document_registry import RAGDocumentRegistry

    reg = RAGDocumentRegistry(collection_name="test_rag_documents")
    doc = "Notes/__global__/integration_test_doc.md"
    try:
        reg.upsert_doc(doc=doc, user_id="", space_id="__global__", chunk_count=1)
        docs = reg.list_documents(user_id=None, space_id="__global__")
        found = [d for d in docs if d["doc"] == doc]
        assert len(found) >= 1
        assert found[0]["chunk_count"] == 1
    finally:
        reg.delete_doc(doc, user_id=None)


def test_get_rag_documents_from_registry():
    """Test GET /rag/documents returns tree when RAG_DOCUMENT_SOURCE=qdrant."""
    from fastapi.testclient import TestClient

    # Ensure test doc exists
    from memory.rag_document_registry import RAGDocumentRegistry
    reg = RAGDocumentRegistry(collection_name="test_rag_documents")
    doc = "Notes/__global__/integration_tree_test.md"
    reg.upsert_doc(doc=doc, user_id="", space_id="__global__", chunk_count=1)

    try:
        from api import app
        client = TestClient(app)
        resp = client.get("/api/rag/documents", params={"space_id": "__global__"})
        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data
        # Tree may be empty if no user_id in auth context; we just check no error
    finally:
        reg.delete_doc(doc, user_id=None)


def test_document_content_via_rag_storage(tmp_path):
    """Test GET /rag/document_content serves a file from data/."""
    from fastapi.testclient import TestClient

    # Create a real file under data/
    test_file = ROOT / "data" / "Notes" / "__global__"
    test_file.mkdir(parents=True, exist_ok=True)
    test_path = test_file / "integration_content_test.md"
    test_path.write_text("# Test Content")

    try:
        from api import app
        client = TestClient(app)
        resp = client.get("/api/rag/document_content", params={"path": "Notes/__global__/integration_content_test.md"})
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data
        assert "Test Content" in data["content"]
    finally:
        if test_path.exists():
            test_path.unlink()
