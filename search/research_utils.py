"""
search/research_utils.py
Utility functions for deep research data processing.
Extracted from core/loop.py to consolidate research logic in the search module.

Functions:
    fix_citations       - Replace placeholder citation URLs with real source_index URLs
    extract_sub_queries - Parse decomposed sub-queries from ThinkerAgent output
    extract_followup_queries   - Parse follow-up queries from gap analysis output
    extract_contradiction_queries - Parse contradiction verification queries
    build_source_index  - Build deduplicated source index from retriever outputs
    preprocess_sources  - Organize retriever outputs by dimension with excerpts
"""
import json
import re


def fix_citations(text: str, source_index: dict) -> str:
    """Replace placeholder/fake citation URLs with real URLs from source_index.

    Handles these patterns:
      [[N]](any-url)           -> [[N] Title](real-url)
      [[N]]                    -> [[N] Title](real-url)
      [[N] any-title](any-url) -> [[N] Title](real-url)
      [N]                      -> [[N] Title](real-url) (bare numeric refs)

    Args:
        text: Markdown text containing citation references.
        source_index: Mapping of {"1": {"url": "...", "title": "..."}, ...}

    Returns:
        Text with citations replaced with real URLs.
    """
    if not text or not source_index:
        return text

    def replace_with_url(match):
        n = match.group(1)
        src = source_index.get(n) or source_index.get(str(n))
        if src and src.get("url"):
            title = src.get("title", f"Source {n}")
            return f"[[{n}] {title}]({src['url']})"
        return match.group(0)

    # Replace [[N]](any-url) with real URL
    text = re.sub(r'\[\[(\d+)\]\]\([^)]*\)', replace_with_url, text)
    # Replace [[N]] without URL
    text = re.sub(r'\[\[(\d+)\]\](?!\()', replace_with_url, text)
    # Replace [[N] any-title](any-url) with real URL
    text = re.sub(r'\[\[(\d+)\][^\]]*\]\([^)]*\)', replace_with_url, text)
    # Replace bare [N] (single bracket, not already [[N]])
    text = re.sub(r'(?<!\[)\[(\d{1,2})\](?!\(|\[|\])', replace_with_url, text)
    return text


def extract_sub_queries(decomposed_raw) -> list:
    """Robustly extract sub-queries from ThinkerAgent T001 output.

    Handles various formats:
      - JSON string containing a list of {query, dimension} dicts
      - Direct list of dicts or strings
      - Dict with 'decomposed_queries' key (possibly nested under 'output')

    Returns:
        List of {"query": "...", "dimension": "..."} dicts.
    """
    if decomposed_raw is None:
        return []

    # String -> parse
    if isinstance(decomposed_raw, str):
        try:
            decomposed_raw = json.loads(decomposed_raw)
        except (json.JSONDecodeError, TypeError):
            return []

    # List -> validate items
    if isinstance(decomposed_raw, list):
        result = []
        for item in decomposed_raw:
            if isinstance(item, dict) and "query" in item:
                result.append(item)
            elif isinstance(item, str):
                result.append({"query": item, "dimension": "general"})
        return result

    # Dict -> look for 'decomposed_queries' key
    if isinstance(decomposed_raw, dict):
        queries = decomposed_raw.get("decomposed_queries")
        if queries:
            return extract_sub_queries(queries)
        # Nested output
        nested = decomposed_raw.get("output")
        if isinstance(nested, dict):
            queries = nested.get("decomposed_queries")
            if queries:
                return extract_sub_queries(queries)

    return []


def extract_followup_queries(raw) -> list:
    """Extract follow-up queries from gap analysis output.

    Args:
        raw: Raw value from globals_schema (string, list, or dict).

    Returns:
        List of query strings, capped at 3.
    """
    if raw is None:
        return []

    # String -> parse
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []

    # List -> extract query strings directly
    if isinstance(raw, list):
        result = [q if isinstance(q, str) else q.get("query", str(q)) for q in raw]
        return [q for q in result if q.strip()][:3]

    # Dict -> look for followup_queries key (or variants)
    if isinstance(raw, dict):
        for key in ("followup_queries", "follow_up_queries", "deep_queries", "targeted_queries"):
            queries = raw.get(key)
            if queries and isinstance(queries, list):
                result = [q if isinstance(q, str) else q.get("query", str(q)) for q in queries]
                return [q for q in result if q.strip()][:3]

    return []


