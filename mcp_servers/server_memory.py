
import json
import os
import time
from pathlib import Path
from typing import List, Optional, Dict
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP
mcp = FastMCP("memory")

# Configuration
MEMORY_FILE = Path(__file__).parent.parent / "data" / "user_memory.json"
MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

def _load_memory() -> List[Dict]:
    if not MEMORY_FILE.exists():
        return []
    try:
        return json.loads(MEMORY_FILE.read_text())
    except:
        return []

def _save_memory(memories: List[Dict]):
    MEMORY_FILE.write_text(json.dumps(memories, indent=2))

@mcp.tool()
async def store_memory(content: str, tags: List[str] = []) -> str:
    """
    Store a piece of information in long-term memory.
    Useful for remembering user preferences, important facts, or context.
    """
    memories = _load_memory()
    
    # Check duplicate? Or just append?
    # Simple append for now
    memory_id = f"mem-{int(time.time() * 1000)}"
    entry = {
        "id": memory_id,
        "content": content,
        "tags": tags,
        "timestamp": int(time.time())
    }
    
    memories.append(entry)
    _save_memory(memories)
    
    return f"Stored memory: '{content}' (ID: {memory_id})"

@mcp.tool()
async def recall_memory(query: str, limit: int = 5) -> str:
    """
    Recall information from long-term memory based on keywords.
    """
    memories = _load_memory()
    if not memories:
        return "No memories found."
        
    # Simple keyword search (case-insensitive)
    query_terms = query.lower().split()
    results = []
    
    for mem in memories:
        content = mem["content"].lower()
        score = 0
        for term in query_terms:
            if term in content:
                score += 1
            # Check tags too
            for tag in mem.get("tags", []):
                if term in tag.lower():
                    score += 1
                    
        if score > 0:
            results.append((score, mem))
            
    # Sort by score desc
    results.sort(key=lambda x: x[0], reverse=True)
    
    if not results:
        return f"No memories found matching '{query}'."
        
    top_results = results[:limit]
    output = []
    for score, mem in top_results:
        output.append(f"- {mem['content']} (Tags: {', '.join(mem['tags'])})")
        
    return "\n".join(output)

@mcp.tool()
async def forget_memory(memory_id: str) -> str:
    """Delete a specific memory by ID."""
    memories = _load_memory()
    initial_len = len(memories)
    memories = [m for m in memories if m["id"] != memory_id]
    
    if len(memories) < initial_len:
        _save_memory(memories)
        return f"Deleted memory {memory_id}"
    return f"Memory {memory_id} not found"

if __name__ == "__main__":
    mcp.run()
