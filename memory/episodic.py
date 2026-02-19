import os
import json
import sys
from pathlib import Path
from typing import List, Dict

# Standard pathing for Arcturus
PROJECT_ROOT = Path(__file__).parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory" / "episodes"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

def get_recent_episodes(limit: int = 5) -> List[Dict]:
    """Retrieve the most recent session skeletons."""
    if not MEMORY_DIR.exists():
        return []
    files = sorted(MEMORY_DIR.glob("skeleton_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    episodes = []
    for f in files[:limit]:
        try:
            episodes.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return episodes

def search_episodes(query: str, limit: int = 3) -> List[Dict]:
    """
    Search past session skeletons for similar queries or tasks.
    In a full implementation, this could use vector search.
    """
    if not MEMORY_DIR.exists():
        return []
    
    files = list(MEMORY_DIR.glob("skeleton_*.json"))
    results = []
    query_terms = query.lower().split()
    
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            # Score based on keyword matches in query and node descriptions
            content = f"{data.get('original_query', '')} {data.get('id', '')}"
            for node in data.get("nodes", []):
                content += f" {node.get('agent', '')} {node.get('task_goal', '')}"
            
            content = content.lower()
            score = sum(1 for term in query_terms if term in content)
            
            if score > 0:
                results.append((score, data))
        except Exception:
            pass
            
    # Sort by score descending
    results.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in results[:limit]]
