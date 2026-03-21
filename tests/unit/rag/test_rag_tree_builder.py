"""Unit tests for _doc_list_to_tree in routers/rag."""

import sys
from pathlib import Path

import pytest

# Ensure project root in path
ROOT = Path(__file__).parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_doc_list_to_tree_single_file():
    from routers.rag import _doc_list_to_tree

    doc_list = [{"doc": "Notes/__global__/foo.md", "chunk_count": 5}]
    tree = _doc_list_to_tree(doc_list, ROOT / "data")
    assert len(tree) >= 1
    notes = next((n for n in tree if n.get("name") == "Notes"), None)
    assert notes is not None
    assert notes.get("type") == "folder"
    assert notes.get("children")
    # Should have __global__ folder
    global_node = next((c for c in notes["children"] if c.get("name") == "__global__"), None)
    assert global_node is not None
    foo = next((c for c in global_node.get("children", []) if c.get("name") == "foo.md"), None)
    assert foo is not None
    assert foo.get("chunk_count") == 5
    assert foo.get("indexed") is True


def test_doc_list_to_tree_multiple_docs():
    from routers.rag import _doc_list_to_tree

    doc_list = [
        {"doc": "Notes/__global__/a.md", "chunk_count": 2},
        {"doc": "Notes/__global__/b.md", "chunk_count": 3},
        {"doc": "pdfs/doc.pdf", "chunk_count": 10},
    ]
    tree = _doc_list_to_tree(doc_list, ROOT / "data")
    roots = [n.get("name") for n in tree]
    assert "Notes" in roots
    assert "pdfs" in roots


def test_doc_list_to_tree_empty():
    from routers.rag import _doc_list_to_tree

    tree = _doc_list_to_tree([], ROOT / "data")
    assert tree == []


def test_filter_tree_by_space():
    from routers.rag import _filter_tree_by_space

    items = [
        {"name": "__global__", "type": "folder", "children": []},
        {"name": "550e8400-e29b-41d4-a716-446655440000", "type": "folder", "children": []},
    ]
    filtered = _filter_tree_by_space(items, "__global__")
    assert len(filtered) == 1
    assert filtered[0]["name"] == "__global__"

    filtered2 = _filter_tree_by_space(items, "550e8400-e29b-41d4-a716-446655440000")
    assert len(filtered2) == 1
    assert filtered2[0]["name"] == "550e8400-e29b-41d4-a716-446655440000"
