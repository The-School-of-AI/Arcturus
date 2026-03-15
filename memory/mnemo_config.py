"""
P11 Mnemo feature flag: unified extraction + Neo4j Fact/Evidence path.

When MNEMO_ENABLED=true: use unified extractor, ingest to Neo4j (entities + Fact + Evidence),
adapter for GET /preferences (step 4). When false: legacy RemMe extractor, normalizer, JSON hubs.

Backward compatibility: NEO4J_ENABLED still gates Neo4j connectivity and entity ingestion.
MNEMO_ENABLED gates the full Mnemo path (unified extraction + Fact/Evidence). Both can be
read during transition; see .env.example.
"""

import os


def is_mnemo_enabled() -> bool:
    """True when unified extractor and Neo4j Fact/Evidence path should be used."""
    return os.environ.get("MNEMO_ENABLED", "").lower() in ("true", "1", "yes")


def is_async_kg_ingest_enabled() -> bool:
    """True when KG ingestion runs in background after Qdrant upsert (faster add latency)."""
    return os.environ.get("ASYNC_KG_INGEST", "false").lower() in ("true", "1", "yes")
