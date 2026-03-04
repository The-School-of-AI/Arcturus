#!/usr/bin/env python3
"""
Backfill existing Qdrant memories into Neo4j knowledge graph.

Reads all memories from arcturus_memories, extracts entities via LLM,
writes to Neo4j, and updates Qdrant payload with entity_ids.

Prerequisites:
    - NEO4J_ENABLED=true
    - NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    - VECTOR_STORE_PROVIDER=qdrant (memories must be in Qdrant)
    - Ollama running (for entity extraction)

Usage:
    uv run python scripts/migrate_memories_to_neo4j.py
    uv run python scripts/migrate_memories_to_neo4j.py --dry-run  # Skip Neo4j writes
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from memory.vector_store import get_vector_store
from memory.knowledge_graph import get_knowledge_graph
from memory.entity_extractor import EntityExtractor
from core.utils import log_step, log_error


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Qdrant memories to Neo4j")
    parser.add_argument("--dry-run", action="store_true", help="Extract only, skip Neo4j and Qdrant updates")
    parser.add_argument("--limit", type=int, default=0, help="Max memories to process (0 = all)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print raw LLM response for first memory (debug)")
    args = parser.parse_args()

    # Ensure we use Qdrant
    import os
    os.environ.setdefault("VECTOR_STORE_PROVIDER", "qdrant")

    store = get_vector_store(provider="qdrant")
    kg = get_knowledge_graph()
    if not kg or not kg.enabled:
        log_error("Neo4j not enabled. Set NEO4J_ENABLED=true and NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD")
        return 1

    memories = store.get_all()
    if not memories:
        print("No memories in Qdrant.")
        return 0

    to_process = []
    for m in memories:
        if args.limit and len(to_process) >= args.limit:
            break
        entity_ids = m.get("entity_ids") or []
        if not entity_ids:
            to_process.append(m)

    print(f"Found {len(memories)} memories, {len(to_process)} need Neo4j backfill")
    if not to_process:
        return 0

    extractor = EntityExtractor()
    ok = 0
    err = 0
    for i, m in enumerate(to_process):
        memory_id = m.get("id")
        text = m.get("text", "")
        user_id = m.get("user_id", "")
        session_id = m.get("session_id") or m.get("source", "unknown")
        if isinstance(session_id, str) and session_id.startswith("run_"):
            session_id = session_id.replace("run_", "")
        category = m.get("category", "general")
        source = m.get("source", "manual")

        if not text:
            continue
        try:
            extracted = extractor.extract(text, verbose=args.verbose and i == 0)
            if args.verbose and i == 0:
                import json
                print(f"[VERBOSE] Model: {extractor.model}")
                print(f"[VERBOSE] Memory text (first 200 chars): {text[:200]}...")
                print(f"[VERBOSE] Extracted: {json.dumps(extracted, indent=2)[:600]}...")
            if args.dry_run:
                n_ent = len(extracted.get("entities", []))
                print(f"  [{i+1}/{len(to_process)}] {memory_id[:8]}... -> {n_ent} entities (dry-run)")
                ok += 1
                continue

            result = kg.ingest_memory(
                memory_id=memory_id,
                text=text,
                user_id=user_id,
                session_id=session_id,
                category=category,
                source=source,
                entities=extracted.get("entities"),
                entity_relationships=extracted.get("entity_relationships"),
                user_facts=extracted.get("user_facts"),
            )
            entity_ids = result.get("entity_ids", result if isinstance(result, list) else [])
            entity_labels = result.get("entity_labels", []) if isinstance(result, dict) else []
            if entity_ids or entity_labels:
                meta = {"entity_ids": entity_ids}
                if entity_labels:
                    meta["entity_labels"] = entity_labels
                store.update(memory_id, metadata=meta)
            print(f"  [{i+1}/{len(to_process)}] {memory_id[:8]}... -> {len(entity_ids)} entities")
            ok += 1
        except Exception as e:
            log_error(f"Failed {memory_id[:8]}: {e}")
            err += 1

    log_step(f"Done: {ok} ok, {err} errors", symbol="✅")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
