"""
search/synthesizer.py
Multi-source answer fusion with:
- Inline citation tagging [N]
- Per-paragraph confidence scoring (HIGH/MEDIUM/LOW)
- Contradiction detection
- Anti-hallucination guardrails
- Structured report output
"""
import asyncio
import json
import os
import sys
import re
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings_loader import settings


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    index: int
    url: str
    title: str
    timestamp: str = ""
    credibility: str = "MEDIUM"  # HIGH | MEDIUM | LOW


@dataclass
class SynthesisResult:
    answer_md: str
    citations: list[Citation] = field(default_factory=list)
    executive_summary: str = ""
    contradictions: list[str] = field(default_factory=list)
    confidence_per_para: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT = (
    "You are an expert research synthesizer. Given a query and {n_sources} source documents, "
    "produce a comprehensive, cited answer.\n\n"
    "QUERY: {query}\n"
    "FOCUS MODE: {focus_mode}\n"
    "ITERATION: {iteration} of 5\n\n"
    "SOURCE DOCUMENTS:\n{sources_block}\n\n"
    "INSTRUCTIONS:\n"
    "1. Write a comprehensive answer in Markdown.\n"
    "2. After EVERY factual claim, add an inline citation [N] where N is the source index.\n"
    "3. Identify contradictions between sources and surface them explicitly as:\n"
    '   "Source A claims X, while Source B states Y."\n'
    "4. For each paragraph, rate confidence as HIGH (>=3 sources agree), "
    "MEDIUM (1-2 sources), or LOW (single source or inferred).\n"
    "5. Flag any claim you cannot ground in the sources with [unverified].\n"
    "6. End with a structured JSON block (inside ```json ... ```) with this exact schema:\n"
    '{{\n'
    '  "executive_summary": "2-3 sentence summary",\n'
    '  "key_findings": ["finding 1", "finding 2", ...],\n'
    '  "citations": [\n'
    '    {{"index": 1, "url": "...", "title": "...", "timestamp": "...", "credibility": "HIGH|MEDIUM|LOW"}},\n'
    '    ...\n'
    '  ],\n'
    '  "confidence_per_para": ["HIGH", "MEDIUM", ...],\n'
    '  "contradictions": ["Source 1 claims X while Source 3 states Y", ...],\n'
    '  "flagged_unsupported": ["sentence that had no grounding", ...]\n'
    '}}\n\n'
    "Write the Markdown answer first, then the JSON block.\n"
)

GAP_PROMPT = (
    'Given this research answer about: "{query}"\n\n'
    "Answer so far:\n{answer}\n\n"
    "What important sub-topics or questions are NOT yet covered or are only mentioned briefly?\n"
    "Return a JSON array of 2-4 specific gap questions to search next. Return ONLY the JSON array."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_gemini_client():
    from core.model_manager import ModelManager
    from config.settings_loader import reload_settings
    agent_cfg = reload_settings().get("agent", {})
    provider = agent_cfg.get("model_provider", "gemini")
    model = agent_cfg.get("default_model", "gemini-2.5-flash")
    return ModelManager(model_name=model, provider=provider)


def _build_sources_block(sources: list[dict]) -> str:
    """Format source documents into a numbered text block for the prompt."""
    parts = []
    for i, src in enumerate(sources, 1):
        url = src.get("url", "")
        title = src.get("title", "")
        content = src.get("content", "")[:6000]
        parts.append(
            f"[{i}] URL: {url}\n"
            f"    Title: {title}\n"
            f"    Content: {content}\n"
        )
    return "\n".join(parts)


def _parse_synthesis(raw: str, sources: list[dict]) -> SynthesisResult:
    """Parse the model's combined markdown + JSON output into a SynthesisResult."""

    # Split off the trailing JSON block (inside ```json ... ```)
    answer_md = raw
    json_block = {}

    match = re.search(r"```json\s*\n(.*?)```", raw, re.DOTALL)
    if match:
        answer_md = raw[: match.start()].strip()
        try:
            json_block = json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Build Citation objects from the JSON block (preferred) or from sources
    citations: list[Citation] = []
    for c in json_block.get("citations", []):
        citations.append(Citation(
            index=c.get("index", 0),
            url=c.get("url", ""),
            title=c.get("title", ""),
            timestamp=c.get("timestamp", ""),
            credibility=c.get("credibility", "MEDIUM"),
        ))

    # Fallback: build from sources if the model didn't return citations
    if not citations:
        for i, src in enumerate(sources, 1):
            citations.append(Citation(
                index=i,
                url=src.get("url", ""),
                title=src.get("title", ""),
            ))

    return SynthesisResult(
        answer_md=answer_md,
        citations=citations,
        executive_summary=json_block.get("executive_summary", ""),
        contradictions=json_block.get("contradictions", []),
        confidence_per_para=json_block.get("confidence_per_para", []),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def synthesize(
    query: str,
    sources: list[dict],
    focus_mode: str = "web",
    iteration: int = 1,
) -> SynthesisResult:
    """Synthesize *sources* into a cited narrative answering *query*.

    Each source dict should have keys: url, title, content.
    Returns a SynthesisResult with markdown, citations, contradictions, etc.
    """
    sources_block = _build_sources_block(sources)
    prompt = SYNTHESIS_PROMPT.format(
        n_sources=len(sources),
        query=query,
        focus_mode=focus_mode,
        iteration=iteration,
        sources_block=sources_block,
    )

    client = _get_gemini_client()
    raw = await client.generate_text(prompt)
    return _parse_synthesis(raw, sources)


async def identify_gaps(query: str, answer_md: str) -> list[str]:
    """Ask the model what's missing from the answer so far.

    Returns a list of 2-4 gap questions for follow-up searches.
    """
    prompt = GAP_PROMPT.format(query=query, answer=answer_md[:8000])

    client = _get_gemini_client()
    raw = await client.generate_text(prompt)

    # Strip markdown fences
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    try:
        gaps = json.loads(raw)
        if isinstance(gaps, list):
            return [str(g) for g in gaps][:4]
    except json.JSONDecodeError:
        pass

    # Fallback: split by lines
    return [line.strip().strip('"').strip("- ") for line in raw.splitlines() if line.strip()][:4]
