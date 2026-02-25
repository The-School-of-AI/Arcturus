#!/usr/bin/env python3
"""
Migrate FAISS memories to Qdrant arcturus_memories collection.

Reads memories from memory/remme_index (memories.json + index.bin),
ensures user_id exists in memory/remme_index/user_id.json (creates if missing),
and adds each memory to the Qdrant collection with the user_id.

Usage:
    export VECTOR_STORE_PROVIDER=qdrant
    docker-compose up -d   # ensure Qdrant is running
    uv run python scripts/migrate_faiss_to_qdrant.py
"""

import json
import sys
from pathlib import Path

import faiss
import numpy as np

# Add project root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from memory.user_id import get_user_id
from memory.vector_store import get_vector_store
from core.utils import log_step, log_error


def ensure_user_id() -> str:
    """
    Read or create user_id in memory/remme_index/user_id.json.
    Uses get_user_id() which handles create-if-missing.
    """
    return get_user_id()


def load_faiss_memories(persistence_dir: str = "memory/remme_index") -> tuple[list[dict], faiss.Index | None]:
    """
    Load memories metadata and FAISS index.
    Returns (memories, index) or ([], None) if no data.
    """
    root = ROOT / persistence_dir
    metadata_path = root / "memories.json"
    index_path = root / "index.bin"

    memories = []
    if metadata_path.exists():
        try:
            memories = json.loads(metadata_path.read_text())
        except Exception as e:
            log_error(f"Failed to load memories.json: {e}")
            return [], None

    if not memories:
        print("No memories to migrate.")
        return [], None

    index = None
    if index_path.exists():
        try:
            index = faiss.read_index(str(index_path))
        except Exception as e:
            log_error(f"Failed to load FAISS index: {e}")
            return memories, None

    return memories, index


def migrate():
    """Run the migration."""
    print("=" * 60)
    print("FAISS → Qdrant Migration")
    print("=" * 60)

    # 1. Ensure user_id exists (read or create memory/remme_index/user_id.json)
    user_id = ensure_user_id()
    print(f"\n✓ User ID: {user_id[:8]}... (from memory/remme_index/user_id.json)")

    # 2. Load FAISS data
    memories, faiss_index = load_faiss_memories()
    if not memories:
        print("\nNo memories to migrate. Exiting.")
        return

    print(f"\n✓ Loaded {len(memories)} memories from FAISS")

    # 3. Initialize Qdrant store
    store = get_vector_store(provider="qdrant")
    existing_count = store.count()
    print(f"✓ Qdrant arcturus_memories has {existing_count} existing points")

    # 4. Migrate each memory
    migrated = 0
    skipped = 0

    for i, m in enumerate(memories):
        faiss_id = m.get("faiss_id")
        text = m.get("text", "")
        category = m.get("category", "general")
        source = m.get("source", "migration")

        if not text:
            skipped += 1
            continue

        # Get embedding: from FAISS if available, else re-embed
        embedding = None
        if faiss_index is not None and faiss_id is not None:
            try:
                embedding = faiss_index.reconstruct(int(faiss_id))
                if isinstance(embedding, np.ndarray):
                    embedding = embedding.astype(np.float32)
            except Exception:
                pass

        if embedding is None or len(embedding) == 0:
            # Re-embed via Ollama
            try:
                from remme.utils import get_embedding
                embedding = get_embedding(text, task_type="search_document")
            except Exception as e:
                log_error(f"Re-embed failed for memory {m.get('id', i)}: {e}")
                skipped += 1
                continue

        try:
            store.add(
                text=text,
                embedding=embedding,
                category=category,
                source=source,
                metadata={"migrated_from": "faiss", "original_id": m.get("id", "")},
                deduplication_threshold=0,
            )
            migrated += 1
            if (i + 1) % 10 == 0:
                print(f"  Migrated {i + 1}/{len(memories)}...")
        except Exception as e:
            log_error(f"Failed to add memory: {e}")
            skipped += 1

    print(f"\n✓ Migration complete: {migrated} migrated, {skipped} skipped")
    print(f"  Qdrant total: {store.count()} points")
    print("=" * 60)


if __name__ == "__main__":
    migrate()
