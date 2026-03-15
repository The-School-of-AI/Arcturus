from fastapi import APIRouter
from pydantic import BaseModel
from core.query_optimizer import QueryOptimizer
import json

router = APIRouter(prefix="/optimizer", tags=["optimizer"])

class OptimizeRequest(BaseModel):
    query: str


def _get_user_id():
    """Current user for episodic scope. None if unavailable."""
    try:
        from memory.user_id import get_user_id
        return get_user_id()
    except Exception:
        return None


@router.post("/preview")
async def preview_optimization(req: OptimizeRequest):
    """
    Generate an optimized version of the query for preview.
    """
    opt = QueryOptimizer()
    return await opt.optimize_query(req.query)


@router.get("/skeletons")
async def get_skeletons(limit: int = 10):
    """
    Retrieve recent session skeletons (recipes).
    Uses EPISODIC_STORE_PROVIDER: qdrant → Qdrant; legacy → memory/episodic_skeletons/skeleton_*.json.
    """
    try:
        from memory.episodic import get_recent_episodes

        user_id = _get_user_id()
        episodes = get_recent_episodes(limit=limit, user_id=user_id, space_id=None)
        skeletons = []
        for ep in episodes:
            sk_json = ep.get("skeleton_json") or "{}"
            try:
                sk = json.loads(sk_json) if isinstance(sk_json, str) else sk_json
            except Exception:
                sk = {}
            sk.setdefault("id", ep.get("id") or ep.get("session_id"))
            skeletons.append(sk)
        return skeletons
    except Exception:
        return []
