# Graph Router - Knowledge graph explorer API for Mnemo (P11 §11.2)
# Provides subgraph data for interactive visualization (entities + relationships).

from fastapi import APIRouter, Query

router = APIRouter(prefix="/graph", tags=["Graph"])


@router.get("/explore")
async def explore_graph(
    space_id: str | None = Query(default=None, description="Filter by space_id; __global__ or omit for all"),
    limit: int = Query(default=150, ge=10, le=500, description="Max nodes to return"),
):
    """
    Return a subgraph for the knowledge graph explorer.
    Entities and relationships from the user's memories, optionally scoped by space.
    Requires NEO4J_ENABLED=true and MNEMO; returns empty graph when disabled.
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
