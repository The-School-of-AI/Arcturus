#!/usr/bin/env python3
"""
Migrate RAG FAISS index to Qdrant arcturus_rag_chunks collection.

Reads chunks from mcp_servers/faiss_index (metadata.json + index.bin)
and adds each to the Qdrant arcturus_rag_chunks collection.
Keeps metadata.json for BM25 (unchanged).

Usage:
    # For Qdrant Cloud, ensure .env has:
    #   QDRANT_URL=https://your-cluster.region.cloud.qdrant.io
    #   QDRANT_API_KEY=your-api-key
    #   RAG_VECTOR_STORE_PROVIDER=qdrant
    uv run python scripts/migrate_rag_faiss_to_qdrant.py

    # Or export before running:
    export QDRANT_URL=https://your-cluster.region.cloud.qdrant.io
    export QDRANT_API_KEY=your-api-key
    export RAG_VECTOR_STORE_PROVIDER=qdrant
    uv run python scripts/migrate_rag_faiss_to_qdrant.py
"""

import json
import sys
from pathlib import Path

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


def migrate():
    """Run the migration."""
    print("=" * 60)
    print("RAG FAISS → Qdrant Migration")
    print("=" * 60)

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
                store.add_chunks(entries=entries_batch, embeddings=embeddings_batch)
                migrated += len(entries_batch)
                print(f"  Migrated {migrated}/{len(metadata)}...")
            except Exception as e:
                print(f"  Batch add failed: {e}")
                skipped += len(entries_batch)
            entries_batch = []
            embeddings_batch = []

    if entries_batch:
        try:
            store.add_chunks(entries=entries_batch, embeddings=embeddings_batch)
            migrated += len(entries_batch)
        except Exception as e:
            print(f"  Final batch failed: {e}")
            skipped += len(entries_batch)

    print(f"\n✓ Migration complete: {migrated} migrated, {skipped} skipped")
    print("  metadata.json unchanged (used for BM25)")
    print("  Set RAG_VECTOR_STORE_PROVIDER=qdrant to use Qdrant for search")
    print("=" * 60)


if __name__ == "__main__":
    migrate()
