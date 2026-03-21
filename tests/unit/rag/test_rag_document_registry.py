"""Unit tests for RAGDocumentRegistry (mocked Qdrant)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root in path
ROOT = Path(__file__).parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def mock_qdrant_client():
    client = MagicMock()
    # scroll returns (points, next_offset)
    client.scroll.return_value = ([], None)
    client.get_collections.return_value = MagicMock(collections=[MagicMock(name="test_rag_documents")])
    return client


def test_registry_upsert_calls_client(mock_qdrant_client):
    with patch("memory.rag_document_registry.QdrantClient", return_value=mock_qdrant_client):
        with patch("memory.rag_document_registry._ensure_registry_collection"):
            from memory.rag_document_registry import RAGDocumentRegistry

            reg = RAGDocumentRegistry(collection_name="test_rag_documents")
            reg.client = mock_qdrant_client

            reg.upsert_doc(doc="Notes/__global__/x.md", user_id="user1", space_id="__global__", chunk_count=5)
            mock_qdrant_client.upsert.assert_called_once()
            call_kw = mock_qdrant_client.upsert.call_args
            assert call_kw[1]["collection_name"] == "test_rag_documents"
            points = call_kw[1]["points"]
            assert len(points) == 1
            payload = points[0].payload
            assert payload["doc"] == "Notes/__global__/x.md"
            assert payload["chunk_count"] == 5


def test_registry_delete_calls_client(mock_qdrant_client):
    with patch("memory.rag_document_registry.QdrantClient", return_value=mock_qdrant_client):
        with patch("memory.rag_document_registry._ensure_registry_collection"):
            from memory.rag_document_registry import RAGDocumentRegistry

            reg = RAGDocumentRegistry(collection_name="test_rag_documents")
            reg.client = mock_qdrant_client

            reg.delete_doc(doc="Notes/__global__/x.md", user_id="user1")
            mock_qdrant_client.delete.assert_called_once()


def test_registry_list_documents_returns_from_scroll(mock_qdrant_client):
    from memory.rag_document_registry import RAGDocumentRegistry

    # Create a mock point with payload
    mock_point = MagicMock()
    mock_point.payload = {"doc": "Notes/__global__/a.md", "space_id": "__global__", "chunk_count": 2}
    mock_qdrant_client.scroll.return_value = ([mock_point], None)

    with patch("memory.rag_document_registry.QdrantClient", return_value=mock_qdrant_client):
        with patch("memory.rag_document_registry._ensure_registry_collection"):
            reg = RAGDocumentRegistry(collection_name="test_rag_documents")
            reg.client = mock_qdrant_client
            reg._is_tenant = False

            docs = reg.list_documents(user_id=None, space_id=None)
            assert len(docs) == 1
            assert docs[0]["doc"] == "Notes/__global__/a.md"
            assert docs[0]["chunk_count"] == 2
