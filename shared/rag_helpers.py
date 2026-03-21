"""
RAG path resolution and user/space helpers.

Backend-only path logic: resolve_rag_path builds canonical doc paths from
relative paths + space_id. Frontend should never construct Notes/<uuid>/.
"""

from pathlib import Path
from typing import Optional, Tuple

from memory.space_constants import SPACE_ID_GLOBAL

PROJECT_ROOT = Path(__file__).parent.parent
DATA_ROOT = PROJECT_ROOT / "data"


def resolve_rag_path(
    relative_path: str,
    space_id: Optional[str],
    context: str = "notes",
) -> str:
    """
    Build canonical doc path (relative to data/) from relative_path + space_id.

    For Notes: Notes/<space_id>/<relative_path> (or Notes/__global__/ when space is Global).
    For RAG (non-Notes): if space_id, could use top-level <space_id>/<path>; else <path>.

    Args:
        relative_path: User-relative path (e.g. "MyFolder/note.md", "Subfolder").
        space_id: Space UUID or __global__ or None (treated as __global__).
        context: "notes" or "rag".

    Returns:
        Canonical path like Notes/__global__/MyFolder/note.md or Notes/<uuid>/Subfolder.
    """
    clean = relative_path.strip().strip("/").replace("..", "").strip("/")
    sid = (space_id or SPACE_ID_GLOBAL).strip() or SPACE_ID_GLOBAL

    if context == "notes":
        return f"Notes/{sid}/{clean}" if clean else f"Notes/{sid}"
    # For general RAG uploads outside Notes
    return f"{sid}/{clean}" if sid != SPACE_ID_GLOBAL and clean else clean or sid


def get_rag_user_and_space(
    space_id_from_query: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve (user_id, space_id) for RAG routes.
    Uses auth context when available; space_id from query param.
    """
    user_id = None
    try:
        from core.auth.context import get_current_user_id
        user_id = get_current_user_id()
    except Exception:
        pass
    if not user_id:
        try:
            from memory.user_id import get_user_id
            user_id = get_user_id()
        except Exception:
            pass

    space_id = space_id_from_query
    if space_id == "__global__" or space_id == "":
        space_id = None  # None means "all" for listing
    return user_id, space_id


def _derive_space_id_for_path(rel_path: str, default_space_id: Optional[str]) -> str:
    """For path already on disk: derive space_id from path (Notes/__global__/ or Notes/<uuid>/)."""
    norm = rel_path.replace("\\", "/").strip("/")
    if not norm.lower().startswith("notes/"):
        return default_space_id or SPACE_ID_GLOBAL
    parts = norm.split("/")
    if len(parts) >= 2:
        first = parts[1]
        if first == "__global__":
            return SPACE_ID_GLOBAL
        import uuid as _uuid
        try:
            _uuid.UUID(first)
            return first
        except (ValueError, TypeError):
            pass
    return default_space_id or SPACE_ID_GLOBAL
