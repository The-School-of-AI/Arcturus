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
from difflib import SequenceMatcher
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
    key_findings: list[dict] = field(default_factory=list)  # [{finding, confidence, source_count}]
    contradictions: list[str] = field(default_factory=list)
    confidence_per_para: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYNTHESIS_PROMPT = (
    "You are an expert deep research analyst. Given a query and {n_sources} source documents, "
    "produce an exhaustive, publication-quality research report.\n\n"
    "QUERY: {query}\n"
    "FOCUS MODE: {focus_mode}\n"
    "ITERATION: {iteration} of 5\n\n"
    "SOURCE DOCUMENTS:\n{sources_block}\n\n"
    "REPORT STRUCTURE — follow this exact format:\n\n"
    "# [Descriptive Report Title]\n\n"
    "## Executive Summary\n"
    "[3-5 sentences: what was researched, key findings, primary takeaway]\n\n"
    "## Key Findings\n"
    "For each finding, rate confidence as HIGH / MEDIUM / LOW based on cross-source frequency:\n"
    "- HIGH = 3+ sources corroborate the same point\n"
    "- MEDIUM = 2 sources mention it\n"
    "- LOW = only 1 source mentions it\n\n"
    "- **[HIGH]** [Finding corroborated by 3+ sources] [1][4][7]\n"
    "- **[MEDIUM]** [Finding mentioned by 2 sources] [2][5]\n"
    "- **[LOW]** [Finding from single source] [3]\n"
    "- [Continue for ALL major findings — do not skip any]\n\n"
    "## Detailed Analysis\n\n"
    "### [Subtopic A]\n"
    "[In-depth narrative analysis. Every factual claim MUST have an inline [N] citation. "
    "Include specific data, statistics, comparisons. Minimum 2-3 paragraphs per subtopic.]\n\n"
    "### [Subtopic B]\n"
    "[Continue with additional subtopics as needed. Use ### headings to organize.]\n\n"
    "[Add as many subtopic sections as the evidence supports.]\n\n"
    "## Contradictions & Open Questions\n"
    "[Where sources disagree, state both positions with citations: "
    '"Source [N] claims X, while Source [M] states Y. The discrepancy may stem from..."]\n'
    '[If no contradictions exist, state "No significant contradictions were found across sources."]\n\n'
    "## Limitations\n"
    "[What could not be verified, areas where evidence is thin, sources that were inaccessible]\n\n"
    "## Conclusion\n"
    "[Synthesized conclusions with actionable recommendations if applicable]\n\n"
    "CITATION RULES:\n"
    "1. Place [N] IMMEDIATELY after the specific claim it supports, not at paragraph end.\n"
    '2. Multiple citations per sentence are encouraged: "X is true [1][3] while Y holds [2]."\n'
    "3. EVERY factual claim, statistic, date, and proper noun must have a citation.\n"
    "4. If a claim cannot be grounded in any source, mark it [unverified].\n"
    "5. Aim for HIGH citation density — at least one citation per sentence in the analysis.\n\n"
    "EXHAUSTIVE COVERAGE RULES:\n"
    "- Extract and cover EVERY distinct point, fact, and insight from EVERY source document.\n"
    "- Do NOT skip, omit, or gloss over any information — even minor details matter.\n"
    "- If multiple sources mention the same point, consolidate them into one statement with all citations.\n"
    "- Points mentioned by more sources get HIGHER confidence ratings.\n"
    "- Points mentioned by only one source still MUST be included (rated LOW).\n\n"
    "CONFIDENCE RATING (cross-source frequency):\n"
    "- **HIGH**: 3 or more sources corroborate the same claim — strong consensus.\n"
    "- **MEDIUM**: 2 sources mention or support the claim.\n"
    "- **LOW**: Only 1 source mentions it — include but flag as single-source.\n"
    "- Apply this rating in Key Findings AND in the JSON key_findings array.\n\n"
    "QUALITY STANDARDS:\n"
    "- Be EXHAUSTIVE: cover every angle the sources support. Do not summarize briefly.\n"
    "- Include specific numbers, dates, percentages, and data points from sources.\n"
    "- Use comparison tables (Markdown tables) when comparing multiple items.\n"
    "- Minimum report length: 1500 words for the markdown section.\n"
    "- Write for a knowledgeable audience — be analytical, not superficial.\n\n"
    "After the markdown report, end with a structured JSON block (inside ```json ... ```):\n"
    '{{\n'
    '  "executive_summary": "2-3 sentence summary",\n'
    '  "key_findings": [\n'
    '    {{"finding": "finding text", "confidence": "HIGH", "source_count": 4}},\n'
    '    {{"finding": "finding text", "confidence": "MEDIUM", "source_count": 2}},\n'
    '    ...\n'
    '  ],\n'
    '  "citations": [\n'
    '    {{"index": 1, "url": "...", "title": "...", "timestamp": "...", "credibility": "HIGH|MEDIUM|LOW"}},\n'
    '    ...\n'
    '  ],\n'
    '  "confidence_per_para": ["HIGH", "MEDIUM", ...],\n'
    '  "contradictions": ["Source 1 claims X while Source 3 states Y", ...],\n'
    '  "limitations": ["limitation 1", ...],\n'
    '  "flagged_unsupported": ["claim that had no grounding", ...]\n'
    '}}\n'
)

