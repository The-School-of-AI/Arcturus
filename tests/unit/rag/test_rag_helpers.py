"""Unit tests for shared.rag_helpers."""

import pytest
from pathlib import Path

# Ensure project root in path
import sys
ROOT = Path(__file__).parent.parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_resolve_rag_path_notes_global():
    from shared.rag_helpers import resolve_rag_path

    assert resolve_rag_path("", "__global__", "notes") == "Notes/__global__"
    assert resolve_rag_path("foo.md", "__global__", "notes") == "Notes/__global__/foo.md"
    assert resolve_rag_path("folder/foo.md", "__global__", "notes") == "Notes/__global__/folder/foo.md"


def test_resolve_rag_path_notes_space_uuid():
    from shared.rag_helpers import resolve_rag_path

    uuid = "550e8400-e29b-41d4-a716-446655440000"
    assert resolve_rag_path("", uuid, "notes") == f"Notes/{uuid}"
    assert resolve_rag_path("bar.md", uuid, "notes") == f"Notes/{uuid}/bar.md"
    assert resolve_rag_path("a/b/c.md", uuid, "notes") == f"Notes/{uuid}/a/b/c.md"


def test_resolve_rag_path_normalizes():
    from shared.rag_helpers import resolve_rag_path

    assert resolve_rag_path("  foo/bar  ", "__global__", "notes") == "Notes/__global__/foo/bar"
    # .. is replaced with "" (path traversal removed), result is foo//bar
    assert resolve_rag_path("foo/../bar", "__global__", "notes") == "Notes/__global__/foo//bar"


def test_resolve_rag_path_rag_context():
    from shared.rag_helpers import resolve_rag_path

    uuid = "550e8400-e29b-41d4-a716-446655440000"
    assert resolve_rag_path("docs/file.pdf", "__global__", "rag") == "docs/file.pdf"
    assert resolve_rag_path("docs/file.pdf", uuid, "rag") == f"{uuid}/docs/file.pdf"


def test_get_rag_user_and_space_no_auth():
    from shared.rag_helpers import get_rag_user_and_space

    # Without auth/user_id module, may return (None, None) or use memory.user_id
    uid, sid = get_rag_user_and_space(None)
    # sid=None when query param is None
    assert sid is None or sid == "__global__"

    uid2, sid2 = get_rag_user_and_space("__global__")
    assert sid2 is None  # __global__ is normalized to None for "all"

    uid3, sid3 = get_rag_user_and_space("550e8400-e29b-41d4-a716-446655440000")
    assert sid3 == "550e8400-e29b-41d4-a716-446655440000"
