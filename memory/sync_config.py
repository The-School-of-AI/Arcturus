"""
P11 Phase 4 Sync Engine — config and feature flag.

When SYNC_ENGINE_ENABLED=true: sync engine runs push/pull to central sync server.
Requires SYNC_SERVER_URL for remote sync. DEVICE_ID identifies this device (default: generated UUID).
"""

import json
import os
import uuid
from pathlib import Path

_DEVICE_ID_PATH = Path(__file__).parent.parent / "memory" / "remme_index" / "device_id.json"
_CACHED_DEVICE_ID: str | None = None


def is_sync_engine_enabled() -> bool:
    """True when sync engine should run (push/pull)."""
    return os.environ.get("SYNC_ENGINE_ENABLED", "").lower() in ("true", "1", "yes")


def get_sync_server_url() -> str:
    """Sync server base URL (e.g. https://api.example.com). Empty if not configured."""
    return (os.environ.get("SYNC_SERVER_URL") or "").rstrip("/")


def get_device_id() -> str:
    """
    Return device ID. Reads from DEVICE_ID env; otherwise generates UUID and caches to file.
    """
    env_id = os.environ.get("DEVICE_ID")
    if env_id:
        return env_id
    global _CACHED_DEVICE_ID
    if _CACHED_DEVICE_ID is not None:
        return _CACHED_DEVICE_ID
    _DEVICE_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _DEVICE_ID_PATH.exists():
        try:
            data = json.loads(_DEVICE_ID_PATH.read_text())
            _CACHED_DEVICE_ID = data.get("device_id", "")
            if _CACHED_DEVICE_ID:
                return _CACHED_DEVICE_ID
        except Exception:
            pass
    did = str(uuid.uuid4())
    _DEVICE_ID_PATH.write_text(json.dumps({"device_id": did}, indent=2))
    _CACHED_DEVICE_ID = did
    return did
