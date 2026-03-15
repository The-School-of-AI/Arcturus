"""Episodic memory module: stores and retrieves session skeleton recipes.

Phase B: Reads from Qdrant (arcturus_episodic) when EPISODIC_STORE_PROVIDER=qdrant (default).
When EPISODIC_STORE_PROVIDER=legacy, reads/writes local memory/episodic_skeletons/skeleton_*.json
for users who have not migrated to Qdrant yet.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from shared.state import PROJECT_ROOT

# Directory for legacy: read/write skeleton_*.json when EPISODIC_STORE_PROVIDER=legacy
MEMORY_DIR = PROJECT_ROOT / "memory" / "episodic_skeletons"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# Env: qdrant | legacy (default qdrant). When legacy, use local JSON only.
EPISODIC_STORE_PROVIDER_ENV = "EPISODIC_STORE_PROVIDER"

_episodic_store = None


def get_episodic_store_provider() -> str:
    """Return 'qdrant' or 'legacy'. Default qdrant."""
    p = (os.environ.get(EPISODIC_STORE_PROVIDER_ENV) or "qdrant").strip().lower()
    return p if p in ("qdrant", "legacy") else "qdrant"


def _get_episodic_store():
    """Lazy init episodic Qdrant store. Returns None when provider is legacy."""
    if get_episodic_store_provider() != "qdrant":
        return None
    global _episodic_store
    if _episodic_store is None:
        try:
            from memory.backends.episodic_qdrant_store import EpisodicQdrantStore
            _episodic_store = EpisodicQdrantStore()
        except Exception as e:
            from core.utils import log_error
            log_error(f"Episodic Qdrant store init failed: {e}")
            return None
    return _episodic_store


def _build_searchable_text(skeleton: dict) -> str:
    """Build text for embedding from skeleton (mirrors core.episodic_memory)."""
    parts = [str(skeleton.get("original_query", ""))]
    for node in skeleton.get("nodes", []):
        task_goal = node.get("task_goal") or node.get("description")
        if task_goal:
            parts.append(str(task_goal)[:300])
        inst = node.get("instruction")
        if inst:
            parts.append(str(inst)[:300])
    return "\n".join(p for p in parts if p and str(p).strip())


def _legacy_get_recent(limit: int) -> list[dict[str, Any]]:
    """Read recent episodes from local skeleton_*.json (sorted by mtime desc)."""
    if not MEMORY_DIR.exists():
        return []
    files = sorted(
        MEMORY_DIR.glob("skeleton_*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    out = []
    for f in files[:limit]:
        try:
            sk = json.loads(f.read_text())
            sid = sk.get("id", f.stem.replace("skeleton_", ""))
            out.append({
                "id": sid,
                "session_id": sid,
                "skeleton_json": json.dumps(sk),
                **sk,
            })
        except Exception:
            continue
    return out


def _legacy_search(query: str, limit: int) -> list[dict[str, Any]]:
    """Search legacy episodes: load recent files, embed query + texts, cosine sim."""
    if not MEMORY_DIR.exists():
        return []
    files = sorted(
        MEMORY_DIR.glob("skeleton_*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )[:200]
    if not files:
        return []
    skeletons = []
    for f in files:
        try:
            sk = json.loads(f.read_text())
            skeletons.append(sk)
        except Exception:
            continue
    if not skeletons:
        return []
    try:
        from remme.utils import get_embedding
        import numpy as np
        query_emb = np.array(get_embedding(query, task_type="search_query"), dtype=np.float32)
        texts = [_build_searchable_text(sk) or str(sk.get("original_query", "")) for sk in skeletons]
        if not any(t.strip() for t in texts):
            return _legacy_get_recent(limit)
        embs = [get_embedding(t or " ", task_type="search_document") for t in texts]
        embs = np.array(embs, dtype=np.float32)
        dots = np.dot(embs, query_emb)
        norms_q = np.linalg.norm(query_emb)
        norms = np.linalg.norm(embs, axis=1)
        norms = np.where(norms == 0, 1e-9, norms)
        scores = dots / (norms * norms_q)
        order = np.argsort(scores)[::-1][:limit]
        out = []
        for i in order:
            sk = skeletons[i]
            sid = sk.get("id", "")
            out.append({"id": sid, "session_id": sid, "skeleton_json": json.dumps(sk), **sk})
        return out
    except Exception as e:
        from core.utils import log_error
        log_error(f"Episodic legacy search failed: {e}")
        return _legacy_get_recent(limit)


def search_episodes(
    query: str,
    limit: int = 5,
    user_id: Optional[str] = None,
    space_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Search relevant past episodes. Qdrant when provider=qdrant; local JSON when legacy (user/space filters ignored for legacy)."""
    if get_episodic_store_provider() == "legacy":
        return _legacy_search(query, limit=limit)
    store = _get_episodic_store()
    if not store:
        return []
    try:
        from remme.utils import get_embedding
        emb = get_embedding(query, task_type="search_query")
        results = store.search(emb, limit=limit, user_id=user_id, space_id=space_id)
        return results
    except Exception as e:
        from core.utils import log_error
        log_error(f"search_episodes failed: {e}")
        return []


def get_recent_episodes(
    limit: int = 10,
    user_id: Optional[str] = None,
    space_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Return most recent episodes. Qdrant when provider=qdrant; local JSON when legacy (user/space ignored for legacy)."""
    if get_episodic_store_provider() == "legacy":
        return _legacy_get_recent(limit)
    store = _get_episodic_store()
    if not store:
        return []
    try:
        return store.get_recent(limit=limit, user_id=user_id, space_id=space_id)
    except Exception as e:
        from core.utils import log_error
        log_error(f"get_recent_episodes failed: {e}")
        return []
