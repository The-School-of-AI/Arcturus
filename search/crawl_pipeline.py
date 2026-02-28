"""
search/crawl_pipeline.py
Thin orchestration wrapper over existing smart_search + smart_web_extract.
No new dependencies — reuses playwright + httpx tools already in mcp_servers/tools/.
"""
import asyncio
import sys
import os
from dataclasses import dataclass, field
from typing import Optional

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_servers.tools.switch_search_method import smart_search
from mcp_servers.tools.web_tools_async import smart_web_extract


EXTRACT_TIMEOUT = 8   # seconds per URL — matches server_browser.py:98
MAX_CONTENT_CHARS = 8000  # matches server_browser.py:105


@dataclass
class SourceDocument:
    url: str
    title: str
    content: str
    rank: int
    error: Optional[str] = None


async def _extract_single(url: str, rank: int) -> SourceDocument:
    """Extract text from a single URL with timeout.

    Mirrors server_browser.py:100-121 but returns a SourceDocument
    instead of a raw dict wrapped in MCP TextContent.
    """
    try:
        web_result = await asyncio.wait_for(
            smart_web_extract(url), timeout=EXTRACT_TIMEOUT
        )
        text_content = web_result.get("best_text", "")[:MAX_CONTENT_CHARS]
        text_content = text_content.replace("\n", " ").replace("  ", " ").strip()
        if not text_content.strip():
            return SourceDocument(
                url=url, title="", content="", rank=rank,
                error="No readable content found",
            )
        return SourceDocument(
            url=url,
            title=web_result.get("title", ""),
            content=text_content,
            rank=rank,
        )
    except asyncio.TimeoutError:
        return SourceDocument(
            url=url, title="", content="", rank=rank,
            error=f"Timeout after {EXTRACT_TIMEOUT}s",
        )
    except Exception as e:
        return SourceDocument(
            url=url, title="", content="", rank=rank,
            error=str(e),
        )


class CrawlPipeline:
    """Parallel web crawler with content extraction.

    Composes smart_search() for URL discovery and smart_web_extract()
    for content extraction.  Mirrors search_web_with_text_content()
    from server_browser.py but as a direct Python API.
    """

    async def search_and_extract(
        self,
        sub_queries: list[str],
        top_k: int = 10,
        max_sources: int = 60,
    ) -> list[SourceDocument]:
        """Search for each sub-query and extract content from result URLs.

        Args:
            sub_queries: List of search strings to execute.
            top_k: Max URLs to fetch per sub-query.
            max_sources: Hard cap on total sources returned.

        Returns:
            Deduplicated list of SourceDocument sorted by rank.
        """
        seen_urls: set[str] = set()
        all_docs: list[SourceDocument] = []
        global_rank = 0

        for query in sub_queries:
            urls = await smart_search(query, limit=top_k)
            if not urls:
                continue

            # Deduplicate across sub-queries
            new_urls = []
            for u in urls:
                if u not in seen_urls:
                    seen_urls.add(u)
                    new_urls.append(u)

            if not new_urls:
                continue

            # Extract all URLs concurrently (same pattern as server_browser.py:143)
            tasks = [
                _extract_single(url, global_rank + i + 1)
                for i, url in enumerate(new_urls)
            ]
            results = await asyncio.gather(*tasks)
            global_rank += len(new_urls)

            all_docs.extend(results)

            if len(all_docs) >= max_sources:
                break

        # Filter out errored docs, keep them at the end for transparency
        good = [d for d in all_docs if d.error is None]
        bad = [d for d in all_docs if d.error is not None]
        return (good + bad)[:max_sources]

    async def extract_urls(self, urls: list[str]) -> list[SourceDocument]:
        """Extract content from an explicit list of URLs in parallel."""
        tasks = [_extract_single(url, i + 1) for i, url in enumerate(urls)]
        results = await asyncio.gather(*tasks)
        return sorted(results, key=lambda d: d.rank)
