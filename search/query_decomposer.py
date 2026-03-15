"""
search/query_decomposer.py
Uses Gemini to break a complex query into 3-8 focused sub-queries.
Also applies focus-mode domain enrichment via focus_modes.apply_focus().
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings_loader import settings
from search.focus_modes import apply_focus


DECOMPOSE_PROMPT = (
    "You are a research assistant. Break the following query into {n_queries} focused sub-queries "
    "that together comprehensively cover all aspects of the topic.\n\n"
    "Rules:\n"
    "- Return ONLY a JSON array of strings (sub-queries), no markdown, no explanation.\n"
    "- Each sub-query should be specific and independently searchable.\n"
    "- Avoid duplicates or overly similar sub-queries.\n"
    "- Sub-queries should complement each other (different angles, time periods, subtopics).\n"
    "- Consider every plausible interpretation and domain the query could refer to.\n"
    "- Include one synthesis query that compares/contrasts across identified domains.\n\n"
    "Query: {query}\n\n"
    "JSON array:"
)


def _get_gemini_client():
    """Create a ModelManager instance using the configured provider."""
    from core.model_manager import ModelManager
    from config.settings_loader import reload_settings
    agent_cfg = reload_settings().get("agent", {})
    provider = agent_cfg.get("model_provider", "gemini")
    model = agent_cfg.get("default_model", "gemini-2.5-flash")
    return ModelManager(model_name=model, provider=provider)


async def decompose(
    query: str,
    focus_mode: str = "web",
    n_queries: int = 6,
) -> list[str]:
    """Decompose *query* into *n_queries* focused sub-queries.

    Steps:
        1. Call Gemini to generate sub-queries as a JSON array.
        2. Apply focus-mode search suffixes via apply_focus().

    Returns:
        List of enriched search strings ready for CrawlPipeline.
    """
    prompt = DECOMPOSE_PROMPT.format(query=query, n_queries=n_queries)

    client = _get_gemini_client()
    raw = await client.generate_text(prompt)

    # Parse — strip markdown fences if the model wraps its output
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    try:
        sub_queries = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: treat each non-empty line as a sub-query
        sub_queries = [line.strip().strip('"').strip("- ") for line in raw.splitlines() if line.strip()]

    # Ensure we have a list of strings
    if not isinstance(sub_queries, list):
        sub_queries = [str(sub_queries)]
    sub_queries = [str(q) for q in sub_queries if q][:n_queries]

    # Apply focus-mode domain enrichment
    return apply_focus(sub_queries, focus_mode)
