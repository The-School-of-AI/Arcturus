"""
Load and resolve Qdrant collection configs from config/qdrant_config.yaml.
"""

from pathlib import Path
from typing import Dict, Any, Optional

import yaml

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "qdrant_config.yaml"
_CACHE: Optional[Dict[str, Any]] = None


def _load_config() -> Dict[str, Any]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    if not _CONFIG_PATH.exists():
        _CACHE = {"default_collection": "arcturus_memories", "collections": {}}
        return _CACHE
    _CACHE = yaml.safe_load(_CONFIG_PATH.read_text()) or {}
    return _CACHE


def get_collection_config(collection_name: str) -> Dict[str, Any]:
    """
    Return config for a collection. Uses defaults if not in YAML.

    Returns:
        Dict with keys: dimension, distance, and any collection-specific settings.
    """
    cfg = _load_config()
    collections = cfg.get("collections", {})
    spec = collections.get(collection_name, {}).copy()
    # Apply defaults
    spec.setdefault("dimension", 768)
    spec.setdefault("distance", "cosine")
    return spec


def get_default_collection() -> str:
    """Return the default collection name from config."""
    cfg = _load_config()
    return cfg.get("default_collection", "arcturus_memories")


def list_collections() -> list[str]:
    """Return names of all configured collections."""
    cfg = _load_config()
    return list(cfg.get("collections", {}).keys())
