"""
Local user ID for multi-tenant memory isolation.

Reads user_id from the current request's auth context (JWT or X-User-Id).
When there is no request context (e.g. migration scripts), fallback to file
read/generate is only allowed when VITE_ENABLE_LOCAL_MIGRATION=true (local/dev only;
must be false in production).
"""

import json
import uuid
import os
from pathlib import Path

from core.auth.context import get_current_user_id

_USER_ID_PATH = Path(__file__).parent.parent / "memory" / "remme_index" / "user_id.json"
_CACHED_USER_ID: str | None = None


def is_auth_enabled() -> bool:
    """Check if Phase 5 Auth mechanism (JWT/Header context) is enabled."""
    return os.environ.get("AUTH_ENABLED", "true").lower() == "true"


def _is_local_migration_enabled() -> bool:
    """
    True when local migration fallback is allowed (read/generate user_id from file).
    Must be false in production; set VITE_ENABLE_LOCAL_MIGRATION=true only for
    local migration scripts (e.g. migrate_all_memories.py).
    """
    return os.environ.get("VITE_ENABLE_LOCAL_MIGRATION", "false").lower() in ("true", "1", "yes")


def get_user_id() -> str:
    """
    Return the local user ID.
    1. Reads from FastAPI Auth Context / headers if Phase 5 Auth is enabled.
    2. If no context and VITE_ENABLE_LOCAL_MIGRATION=true: legacy fallback (read file or generate and cache).
    3. If no context and VITE_ENABLE_LOCAL_MIGRATION=false: raise (production-safe; no server-side generation).
    """
    # 1. Request context (JWT or X-User-Id from AuthMiddleware)
    if is_auth_enabled():
        ctx_user_id = get_current_user_id()
        if ctx_user_id:
            return ctx_user_id
        # Note: AuthMiddleware protects the routes. If we reach here without a user,
        # it might be a background task or public route. 
        # No user in context (e.g. background script, migration). Only allow file fallback when explicitly enabled.
        if not _is_local_migration_enabled():
            raise RuntimeError(
                "No user_id in request context and VITE_ENABLE_LOCAL_MIGRATION is not enabled. "
                "Set VITE_ENABLE_LOCAL_MIGRATION=true only for local migration scripts; keep false in production."
            )

    # 2. Legacy fallback (only when VITE_ENABLE_LOCAL_MIGRATION=true)
    global _CACHED_USER_ID
    if _CACHED_USER_ID is not None:
        return _CACHED_USER_ID
    _USER_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _USER_ID_PATH.exists():
        try:
            data = json.loads(_USER_ID_PATH.read_text())
            _CACHED_USER_ID = data.get("user_id", "")
            if _CACHED_USER_ID:
                return _CACHED_USER_ID
        except Exception:
            pass
    uid = str(uuid.uuid4())
    _USER_ID_PATH.write_text(json.dumps({"user_id": uid}, indent=2))
    _CACHED_USER_ID = uid
    return uid
