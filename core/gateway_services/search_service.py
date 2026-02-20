from __future__ import annotations

import asyncio
from typing import Any, Dict

try:
    from mcp_servers.tools.switch_search_method import smart_search
    from mcp_servers.tools.web_tools_async import smart_web_extract
except ImportError:
    # Fallback path resolution for environments that execute from nested modules.
    import sys

    sys.path.append(".")
    from mcp_servers.tools.switch_search_method import smart_search
    from mcp_servers.tools.web_tools_async import smart_web_extract


async def web_search(query: str, limit: int = 5) -> Dict[str, Any]:
    """Internal-first web search contract used by agent router and gateway adapters."""
    urls = await smart_search(query, limit)
    if not urls:
        return {"status": "success", "results": [], "message": "No results found"}

    results = []
    max_extracts = min(len(urls), limit)
    for index, url in enumerate(urls[:max_extracts]):
        try:
            web_result = await asyncio.wait_for(smart_web_extract(url), timeout=20)
            text_content = web_result.get("best_text", "")[:4000]
            text_content = " ".join(text_content.split()).strip()
            results.append(
                {
                    "url": url,
                    "title": web_result.get("title", ""),
                    "content": text_content if text_content else "[No readable content]",
                    "rank": index + 1,
                }
            )
        except Exception as exc:  # noqa: BLE001 - best-effort fetch
            results.append(
                {
                    "url": url,
                    "title": "",
                    "content": f"[Error visiting: {exc}]",
                    "rank": index + 1,
                }
            )

    return {
        "status": "success",
        "results": results,
        "summary": f"Found and read {len(results)} pages for '{query}'",
    }


async def read_url(url: str, timeout_seconds: int = 45) -> Dict[str, Any]:
    """Internal-first single URL reader contract used by agent router."""
    result = await asyncio.wait_for(smart_web_extract(url), timeout=timeout_seconds)
    text = result.get("best_text", "")[:15000]
    return {
        "status": "success",
        "url": url,
        "title": result.get("title", ""),
        "content": text if text else "[No text extracted]",
    }
