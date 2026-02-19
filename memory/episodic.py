"""
Episodic Memory Module
Stores and retrieves session skeletons (lightweight execution recipes).
"""
import json
from pathlib import Path
from typing import List, Dict, Any
import re

# Directory where skeleton files are stored
MEMORY_DIR = Path(__file__).parent / "episodic"
MEMORY_DIR.mkdir(exist_ok=True)


def _load_skeleton(file_path: Path) -> Dict[str, Any]:
    """Load a skeleton JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _calculate_relevance_score(skeleton: Dict[str, Any], query: str) -> float:
    """
    Calculate a simple relevance score based on keyword matching.
    Higher score = more relevant.
    """
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    
    if not query_words:
        return 0.0
    
    score = 0.0
    
    # Check original_query (highest weight)
    original_query = skeleton.get("original_query", "").lower()
    if original_query:
        original_words = set(re.findall(r'\w+', original_query))
        matches = len(query_words & original_words)
        score += matches * 3.0
    
    # Check task_goal in nodes
    nodes = skeleton.get("nodes", [])
    for node in nodes:
        task_goal = node.get("task_goal", "").lower()
        if task_goal:
            task_words = set(re.findall(r'\w+', task_goal))
            matches = len(query_words & task_words)
            score += matches * 2.0
        
        # Check instruction/prompt
        instruction = node.get("instruction", "").lower()
        if instruction:
            inst_words = set(re.findall(r'\w+', instruction))
            matches = len(query_words & inst_words)
            score += matches * 1.0
    
    # Normalize by query length
    if len(query_words) > 0:
        score = score / len(query_words)
    
    return score


def search_episodes(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search for relevant past episodes based on query.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return
        
    Returns:
        List of skeleton dictionaries, sorted by relevance (highest first)
    """
    if not MEMORY_DIR.exists():
        return []
    
    # Find all skeleton files
    skeleton_files = list(MEMORY_DIR.glob("skeleton_*.json"))
    
    if not skeleton_files:
        return []
    
    # Load and score each skeleton
    scored_episodes = []
    for file_path in skeleton_files:
        skeleton = _load_skeleton(file_path)
        if not skeleton:
            continue
        
        score = _calculate_relevance_score(skeleton, query)
        if score > 0:
            scored_episodes.append((score, skeleton))
    
    # Sort by score (descending) and return top results
    scored_episodes.sort(key=lambda x: x[0], reverse=True)
    
    return [episode for _, episode in scored_episodes[:limit]]


def get_recent_episodes(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the most recently modified episodes.
    
    Args:
        limit: Maximum number of results to return
        
    Returns:
        List of skeleton dictionaries, sorted by modification time (newest first)
    """
    if not MEMORY_DIR.exists():
        return []
    
    # Find all skeleton files and sort by modification time
    skeleton_files = sorted(
        MEMORY_DIR.glob("skeleton_*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    
    episodes = []
    for file_path in skeleton_files[:limit]:
        skeleton = _load_skeleton(file_path)
        if skeleton:
            episodes.append(skeleton)
    
    return episodes

