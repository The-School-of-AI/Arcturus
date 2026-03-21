"""Unit tests for memory.rag_storage (local mode)."""

import sys
import uuid
from pathlib import Path

import pytest

# Ensure project root in path
ROOT = Path(__file__).parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_rag_storage_local_read_write(monkeypatch):
    """Test read_doc, write_doc, exists_doc with local FS (no S3)."""
    monkeypatch.delenv("RAG_S3_BUCKET", raising=False)
    import memory.rag_storage as storage

    # Use unique path under project data to avoid collisions
    suffix = uuid.uuid4().hex[:8]
    doc = f"Notes/__global__/test_rag_unit_{suffix}.md"
    content = b"# Hello World"
    try:
        assert storage.write_doc(doc, content) is True
        assert storage.exists_doc(doc) is True
        read_back = storage.read_doc(doc)
        assert read_back == content
    finally:
        p = storage.DATA_ROOT / doc
        if p.exists():
            p.unlink()

    assert storage.read_doc("nonexistent_xyz_123/file.md") is None
    assert storage.exists_doc("nonexistent_xyz_123/file.md") is False


def test_rag_storage_normalizes_path(monkeypatch):
    """Test that doc paths are normalized."""
    monkeypatch.delenv("RAG_S3_BUCKET", raising=False)
    import memory.rag_storage as storage

    suffix = uuid.uuid4().hex[:8]
    doc = f"Notes/__global__/test_norm_{suffix}.md"
    content = b"test"
    try:
        assert storage.write_doc(doc, content) is True
        assert storage.read_doc(doc) == content
    finally:
        p = storage.DATA_ROOT / doc
        if p.exists():
            p.unlink()


def test_rag_storage_empty_doc_returns_none(monkeypatch):
    monkeypatch.delenv("RAG_S3_BUCKET", raising=False)
    import memory.rag_storage as storage

    assert storage.read_doc("") is None
    assert storage.exists_doc("") is False
    assert storage.write_doc("", b"x") is False
