# Graph Router - Knowledge graph explorer API for Mnemo (P11 §11.2)
# Provides subgraph data for interactive visualization (entities + relationships).

import json
from pathlib import Path

from fastapi import APIRouter, Query

router = APIRouter(prefix="/graph", tags=["Graph"])

_MEMORIES_JSON = Path(__file__).parent.parent / "memory" / "remme_index" / "memories.json"


@router.get("/explore")
async def explore_graph(
    space_id: str | None = Query(default=None, description="Filter by space_id; __global__ or omit for all"),
    limit: int = Query(default=150, ge=10, le=500, description="Max nodes to return"),
):
    """
    Return a subgraph for the knowledge graph explorer.
    Entities and relationships from the user's memories, optionally scoped by space.
    Uses Neo4j when available, falls back to NetworkX (local JSON persistence).
    Returns empty graph when NEO4J_ENABLED is false.
    """
    from memory.knowledge_graph import get_knowledge_graph
    from memory.user_id import get_user_id

    user_id = get_user_id()
    if not user_id:
        return {"nodes": [], "edges": []}

    kg = get_knowledge_graph()
    if not kg or not kg.enabled:
        return {"nodes": [], "edges": []}

    data = kg.get_subgraph_for_explore(
        user_id=user_id,
        space_id=space_id,
        limit=limit,
    )
    return {"nodes": data["nodes"], "edges": data["edges"]}


@router.post("/migrate")
async def migrate_faiss_to_graph():
    """
    Backfill existing FAISS RemMe memories into the knowledge graph.
    Reads memory/remme_index/memories.json, extracts entities via LLM,
    and ingests into the active KG backend (Neo4j or NetworkX).
    """
    from memory.knowledge_graph import get_knowledge_graph
    from memory.user_id import get_user_id
    from core.utils import log_step, log_error

    user_id = get_user_id()
    if not user_id:
        return {"status": "error", "message": "No user_id in request context"}

    kg = get_knowledge_graph()
    if not kg or not kg.enabled:
        return {"status": "error", "message": "Knowledge graph not available"}

    if not _MEMORIES_JSON.exists():
        return {"status": "error", "message": "No FAISS memories.json found"}

    try:
        memories = json.loads(_MEMORIES_JSON.read_text())
    except Exception as e:
        return {"status": "error", "message": f"Failed to read memories.json: {e}"}

    if not memories:
        return {"status": "ok", "migrated": 0, "skipped": 0, "errors": 0}

    # Check which memories are already ingested (have a Memory node in the graph)
    already_ingested = set()
    if hasattr(kg, '_graph'):
        # NetworkX backend — check for existing memory nodes
        for nid, nd in kg._graph.nodes(data=True):
            if nd.get("kind") == "Memory":
                already_ingested.add(nid)

    try:
        from memory.entity_extractor import EntityExtractor
        extractor = EntityExtractor()
    except Exception as e:
        return {"status": "error", "message": f"EntityExtractor unavailable: {e}"}

    migrated = 0
    skipped = 0
    errors = 0

    for mem in memories:
        memory_id = mem.get("id", "")
        text = mem.get("text", "")
        if not text or not memory_id:
            skipped += 1
            continue
        if memory_id in already_ingested:
            skipped += 1
            continue

        try:
            extracted = extractor.extract(text)
            kg.ingest_memory(
                memory_id=memory_id,
                text=text,
                user_id=user_id,
                session_id=mem.get("source", "migration"),
                category=mem.get("category", "general"),
                source=mem.get("source", "migration"),
                entities=extracted.get("entities"),
                entity_relationships=extracted.get("entity_relationships"),
                user_facts=extracted.get("user_facts"),
            )
            migrated += 1
            log_step("GraphMigrate", f"Ingested {memory_id[:8]}... ({migrated})")
        except Exception as e:
            log_error("GraphMigrate", f"Failed {memory_id[:8]}: {e}")
            errors += 1

    return {
        "status": "ok",
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
        "total": len(memories),
    }
