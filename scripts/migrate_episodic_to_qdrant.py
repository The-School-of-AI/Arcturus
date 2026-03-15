#!/usr/bin/env python3
"""
Migrate episodic skeletons from memory/episodic_skeletons/*.json to Qdrant arcturus_episodic.

Phase B: Reads local skeleton files, embeds searchable text, writes to Qdrant
with user_id and space_id=__global__ for legacy episodes.

Usage:
    export VITE_ENABLE_LOCAL_MIGRATION=true  # if no auth context
    uv run python scripts/migrate_episodic_to_qdrant.py
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from memory.user_id import get_user_id
from memory.space_constants import SPACE_ID_GLOBAL
from memory.backends.episodic_qdrant_store import EpisodicQdrantStore
from core.utils import log_step, log_error


def _build_searchable_text(skeleton: dict) -> str:
    """Build text for embedding: original_query + condensed node descriptions."""
    parts = [str(skeleton.get("original_query", ""))]
    for node in skeleton.get("nodes", []):
        task_goal = node.get("task_goal") or node.get("description")
        if task_goal:
            parts.append(str(task_goal)[:300])
        inst = node.get("instruction")
        if inst:
            parts.append(str(inst)[:300])
    return "\n".join(p for p in parts if p and p.strip()) or str(skeleton.get("original_query", ""))


def get_embedding(text: str) -> np.ndarray:
    """Embed via remme.utils (Ollama)."""
    from remme.utils import get_embedding as _get_embedding
    return _get_embedding(text, task_type="search_document")


def migrate() -> int:
    """Migrate episodic_skeletons to Qdrant. Returns count migrated."""
    print("=" * 60)
    print("Episodic Skeletons → Qdrant Migration")
    print("=" * 60)

    user_id = get_user_id()
    print(f"\n✓ User ID: {user_id[:8]}...")

    mem_dir = ROOT / "memory" / "episodic_skeletons"
    if not mem_dir.exists():
        print("\nNo episodic_skeletons directory. Nothing to migrate.")
        return 0

    files = list(mem_dir.glob("skeleton_*.json"))
    if not files:
        print("\nNo skeleton_*.json files. Nothing to migrate.")
        return 0

    print(f"\nFound {len(files)} skeleton files.")

    store = EpisodicQdrantStore()
    migrated = 0

    for fp in files:
        try:
            skeleton = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            log_error(f"Failed to load {fp.name}: {e}")
            continue

        session_id = skeleton.get("id")
        if not session_id:
            log_error(f"Skipping {fp.name}: no id")
            continue

        searchable_text = _build_searchable_text(skeleton)
        try:
            emb = get_embedding(searchable_text)
        except Exception as e:
            log_error(f"Embedding failed for {fp.name}: {e}")
            continue

        try:
            store.upsert(
                session_id=str(session_id),
                searchable_text=searchable_text,
                embedding=emb,
                skeleton_json=json.dumps(skeleton),
                original_query=str(skeleton.get("original_query", "")),
                outcome=str(skeleton.get("outcome", "completed")),
                user_id=user_id,
                space_id=SPACE_ID_GLOBAL,
            )
            migrated += 1
            print(f"  ✓ {fp.name}")
        except Exception as e:
            log_error(f"Upsert failed for {fp.name}: {e}")

    print(f"\n✓ Migrated {migrated}/{len(files)} episodic skeletons.")
    return migrated


def main() -> int:
    try:
        migrate()
        return 0
    except Exception as e:
        log_error(str(e))
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