def extract_contradiction_queries(queries_raw, contradictions_raw=None) -> list:
    """Extract contradiction-specific verification queries.

    First tries the dedicated contradiction_queries value, then falls back to
    generating queries from the contradictions list.

    Args:
        queries_raw: Raw contradiction_queries value from globals_schema.
        contradictions_raw: Raw contradictions list value (fallback).

    Returns:
        List of query strings, capped at 3.
    """
    # Primary: look for explicit contradiction queries
    if queries_raw is not None:
        if isinstance(queries_raw, str):
            try:
                queries_raw = json.loads(queries_raw)
            except (json.JSONDecodeError, TypeError):
                queries_raw = None

        if isinstance(queries_raw, list) and queries_raw:
            result = [q if isinstance(q, str) else q.get("query", str(q)) for q in queries_raw]
            return [q for q in result if q.strip()][:3]

    # Fallback: generate queries from contradictions list
    if contradictions_raw is not None:
        if isinstance(contradictions_raw, str):
            try:
                contradictions_raw = json.loads(contradictions_raw)
            except (json.JSONDecodeError, TypeError):
                contradictions_raw = None

        if isinstance(contradictions_raw, list) and contradictions_raw:
            generated_queries = []
            for c in contradictions_raw[:3]:
                if isinstance(c, str) and len(c) > 20:
                    generated_queries.append(f"verify: {c[:150]}")
                elif isinstance(c, dict):
                    claim = c.get("claim") or c.get("claim_a") or c.get("details") or c.get("claim_1", "")
                    if claim and len(claim) > 20:
                        generated_queries.append(f"verify: {claim[:150]}")
            if generated_queries:
                return generated_queries

    return []


def _unwrap_raw_sources(raw):
    """Unwrap raw retriever output into a list of source dicts/strings.

    Handles:
      - JSON strings
      - MCP TextContent format: {"content": [{"type": "text", "text": "[...]"}]}
      - Dict wrappers with list values
      - Direct lists
    """
    if raw is None:
        return []

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []

    if isinstance(raw, dict):
        # Unwrap MCP TextContent format first
        content_list = raw.get("content")
        if isinstance(content_list, list) and content_list:
            first = content_list[0]
            if isinstance(first, dict) and first.get("type") == "text" and "text" in first:
                try:
                    raw = json.loads(first["text"])
                except (json.JSONDecodeError, TypeError):
                    return []
            else:
                raw = content_list
        else:
            # Look for the first list value inside the dict
            for v in raw.values():
                if isinstance(v, list) and v:
                    raw = v
                    break
            else:
                return []

    return raw if isinstance(raw, list) else []


def build_source_index(globals_schema: dict, write_keys: list) -> dict:
    """Build a deduplicated source index from retriever outputs.

    Args:
        globals_schema: The plan graph globals_schema dict.
        write_keys: List of retriever output keys to process.

    Returns:
        {"1": {"url": "...", "title": "...", "snippet": "..."}, ...}
        Also stores it in globals_schema["source_index"].
    """
    seen_urls = set()
    source_index = {}
    counter = 1

    for key in write_keys:
        raw = globals_schema.get(key)
        sources = _unwrap_raw_sources(raw)

        for src in sources:
            if isinstance(src, str):
                url = src.strip()
                if url and url.startswith("http") and url not in seen_urls:
                    seen_urls.add(url)
                    source_index[str(counter)] = {
                        "url": url,
                        "title": "",
                        "snippet": ""
                    }
                    counter += 1
            elif isinstance(src, dict):
                url = src.get("url", "")
                if not url or url in seen_urls:
                    continue
                content = src.get("content", "")
                if isinstance(content, str) and content.startswith("[error]"):
                    continue
                seen_urls.add(url)
                source_index[str(counter)] = {
                    "url": url,
                    "title": src.get("title", ""),
                    "snippet": content[:200] if isinstance(content, str) else ""
                }
                counter += 1

    globals_schema["source_index"] = source_index
    return source_index


def preprocess_sources(globals_schema: dict, write_keys: list, sub_queries: list, focus_mode: str = "") -> list:
    """Pre-process retriever outputs into organized, deduplicated structure by dimension.

    Args:
        globals_schema: The plan graph globals_schema dict.
        write_keys: List of retriever output keys to process.
        sub_queries: List of sub-query dicts with 'dimension' labels.
        focus_mode: Focus mode string (e.g. "code" for larger excerpts).

    Returns:
        List of dimension dicts. Also stores as globals_schema["processed_sources"].
    """
    source_index = globals_schema.get("source_index", {})

    # Build reverse lookup: url -> source index number
    url_to_index = {}
    for idx, info in source_index.items():
        url_to_index[info.get("url", "")] = idx

    dimensions = []
    for i, key in enumerate(write_keys):
        dim_label = "general"
        if i < len(sub_queries):
            sq = sub_queries[i]
            dim_label = sq.get("dimension", f"dimension_{i+1}") if isinstance(sq, dict) else f"dimension_{i+1}"

        sources = _unwrap_raw_sources(globals_schema.get(key))
        max_chars = 12000 if focus_mode == "code" else 8000

        dim_sources = []
        for src in sources:
            if not isinstance(src, dict):
                continue
            url = src.get("url", "")
            content = src.get("content", "")
            if content.startswith("[error]") or not url:
                continue
            idx = url_to_index.get(url, "?")
            dim_sources.append({
                "index": idx,
                "url": url,
                "title": src.get("title", ""),
                "excerpt": content[:max_chars]
            })

        if dim_sources:
            dimensions.append({
                "dimension": dim_label,
                "sources": dim_sources
            })

    globals_schema["processed_sources"] = dimensions
    return dimensions
