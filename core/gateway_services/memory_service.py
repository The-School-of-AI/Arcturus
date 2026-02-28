from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from remme.utils import get_embedding
from shared.state import get_remme_store


async def read_memories(category: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    """Read memories using internal-first contract."""
    store = get_remme_store()
    items = store.get_all()
    if category:
        items = [item for item in items if item.get("category") == category]
    items = items[: max(1, limit)]
    return {"status": "success", "count": len(items), "memories": items}


async def write_memory(text: str, source: str = "api_v1", category: str = "general") -> Dict[str, Any]:
    """Write memory using existing Remme behavior."""
    embedding = await asyncio.to_thread(get_embedding, text, "search_document")
    store = get_remme_store()
    memory = await asyncio.to_thread(store.add, text, embedding, category, source)
    return {"status": "success", "memory": memory}


async def search_memories(query: str, limit: int = 5) -> Dict[str, Any]:
    """Semantic memory search using existing Remme store behavior."""
    query_embedding = await asyncio.to_thread(get_embedding, query, "search_query")
    store = get_remme_store()
    matches = await asyncio.to_thread(store.search, query_embedding, query, max(1, limit))
    return {"status": "success", "count": len(matches), "memories": matches}
