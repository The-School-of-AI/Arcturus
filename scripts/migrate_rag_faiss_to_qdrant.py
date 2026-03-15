#!/usr/bin/env python3
"""
Migrate RAG FAISS index to Qdrant arcturus_rag_chunks collection.

Reads chunks from mcp_servers/faiss_index (metadata.json + index.bin)
and adds each to the Qdrant arcturus_rag_chunks collection.
Phase A: Populates user_id and space_id for tenant/space scope.
Phase C: QdrantRAGStore.add_chunks() generates sparse vectors (FastEmbed SPLADE) when collection has sparse_vectors config.

Usage:
    # For Qdrant Cloud, ensure .env has:
    #   QDRANT_URL=https://your-cluster.region.cloud.qdrant.io
    #   QDRANT_API_KEY=your-api-key
    #   RAG_VECTOR_STORE_PROVIDER=qdrant
    #   VITE_ENABLE_LOCAL_MIGRATION=true  # allows user_id from memory/remme_index/user_id.json
    uv run python scripts/migrate_rag_faiss_to_qdrant.py

    # With explicit user_id and space_id:
    uv run python scripts/migrate_rag_faiss_to_qdrant.py --user-id YOUR_USER_ID --space-id __global__

    # Or via env:
    export MIGRATION_USER_ID=your-user-id
    export MIGRATION_SPACE_ID=__global__
    uv run python scripts/migrate_rag_faiss_to_qdrant.py
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Add project root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Load .env so QDRANT_URL and QDRANT_API_KEY are available
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

RAG_INDEX_DIR = ROOT / "mcp_servers" / "faiss_index"


def get_embedding(text: str):
    """Get embedding via Ollama (same as RAG server)."""
    import requests
    from config.settings_loader import get_ollama_url, get_model, get_timeout
    url = get_ollama_url("embeddings")
    model = get_model("embedding")
    resp = requests.post(url, json={"model": model, "input": text}, timeout=get_timeout())
    resp.raise_for_status()
    import numpy as np
    data = resp.json()
    emb = data["embeddings"][0] if data.get("embeddings") else data.get("embedding", [])
    return np.array(emb, dtype=np.float32)


def _resolve_user_id(user_id_arg: Optional[str]) -> str:
    """Resolve user_id from arg, env, or memory.user_id (when VITE_ENABLE_LOCAL_MIGRATION=true)."""
    if user_id_arg:
        return user_id_arg
    env_uid = os.environ.get("MIGRATION_USER_ID")
    if env_uid:
        return env_uid.strip()
    try:
        from memory.user_id import get_user_id
        return get_user_id()
    except Exception as e:
        print(
            "\n❌ user_id required for RAG migration (tenant-scoped collection). "
            "Provide via: --user-id ID, or MIGRATION_USER_ID env, "
            "or set VITE_ENABLE_LOCAL_MIGRATION=true to use memory/remme_index/user_id.json"
        )
        print(f"   Error: {e}")
        sys.exit(1)


def migrate(user_id: Optional[str], space_id: Optional[str]):
    """Run the migration."""
    uid = _resolve_user_id(user_id)
    sid = (space_id or os.environ.get("MIGRATION_SPACE_ID") or "__global__").strip()

    print("=" * 60)
    print("RAG FAISS → Qdrant Migration")
    print("=" * 60)
    print(f"  user_id: {uid}")
    print(f"  space_id: {sid}")

    index_path = RAG_INDEX_DIR / "index.bin"
    meta_path = RAG_INDEX_DIR / "metadata.json"

    if not meta_path.exists():
        print("\nNo metadata.json found. Run RAG indexing first.")
        return

    metadata = json.loads(meta_path.read_text())
    if not metadata:
        print("\nNo chunks to migrate.")
        return

    print(f"\n✓ Loaded {len(metadata)} chunks from metadata.json")

    # Load FAISS index for embeddings
    faiss_index = None
    if index_path.exists():
        try:
            import faiss
            faiss_index = faiss.read_index(str(index_path))
            print(f"✓ Loaded FAISS index ({faiss_index.ntotal} vectors)")
        except Exception as e:
            print(f"⚠ FAISS load failed: {e}. Will re-embed via Ollama.")

    # Initialize Qdrant RAG store
    from memory.rag_store import get_rag_vector_store
    store = get_rag_vector_store(provider="qdrant")
    print(f"✓ Qdrant RAG store initialized {store}")
    print("=" * 60)

    migrated = 0
    skipped = 0
    batch_size = 32
    entries_batch = []
    embeddings_batch = []

    for i, m in enumerate(metadata):
        chunk_id = m.get("chunk_id", f"idx_{i}")
        chunk_text = m.get("chunk", "")
        doc = m.get("doc", "")
        page = m.get("page", 1)

        if not chunk_text:
            skipped += 1
            continue

        # Get embedding
        embedding = None
        if faiss_index is not None and i < faiss_index.ntotal:
            try:
                import numpy as np
                embedding = faiss_index.reconstruct(i)
                if isinstance(embedding, np.ndarray):
                    embedding = embedding.astype(np.float32)
            except Exception:
                pass

        if embedding is None:
            try:
                embedding = get_embedding(chunk_text)
            except Exception as e:
                print(f"  Re-embed failed for {chunk_id}: {e}")
                skipped += 1
                continue

        entries_batch.append({
            "chunk_id": chunk_id,
            "doc": doc,
            "chunk": chunk_text,
            "page": page,
        })
        embeddings_batch.append(embedding)

        if len(entries_batch) >= batch_size:
            try:
                store.add_chunks(
                    entries=entries_batch,
                    embeddings=embeddings_batch,
                    user_id=uid,
                    space_id=sid,
                )
                migrated += len(entries_batch)
                print(f"  Migrated {migrated}/{len(metadata)}...")
            except Exception as e:
                print(f"  Batch add failed: {e}")
                skipped += len(entries_batch)
            entries_batch = []
            embeddings_batch = []

    if entries_batch:
        try:
            store.add_chunks(
                entries=entries_batch,
                embeddings=embeddings_batch,
                user_id=uid,
                space_id=sid,
            )
            migrated += len(entries_batch)
        except Exception as e:
            print(f"  Final batch failed: {e}")
            skipped += len(entries_batch)

    print(f"\n✓ Migration complete: {migrated} migrated, {skipped} skipped")
    print("  metadata.json unchanged (used for BM25)")
    print("  Set RAG_VECTOR_STORE_PROVIDER=qdrant to use Qdrant for search")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate RAG FAISS index to Qdrant arcturus_rag_chunks (Phase A: user_id + space_id)"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="User ID for tenant scope. Else MIGRATION_USER_ID env or memory.user_id when VITE_ENABLE_LOCAL_MIGRATION=true",
    )
    parser.add_argument(
        "--space-id",
        type=str,
        default=None,
        help="Space ID for scope (default: __global__). Else MIGRATION_SPACE_ID env.",
    )
    args = parser.parse_args()
    migrate(user_id=args.user_id, space_id=args.space_id)
