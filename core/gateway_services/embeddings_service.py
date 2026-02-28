from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from config.settings_loader import get_model
from remme.utils import get_embedding


async def create_embeddings(inputs: List[str], model: Optional[str] = None) -> Dict[str, Any]:
    """Create embeddings using existing embedding utility and return current v1-style payload."""
    vectors = await asyncio.gather(
        *[asyncio.to_thread(get_embedding, text, "search_document") for text in inputs]
    )

    data = [
        {
            "object": "embedding",
            "index": index,
            "embedding": vector.tolist(),
        }
        for index, vector in enumerate(vectors)
    ]

    token_estimates = [max(1, len(text.split())) for text in inputs]
    prompt_tokens = sum(token_estimates)

    return {
        "object": "list",
        "model": model or get_model("embedding"),
        "data": data,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "total_tokens": prompt_tokens,
        },
    }
