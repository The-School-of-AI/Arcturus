"""
Local user ID for multi-tenant memory isolation.

Generates a random UUID on first use and caches it to disk.
All subsequent requests use the same cached user_id.
"""

import json
import uuid
from pathlib import Path

_USER_ID_PATH = Path(__file__).parent.parent / "memory" / "remme_index" / "user_id.json"
_CACHED_USER_ID: str | None = None


def get_user_id() -> str:
    """
    Return the local user ID. Generates a UUID on first call and caches to file.
    """
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
