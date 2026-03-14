import os
import json
from typing import List
from mcp.server.fastmcp import FastMCP
import numpy as np

# Initialize FastMCP
mcp = FastMCP("memory")

def _get_store():
    from memory.vector_store import get_vector_store
    return get_vector_store(provider="qdrant")

def _get_embedding(text: str) -> np.ndarray:
    try:
        from remme.utils import get_embedding
        return get_embedding(text, task_type="document")
    except Exception:
        # Fallback dummy embedding if running standalone
        return np.zeros(768)

@mcp.tool()
async def store_memory(content: str, tags: List[str] = []) -> str:
    """
    Store a piece of information in long-term memory.
    Useful for remembering user preferences, important facts, or context.
    """
    try:
        store = _get_store()
        res = store.add(
            text=content,
            embedding=_get_embedding(content),
            metadata={"tags": tags}
        )
        return f"Stored memory: '{content}' (ID: {res['id']})"
    except Exception as e:
        return f"Failed to store memory: {e}"

@mcp.tool()
async def recall_memory(query: str, limit: int = 5) -> str:
    """
    Recall information from long-term memory based on keywords.
    """
    try:
        store = _get_store()
        results = store.search(
            query_vector=_get_embedding(query),
            query_text=query,
            k=limit
        )
        if not results:
            return f"No memories found matching '{query}'."
            
        output = []
        for res in results:
            tags = res.get("tags", [])
            tag_str = f" (Tags: {', '.join(tags)})" if tags else ""
            output.append(f"- {res.get('text', '')}{tag_str}")
            
        return "\n".join(output)
    except Exception as e:
        return f"Failed to recall memory: {e}"

@mcp.tool()
async def forget_memory(memory_id: str) -> str:
    """Delete a specific memory by ID."""
    try:
        store = _get_store()
        if store.delete(memory_id):
            return f"Deleted memory {memory_id}"
        return f"Memory {memory_id} not found"
    except Exception as e:
        return f"Failed to forget memory: {e}"

if __name__ == "__main__":
    mcp.run()
