"""
Feature Flag Store: JSON-file-backed feature toggle system.

Two flag types:
- **Request-based**: Guard checks in code paths. Instant effect.
- **Lifecycle-managed**: Toggle endpoint calls stop()/start() on
  running services via app.state (handled in routers/admin.py).

Usage::

    from ops.admin.feature_flags import flag_store

    if flag_store.get("deep_research"):
        run_deep_research(query)
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("watchtower.flags")

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
_DEFAULT_FLAGS_PATH = _CONFIG_DIR / "feature_flags.json"

# Flags that require lifecycle management (stop/start of background services).
# When toggled, routers/admin.py calls the actual service stop()/start() hooks.
LIFECYCLE_FLAGS = frozenset({"voice_wake", "health_scheduler"})

# Default flag values created on first access when file is missing.
_DEFAULTS: Dict[str, bool] = {
    "deep_research": True,
    "voice_wake": True,
    "multi_agent": False,
    "cost_tracking": True,
    "semantic_cache": True,
    "health_scheduler": True,
}


class FeatureFlagStore:
    """Thread-safe, JSON-file-backed feature flag store."""

    def __init__(self, path: Optional[Path] = None):
        self._path = path or _DEFAULT_FLAGS_PATH
        self._lock = threading.Lock()
        self._ensure_file()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, name: str, default: bool = False) -> bool:
        """Return flag value. Falls back to *default* if flag is undefined."""
        flags = self._read()
        return flags.get(name, default)

    def set(self, name: str, enabled: bool) -> Dict[str, Any]:
        """Set a flag value. Returns the updated flag entry."""
        with self._lock:
            flags = self._read()
            flags[name] = enabled
            self._write(flags)
        logger.info("Flag '%s' set to %s", name, enabled)
        return {"name": name, "enabled": enabled, "lifecycle": name in LIFECYCLE_FLAGS}

    def delete(self, name: str) -> bool:
        """Delete a flag. Returns True if it existed."""
        with self._lock:
            flags = self._read()
            existed = name in flags
            flags.pop(name, None)
            self._write(flags)
        if existed:
            logger.info("Flag '%s' deleted", name)
        return existed

    def list_all(self) -> list[Dict[str, Any]]:
        """Return all flags as a list of dicts."""
        flags = self._read()
        return [
            {
                "name": k,
                "enabled": v,
                "lifecycle": k in LIFECYCLE_FLAGS,
            }
            for k, v in sorted(flags.items())
        ]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_file(self) -> None:
        """Create the flags file with defaults if it doesn't exist."""
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._write(_DEFAULTS.copy())
            logger.info("Created default feature flags at %s", self._path)

    def _read(self) -> Dict[str, bool]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return _DEFAULTS.copy()

    def _write(self, flags: Dict[str, bool]) -> None:
        self._path.write_text(
            json.dumps(flags, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


# Module-level singleton (import and use directly).
flag_store = FeatureFlagStore()
