#!/usr/bin/env python3
"""
P11 Mnemo: Retrieval P95 latency benchmark.

Validates that top-k memory retrieval meets the P95 < 250 ms target.
- Runs N retrieval calls (embed + vector search)
- Computes P50, P95, P99 latencies
- Reports pass/fail vs target

Usage:
    # From repo root; requires .env (QDRANT_URL, etc.) and Qdrant
    uv run python scripts/benchmark_retrieval.py

    # With local user_id fallback (no request context)
    VITE_ENABLE_LOCAL_MIGRATION=true uv run python scripts/benchmark_retrieval.py

    # Custom iterations
    BENCHMARK_ITERATIONS=100 uv run python scripts/benchmark_retrieval.py
"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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

TARGET_P95_MS = 250.0
DEFAULT_ITERATIONS = 50

# Varied queries to exercise retrieval (embed + search)
SAMPLE_QUERIES = [
    "What did I work on recently?",
    "User preferences and settings",
    "Memories about meetings",
    "Important decisions",
    "Project context and goals",
    "Personal information",
    "Recent conversations",
    "Tasks and todos",
]


def _percentile(arr: list[float], p: float) -> float:
    """Compute percentile (e.g. 95 for P95)."""
    if not arr:
        return 0.0
    return float(np.percentile(arr, p))


def main() -> int:
    iterations = int(os.environ.get("BENCHMARK_ITERATIONS", str(DEFAULT_ITERATIONS)))
    print("P11 Mnemo — Retrieval P95 Latency Benchmark")
    print(f"Target: P95 < {TARGET_P95_MS} ms (top-k retrieval: embed + vector search)\n")

    store = get_vector_store(provider="qdrant")
    print(f"Store: {store.url} / {getattr(store, 'collection_name', 'default')}")
    print(f"Iterations: {iterations}\n")

    latencies_ms: list[float] = []
    repeat = max(1, iterations // len(SAMPLE_QUERIES) + 1)
    queries = (SAMPLE_QUERIES * repeat)[:iterations]

    for i, query in enumerate(queries):
        # Time full retrieval path (embed + search) — same as memory_retriever._semantic_recall
        t0 = time.perf_counter()
        emb = np.array(get_embedding(query, task_type="search_query"), dtype=np.float32)
        _ = store.search(
            query_vector=emb,
            query_text=query,
            k=10,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies_ms.append(elapsed_ms)
        if (i + 1) % 10 == 0:
            print(f"  Completed {i + 1}/{iterations}...")

    p50 = _percentile(latencies_ms, 50)
    p95 = _percentile(latencies_ms, 95)
    p99 = _percentile(latencies_ms, 99)
    mean_ms = float(np.mean(latencies_ms))
    min_ms = min(latencies_ms)
    max_ms = max(latencies_ms)

    print()
    print("Results")
    print("-------")
    print(f"  P50:  {p50:.1f} ms")
    print(f"  P95:  {p95:.1f} ms  (target < {TARGET_P95_MS} ms)")
    print(f"  P99:  {p99:.1f} ms")
    print(f"  Mean: {mean_ms:.1f} ms")
    print(f"  Min:  {min_ms:.1f} ms | Max: {max_ms:.1f} ms")

    passed = p95 < TARGET_P95_MS
    print(f"\n  P95 target: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
