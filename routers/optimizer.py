from fastapi import APIRouter
from pydantic import BaseModel
from core.query_optimizer import QueryOptimizer
from core.episodic_memory import MEMORY_DIR
import json
import asyncio

router = APIRouter(prefix="/optimizer", tags=["optimizer"])

class OptimizeRequest(BaseModel):
    query: str

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
    """
    if not MEMORY_DIR.exists():
        return []
        
    # List and sort by time
    files = sorted(MEMORY_DIR.glob("skeleton_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    
    skeletons = []
    for f in files[:limit]:
        try:
            # Run file reading in thread to avoid blocking loop
            content = await asyncio.to_thread(f.read_text)
            data = json.loads(content)
            skeletons.append(data)
        except Exception as e:
            print(f"Failed to load skeleton {f.name}: {e}")
            pass
            
    return skeletons