GAP_PROMPT = (
    'Given this research answer about: "{query}"\n\n'
    "Answer so far:\n{answer}\n\n"
    "What important sub-topics or questions are NOT yet covered or are only mentioned briefly?\n"
    "Return a JSON array of 2-4 specific gap questions to search next. Return ONLY the JSON array."
)

CONTRADICTION_RESOLUTION_PROMPT = (
    "You are a research analyst specializing in resolving conflicting information.\n\n"
    "ORIGINAL QUERY: {query}\n\n"
    "CONTRADICTIONS FOUND:\n{contradictions_block}\n\n"
    "For each contradiction above, generate 1-2 targeted search queries that would help "
    "determine which position is correct, or explain the discrepancy.\n\n"
    "Requirements:\n"
    "- Each query should be specific enough to find authoritative, recent sources.\n"
    "- Focus on finding primary sources, official data, or expert analyses.\n"
    "- Include queries that target the specific factual claims in dispute.\n\n"
    "Return ONLY a JSON array of search query strings (max 6 total). No markdown, no explanation."
)

FINAL_SYNTHESIS_PROMPT = (
    "You are an expert deep research analyst producing the FINAL comprehensive report.\n\n"
    "QUERY: {query}\n"
    "FOCUS MODE: {focus_mode}\n\n"
    "You have been provided {n_sources} source documents collected across multiple research "
    "iterations, including additional sources specifically gathered to resolve contradictions.\n\n"
    "PREVIOUSLY IDENTIFIED CONTRADICTIONS:\n{contradictions_block}\n\n"
    "RESOLUTION SOURCES (gathered specifically to resolve contradictions):\n"
    "{resolution_sources_block}\n\n"
    "ALL SOURCE DOCUMENTS:\n{sources_block}\n\n"
    "YOUR TASK: Produce a COMPREHENSIVE, EXHAUSTIVE research report that extracts and "
    "presents ALL information from ALL source documents. The report must be the equivalent "
    "of at least 2 full pages of dense, analytical content.\n\n"
    "REPORT STRUCTURE — follow this exact format:\n\n"
    "# [Descriptive Report Title]\n\n"
    "## Executive Summary\n"
    "[7-10 sentences: comprehensive overview of what was researched, methodology used, "
    "all key findings, main takeaways, and primary recommendations. This should be a "
    "standalone summary that captures the essence of the entire report.]\n\n"
    "## Key Findings\n"
    "List EVERY significant finding discovered across ALL sources. Do not limit this to "
    "3-5 items — include ALL findings:\n"
    "- HIGH = 3+ sources corroborate\n"
    "- MEDIUM = 2 sources mention it\n"
    "- LOW = single source (still MUST be included)\n\n"
    "- **[HIGH]** [Finding with full detail] [1][4][7]\n"
    "- [Continue until EVERY finding from EVERY source is listed]\n\n"
    "## Detailed Analysis\n\n"
    "This is the core of the report. Create a separate subsection for EACH major theme, "
    "dimension, or aspect found in the sources. You MUST have at least 6-8 subsections.\n\n"
    "### [Subtopic A]\n"
    "[Write 4-5 dense paragraphs. Include ALL specific data points: numbers, dates, "
    "percentages, names, statistics, quotes, comparisons. Every sentence must have "
    "an inline [N] citation. Do NOT summarize briefly — expand on each point with "
    "full context and analysis.]\n\n"
    "### [Subtopic B]\n"
    "[Continue with the same depth. Cross-reference information across sources. "
    "Include comparison tables where multiple sources provide different data points "
    "on the same topic.]\n\n"
    "[Continue adding subsections until ALL information from ALL sources is covered. "
    "If a source contains unique information not fitting existing subsections, create "
    "a new subsection for it. No source content should be left unreported.]\n\n"
    "## Resolved Contradictions\n"
    "[For EACH previously identified contradiction, explain:\n"
    "  1. The original disagreement (Source [N] vs Source [M])\n"
    "  2. What the resolution sources revealed\n"
    "  3. The most likely correct position with evidence\n"
    "  4. Why the discrepancy existed (methodology, timeframe, scope differences)]\n\n"
    "## Remaining Open Questions\n"
    "[Any contradictions or questions that could NOT be fully resolved, with explanation]\n\n"
    "## Limitations\n"
    "[What could not be verified, areas where evidence is thin]\n\n"
    "## Conclusion & Recommendations\n"
    "[Comprehensive synthesized conclusions with specific, actionable recommendations. "
    "At least 2-3 paragraphs.]\n\n"
    "CITATION RULES:\n"
    "1. Place [N] IMMEDIATELY after the specific claim.\n"
    '2. Multiple citations per sentence: "X is true [1][3] while Y holds [2]."\n'
    "3. EVERY factual claim must have a citation.\n"
    "4. If a claim cannot be grounded, mark it [unverified].\n\n"
    "EXHAUSTIVE COVERAGE — THIS IS CRITICAL:\n"
    "- Go through EACH source document one by one and extract EVERY distinct piece of "
    "information: facts, data points, statistics, quotes, names, dates, opinions, "
    "projections, and context.\n"
    "- Do NOT skip, summarize briefly, or gloss over ANY information from ANY source.\n"
    "- If a source mentions a specific number, date, percentage, or name — it MUST appear "
    "in your report.\n"
    "- Every source MUST be cited at least once. Track your citations and verify you have "
    "referenced all {n_sources} sources.\n"
    "- Consolidate overlapping points with ALL relevant citations.\n"
    "- If a source has unique information not covered elsewhere, give it its own paragraph "
    "or subsection.\n"
    "- Think of this as a data extraction task: your job is to transfer ALL information "
    "from the sources into the report, organized thematically.\n\n"
    "LENGTH & QUALITY REQUIREMENTS:\n"
    "- MINIMUM report length: 5000 words for the markdown section (approximately 2+ pages "
    "of dense content). Reports under 4000 words are UNACCEPTABLE.\n"
    "- Each Detailed Analysis subsection: minimum 4-5 substantive paragraphs.\n"
    "- Include comparison tables wherever sources provide parallel data points.\n"
    "- Include ALL specific numbers, dates, percentages, and data points from every source.\n"
    "- Be analytical and authoritative. Provide context and interpretation, not just facts.\n"
    "- This is the DEFINITIVE final report. A reader should never need to consult the "
    "original sources because everything is captured here.\n\n"
    "After the markdown report, end with a structured JSON block (inside ```json ... ```):\n"
    '{{\n'
    '  "executive_summary": "5-7 sentence summary",\n'
    '  "key_findings": [\n'
    '    {{"finding": "...", "confidence": "HIGH", "source_count": 4}},\n'
    '    ...\n'
    '  ],\n'
    '  "citations": [\n'
    '    {{"index": 1, "url": "...", "title": "...", "timestamp": "...", "credibility": "HIGH|MEDIUM|LOW"}},\n'
    '    ...\n'
    '  ],\n'
    '  "confidence_per_para": ["HIGH", "MEDIUM", ...],\n'
    '  "contradictions": ["resolved: ...", ...],\n'
    '  "limitations": ["limitation 1", ...],\n'
    '  "flagged_unsupported": ["claim without grounding", ...]\n'
    '}}\n'
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


def _build_sources_block(sources: list[dict], max_content_per_source: int = 6000) -> str:
    """Format source documents into a numbered text block for the prompt."""
    parts = []
    for i, src in enumerate(sources, 1):
        url = src.get("url", "")
        title = src.get("title", "")
        content = src.get("content", "")[:max_content_per_source]
        parts.append(
            f"[{i}] URL: {url}\n"
            f"    Title: {title}\n"
            f"    Content: {content}\n"
        )
    return "\n".join(parts)


def _deduplicate_sources(
    sources: list[dict],
    content_similarity_threshold: float = 0.85,
) -> list[dict]:
    """Remove duplicate URLs and near-duplicate content across all sources.

    Strategy:
      1. Exact URL dedup (first occurrence wins).
      2. Content similarity dedup using SequenceMatcher.quick_ratio()
         on first 2000 chars of each source's content.

    Returns deduplicated list preserving original order.
    """
    # Phase 1: URL dedup
    seen_urls: set[str] = set()
    url_deduped: list[dict] = []
    for src in sources:
        url = src.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        url_deduped.append(src)

    # Phase 2: Content similarity dedup (only for content >= 100 chars)
    kept: list[dict] = []
    kept_snippets: list[str] = []

    for src in url_deduped:
        snippet = src.get("content", "")[:2000]
        is_dup = False
        if len(snippet) >= 100:
            for existing in kept_snippets:
                if len(existing) >= 100 and SequenceMatcher(None, snippet, existing).quick_ratio() >= content_similarity_threshold:
                    is_dup = True
                    break
        if not is_dup:
            kept.append(src)
            kept_snippets.append(snippet)

    return kept


def _extract_contradictions_from_markdown(md: str) -> list[str]:
    """Extract contradictions from the markdown body as a fallback.

    Looks for the '## Contradictions & Open Questions' section and pulls
    out bullet points or sentences, filtering boilerplate like
    'No significant contradictions'.
    """
    # Find the contradictions section
    pattern = r"##\s*Contradictions\s*(?:&|and)\s*Open\s*Questions\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, md, re.DOTALL | re.IGNORECASE)
    if not match:
        return []

    section = match.group(1).strip()

    # Skip boilerplate
    skip_phrases = [
        "no significant contradictions",
        "no contradictions were found",
        "no contradictions exist",
        "no major contradictions",
    ]
    if any(phrase in section.lower() for phrase in skip_phrases):
        return []

    # Extract bullet points or lines
    contradictions = []
    for line in section.splitlines():
        line = line.strip()
        # Remove bullet markers
        line = re.sub(r"^[-*•]\s*", "", line)
        # Remove numbered list markers
        line = re.sub(r"^\d+\.\s*", "", line)
        line = line.strip()
        if len(line) > 20:  # Skip very short/empty lines
            contradictions.append(line)

    return contradictions


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

    # Extract contradictions: prefer JSON, fall back to markdown extraction
    contradictions = json_block.get("contradictions", [])
    if not contradictions:
        contradictions = _extract_contradictions_from_markdown(answer_md)

    return SynthesisResult(
        answer_md=answer_md,
        citations=citations,
        executive_summary=json_block.get("executive_summary", ""),
        key_findings=json_block.get("key_findings", []),
        contradictions=contradictions,
        confidence_per_para=json_block.get("confidence_per_para", []),
        limitations=json_block.get("limitations", []),
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


async def resolve_contradictions(
    query: str,
    contradictions: list[str],
) -> list[str]:
    """Thinker Agent: analyze contradictions and generate targeted resolution queries.

    Takes contradictions identified during synthesis and produces specific search
    queries designed to find authoritative sources that can resolve each disagreement.

    Returns a list of 2-6 targeted search queries, or empty list if no contradictions.
    """
    if not contradictions:
        return []

    contradictions_block = "\n".join(
        f"{i}. {c}" for i, c in enumerate(contradictions, 1)
    )

    prompt = CONTRADICTION_RESOLUTION_PROMPT.format(
        query=query,
        contradictions_block=contradictions_block,
    )

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
        queries = json.loads(raw)
        if isinstance(queries, list):
            return [str(q) for q in queries][:6]
    except json.JSONDecodeError:
        pass

    # Fallback: split by lines
    return [line.strip().strip('"').strip("- ") for line in raw.splitlines() if line.strip()][:6]


async def final_synthesize(
    query: str,
    all_sources: list[dict],
    resolution_sources: list[dict],
    contradictions: list[str],
    focus_mode: str = "web",
) -> SynthesisResult:
    """Final Summarizer Agent: produce comprehensive 2-3 page report from all sources.

    Deduplicates all sources, then produces a 3000+ word report that specifically
    addresses and resolves contradictions using the resolution evidence.
    """
    # Deduplicate all sources (originals + resolution sources combined)
    combined = all_sources + resolution_sources
    deduped = _deduplicate_sources(combined)

    # Cap per-source content to avoid exceeding context window
    max_content_per_source = min(8000, 250000 // max(len(deduped), 1))
    capped_sources = []
    for src in deduped:
        capped = dict(src)
        capped["content"] = capped.get("content", "")[:max_content_per_source]
        capped_sources.append(capped)

    sources_block = _build_sources_block(capped_sources, max_content_per_source=max_content_per_source)

    contradictions_block = "\n".join(
        f"{i}. {c}" for i, c in enumerate(contradictions, 1)
    ) if contradictions else "No contradictions were identified."

    resolution_block = (
        _build_sources_block(resolution_sources, max_content_per_source=max_content_per_source)
        if resolution_sources
        else "No additional resolution sources were needed."
    )

    prompt = FINAL_SYNTHESIS_PROMPT.format(
        n_sources=len(capped_sources),
        query=query,
        focus_mode=focus_mode,
        contradictions_block=contradictions_block,
        resolution_sources_block=resolution_block,
        sources_block=sources_block,
    )

    client = _get_gemini_client()
    raw = await client.generate_text(prompt)
    return _parse_synthesis(raw, capped_sources)
