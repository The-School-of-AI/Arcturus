#!/usr/bin/env python3
"""
Phase D 3.3: Real-time indexing verification.

Validates that memory is available for search within the performance commitment (~100 ms).
- Times add() with skip_kg_ingest=True (vector path only) → "time to searchable"
- Optionally times full add() (with KG ingest) for breakdown
- Verifies the added memory is returned in search immediately after add

Usage:
    # From repo root; requires .env (QDRANT_URL, etc.) and Qdrant + optional Neo4j
    uv run python scripts/benchmark_realtime_indexing.py

    # Allow local user_id fallback (no request context)
    VITE_ENABLE_LOCAL_MIGRATION=true uv run python scripts/benchmark_realtime_indexing.py
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env before importing app code
def _load_dotenv():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

_load_dotenv()

# Allow get_user_id() to use file fallback when running without request context
os.environ.setdefault("VITE_ENABLE_LOCAL_MIGRATION", "true")

import numpy as np

from memory.vector_store import get_vector_store
from remme.utils import get_embedding


TARGET_TIME_TO_SEARCHABLE_MS = 100.0
TEST_TEXT = "Benchmark realtime indexing phase D verification at " + str(time.time())


def main() -> int:
    print("Phase D 3.3 — Real-time indexing verification")
    print("Target: memory available for vector search within ~100 ms\n")

    store = get_vector_store(provider="qdrant")
    print(f"Store: {store.url} / {getattr(store, 'collection_name', 'default')}\n")

    # Embedding (excluded from "time to searchable" — we measure index path only)
    print("Getting embedding for test text...")
    t_emb = time.perf_counter()
    embedding = np.array(get_embedding(TEST_TEXT, task_type="search_document"), dtype=np.float32)
    emb_ms = (time.perf_counter() - t_emb) * 1000
    print(f"  Embedding: {emb_ms:.1f} ms\n")

    # 1) Add with KG skipped → measures time until searchable (upsert + sparse + payload build)
    print("1) Add (skip_kg_ingest=True) — time to searchable")
    t0 = time.perf_counter()
    out = store.add(
        text=TEST_TEXT,
        embedding=embedding,
        category="general",
        source="benchmark",
        skip_kg_ingest=True,
    )
    time_to_searchable_ms = (time.perf_counter() - t0) * 1000
    memory_id = out["id"]
    print(f"   Memory id: {memory_id[:12]}...")
    print(f"   Time to searchable: {time_to_searchable_ms:.1f} ms")
    passed = time_to_searchable_ms <= TARGET_TIME_TO_SEARCHABLE_MS
    print(f"   Target ≤ {TARGET_TIME_TO_SEARCHABLE_MS} ms: {'PASS' if passed else 'FAIL'}\n")

    # 2) Verify search returns the new memory immediately
    print("2) Search verification (query = same text)")
    query_emb = np.array(get_embedding(TEST_TEXT, task_type="search_query"), dtype=np.float32)
    t_search = time.perf_counter()
    results = store.search(
        query_vector=query_emb,
        query_text=TEST_TEXT,
        k=5,
    )
    search_ms = (time.perf_counter() - t_search) * 1000
    found = any(r.get("id") == memory_id for r in results)
    print(f"   Search latency: {search_ms:.1f} ms")
    print(f"   Memory found in top-5: {'yes' if found else 'no'}")
    if not found and results:
        print(f"   Top result id: {results[0].get('id', '')[:12]}...")
    print()

    # 3) Optional: full add with KG ingest (for breakdown; use a different text to avoid dedup)
    test_text_kg = "Benchmark KG ingest phase D " + str(time.time())
    emb_kg = np.array(get_embedding(test_text_kg, task_type="search_document"), dtype=np.float32)
    print("3) Add (with KG ingest) — full path")
    t_kg = time.perf_counter()
    store.add(
        text=test_text_kg,
        embedding=emb_kg,
        category="general",
        source="benchmark",
        skip_kg_ingest=False,
    )
    total_add_with_kg_ms = (time.perf_counter() - t_kg) * 1000
    print(f"   Total add+KG: {total_add_with_kg_ms:.1f} ms\n")

    # Summary
    print("Summary")
    print("-------")
    print(f"  Time to searchable (add without KG): {time_to_searchable_ms:.1f} ms (target ≤ {TARGET_TIME_TO_SEARCHABLE_MS} ms)")
    print(f"  Search verification: {'PASS' if found else 'FAIL'}")
    print(f"  Full add + KG:       {total_add_with_kg_ms:.1f} ms")
    overall = passed and found
    print(f"\n  Overall: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
