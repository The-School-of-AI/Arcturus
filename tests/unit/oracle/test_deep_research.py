"""Unit tests for the deep research (Oracle) pipeline.

Covers: focus_modes, synthesizer helpers, query_decomposer,
crawl_pipeline, DeepResearchEvent, cache, and graph_bridge.
"""
import asyncio
import json
import os
import textwrap
from dataclasses import asdict
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# ── Module imports ──
from search.focus_modes import (
    FocusConfig,
    apply_focus,
    get_focus_config,
    list_focus_modes,
)
from search.synthesizer import (
    Citation,
    SynthesisResult,
    _build_sources_block,
    _deduplicate_sources,
    _extract_contradictions_from_markdown,
    _parse_synthesis,
)
from search.deep_research import DeepResearchEvent
from search.crawl_pipeline import SourceDocument


# =====================================================================
# 1. Focus Modes  (3 tests)
# =====================================================================


def test_get_focus_config_known_mode():
    """get_focus_config('academic') returns correct config with APA citations."""
    cfg = get_focus_config("academic")
    assert isinstance(cfg, FocusConfig)
    assert cfg.name == "academic"
    assert cfg.citation_format == "apa"
    assert "arxiv.org" in cfg.search_suffix


def test_get_focus_config_unknown_defaults_to_web():
    """Unknown mode falls back to 'web' config."""
    cfg = get_focus_config("nonexistent_mode")
    assert cfg.name == "web"
    assert cfg.search_suffix == ""


def test_apply_focus_appends_suffix():
    """apply_focus adds the mode suffix; 'web' leaves queries unchanged."""
    queries = ["query one", "query two"]

    # Code mode should append suffix
    enriched = apply_focus(queries, "code")
    for q in enriched:
        assert "site:github.com" in q

    # Web mode has no suffix — queries returned unchanged
    unchanged = apply_focus(queries, "web")
    assert unchanged == queries


# =====================================================================
# 2. Synthesizer helpers  (3 tests)
# =====================================================================

SAMPLE_SOURCES = [
    {"url": "https://example.com/1", "title": "Source One", "content": "Alpha content"},
    {"url": "https://example.com/2", "title": "Source Two", "content": "Beta content"},
]


def test_build_sources_block_formatting():
    """_build_sources_block produces numbered [N] URL/Title/Content blocks."""
    block = _build_sources_block(SAMPLE_SOURCES)
    assert "[1] URL: https://example.com/1" in block
    assert "[2] URL: https://example.com/2" in block
    assert "Title: Source One" in block
    assert "Content: Alpha content" in block


def test_build_sources_block_truncates_content():
    """Content longer than 6000 chars is truncated."""
    long_source = [{"url": "https://x.com", "title": "T", "content": "A" * 10000}]
    block = _build_sources_block(long_source)
    # The content portion should be at most 6000 chars
    content_line = [line for line in block.split("\n") if "Content:" in line][0]
    content_text = content_line.split("Content: ", 1)[1]
    assert len(content_text) == 6000


def test_parse_synthesis_with_json_block():
    """_parse_synthesis extracts markdown + structured JSON block correctly."""
    raw = textwrap.dedent("""\
        # Research Report

        The findings show X [1] and Y [2].

        ```json
        {
            "executive_summary": "Summary of research.",
            "citations": [
                {"index": 1, "url": "https://example.com/1", "title": "Source One", "credibility": "HIGH"},
                {"index": 2, "url": "https://example.com/2", "title": "Source Two", "credibility": "MEDIUM"}
            ],
            "confidence_per_para": ["HIGH"],
            "contradictions": ["Source 1 claims X while Source 2 states Y"]
        }
        ```
    """)
    result = _parse_synthesis(raw, SAMPLE_SOURCES)

    assert isinstance(result, SynthesisResult)
    assert "Research Report" in result.answer_md
    assert result.executive_summary == "Summary of research."
    assert len(result.citations) == 2
    assert result.citations[0].credibility == "HIGH"
    assert len(result.contradictions) == 1


def test_parse_synthesis_fallback_no_json():
    """Without a JSON block, citations are built from the source list."""
    raw = "# Report\n\nSome answer text without any JSON block."
    result = _parse_synthesis(raw, SAMPLE_SOURCES)

    assert result.answer_md == raw
    assert len(result.citations) == len(SAMPLE_SOURCES)
    assert result.citations[0].url == "https://example.com/1"
    assert result.executive_summary == ""


# =====================================================================
# 3. Query Decomposer  (2 tests)
# =====================================================================


@patch("search.query_decomposer._get_gemini_client")
def test_decompose_parses_json_array(mock_get_client):
    """decompose() parses a clean JSON array from the LLM and applies focus."""
    from search.query_decomposer import decompose

    mock_client = MagicMock()
    mock_client.generate_text = AsyncMock(
        return_value='["sub query 1", "sub query 2", "sub query 3"]'
    )
    mock_get_client.return_value = mock_client

    result = asyncio.run(decompose("test query", focus_mode="web", n_queries=3))

    assert len(result) == 3
    assert result[0] == "sub query 1"  # web mode has no suffix


@patch("search.query_decomposer._get_gemini_client")
def test_decompose_fallback_on_bad_json(mock_get_client):
    """decompose() falls back to line-splitting when LLM returns non-JSON."""
    from search.query_decomposer import decompose

    mock_client = MagicMock()
    mock_client.generate_text = AsyncMock(
        return_value="- first sub query\n- second sub query\n- third sub query"
    )
    mock_get_client.return_value = mock_client

    result = asyncio.run(decompose("test query", focus_mode="web", n_queries=6))

    assert len(result) >= 3
    assert "first sub query" in result[0]


# =====================================================================
# 4. Crawl Pipeline  (2 tests)
# =====================================================================


@patch("search.crawl_pipeline.smart_web_extract", new_callable=AsyncMock)
def test_extract_single_success(mock_extract):
    """_extract_single returns a SourceDocument with content on success."""
    from search.crawl_pipeline import _extract_single

    mock_extract.return_value = {
        "best_text": "Extracted page content here.",
        "title": "Page Title",
    }

    doc = asyncio.run(_extract_single("https://example.com", rank=1))

    assert isinstance(doc, SourceDocument)
    assert doc.error is None
    assert doc.title == "Page Title"
    assert "Extracted page content" in doc.content
    assert doc.rank == 1


@patch("search.crawl_pipeline.smart_web_extract", new_callable=AsyncMock)
def test_extract_single_timeout(mock_extract):
    """_extract_single returns a SourceDocument with error on timeout."""
    from search.crawl_pipeline import _extract_single

    mock_extract.side_effect = asyncio.TimeoutError()

    doc = asyncio.run(_extract_single("https://slow-site.com", rank=5))

    assert doc.error is not None
    assert "Timeout" in doc.error
    assert doc.content == ""


# =====================================================================
# 4b. Brave & Google Search API  (4 tests)
# =====================================================================


@patch.dict(os.environ, {"BRAVE_API_KEY": "test-brave-key"})
@patch("mcp_servers.tools.switch_search_method.httpx.AsyncClient")
def test_brave_api_returns_urls(mock_client_cls):
    """use_brave_api returns parsed URLs from Brave API JSON response."""
    from mcp_servers.tools.switch_search_method import use_brave_api

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "web": {
            "results": [
                {"url": "https://example.com/brave1"},
                {"url": "https://example.com/brave2"},
            ]
        }
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    urls = asyncio.run(use_brave_api("test query", limit=5))

    assert len(urls) == 2
    assert "https://example.com/brave1" in urls
    assert "https://example.com/brave2" in urls


def test_brave_api_skips_when_no_key():
    """use_brave_api returns [] when BRAVE_API_KEY is not set."""
    from mcp_servers.tools.switch_search_method import use_brave_api

    env = os.environ.copy()
    env.pop("BRAVE_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        urls = asyncio.run(use_brave_api("test query"))
    assert urls == []


@patch.dict(os.environ, {
    "GOOGLE_CUSTOM_SEARCH_API_KEY": "test-key",
    "GOOGLE_CUSTOM_SEARCH_ENGINE_ID": "test-cx",
})
@patch("mcp_servers.tools.switch_search_method.httpx.AsyncClient")
def test_google_cse_returns_urls(mock_client_cls):
    """use_google_custom_search returns parsed URLs from Google CSE JSON."""
    from mcp_servers.tools.switch_search_method import use_google_custom_search

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {"link": "https://example.com/google1"},
            {"link": "https://example.com/google2"},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    urls = asyncio.run(use_google_custom_search("test query", limit=5))

    assert len(urls) == 2
    assert "https://example.com/google1" in urls
    assert "https://example.com/google2" in urls


def test_google_cse_skips_when_no_key():
    """use_google_custom_search returns [] when keys are not set."""
    from mcp_servers.tools.switch_search_method import use_google_custom_search

    env = os.environ.copy()
    env.pop("GOOGLE_CUSTOM_SEARCH_API_KEY", None)
    env.pop("GOOGLE_CUSTOM_SEARCH_ENGINE_ID", None)
    with patch.dict(os.environ, env, clear=True):
        urls = asyncio.run(use_google_custom_search("test query"))
    assert urls == []


# =====================================================================
# 4c. Freshness Filtering  (2 tests)
# =====================================================================


def test_focus_config_freshness_values():
    """Focus configs have correct freshness values per mode."""
    news_cfg = get_focus_config("news")
    assert news_cfg.freshness == "pw"

    finance_cfg = get_focus_config("finance")
    assert finance_cfg.freshness == "pm"

    web_cfg = get_focus_config("web")
    assert web_cfg.freshness == ""

    academic_cfg = get_focus_config("academic")
    assert academic_cfg.freshness == ""

    code_cfg = get_focus_config("code")
    assert code_cfg.freshness == ""


@patch.dict(os.environ, {"BRAVE_API_KEY": "test-brave-key"})
@patch("mcp_servers.tools.switch_search_method.httpx.AsyncClient")
def test_brave_api_passes_freshness_param(mock_client_cls):
    """use_brave_api passes freshness param to Brave API when set."""
    from mcp_servers.tools.switch_search_method import use_brave_api

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "web": {
            "results": [
                {"url": "https://example.com/news1"},
            ]
        }
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    urls = asyncio.run(use_brave_api("test query", limit=5, freshness="pw"))

    assert len(urls) == 1
    # Verify freshness was passed in the request params
    call_kwargs = mock_client.get.call_args
    params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
    assert params["freshness"] == "pw"


# =====================================================================
# 4d. Enhanced Synthesis Parsing  (1 test)
# =====================================================================


def test_parse_synthesis_extracts_key_findings_and_limitations():
    """_parse_synthesis extracts key_findings (with confidence) and limitations from JSON block."""
    raw = textwrap.dedent("""\
        # Deep Research Report

        ## Executive Summary
        This report covers X.

        ## Key Findings
        - **[HIGH]** Finding one [1][2][3]
        - **[LOW]** Finding two [2]

        ## Detailed Analysis
        Analysis text here [1][2].

        ## Limitations
        Limited data on topic Z.

        ```json
        {
            "executive_summary": "Report covers X.",
            "key_findings": [
                {"finding": "Finding one", "confidence": "HIGH", "source_count": 3},
                {"finding": "Finding two", "confidence": "LOW", "source_count": 1}
            ],
            "citations": [
                {"index": 1, "url": "https://example.com/1", "title": "Source One", "credibility": "HIGH"},
                {"index": 2, "url": "https://example.com/2", "title": "Source Two", "credibility": "MEDIUM"}
            ],
            "confidence_per_para": ["HIGH", "MEDIUM"],
            "contradictions": [],
            "limitations": ["Limited data on topic Z", "No access to paywalled sources"],
            "flagged_unsupported": []
        }
        ```
    """)
    result = _parse_synthesis(raw, SAMPLE_SOURCES)

    assert isinstance(result, SynthesisResult)
    assert len(result.key_findings) == 2
    assert result.key_findings[0]["finding"] == "Finding one"
    assert result.key_findings[0]["confidence"] == "HIGH"
    assert result.key_findings[0]["source_count"] == 3
    assert result.key_findings[1]["confidence"] == "LOW"
    assert len(result.limitations) == 2
    assert "Limited data on topic Z" in result.limitations
    assert result.executive_summary == "Report covers X."


# =====================================================================
# 5. Deep Research Orchestrator  (2 tests)
# =====================================================================


def test_deep_research_event_to_sse():
    """DeepResearchEvent.to_sse() produces valid SSE format."""
    event = DeepResearchEvent("phase", {"phase": "decomposition", "iteration": 1})
    sse = event.to_sse()

    assert sse.startswith("data: ")
    assert sse.endswith("\n\n")

    payload = json.loads(sse[len("data: "):-2])
    assert payload["type"] == "phase"
    assert payload["phase"] == "decomposition"
    assert payload["iteration"] == 1


@patch("search.deep_research.graph_bridge")
@patch("search.deep_research.synthesize")
@patch("search.deep_research.decompose")
def test_orchestrator_stop_halts_iteration(
    mock_decompose, mock_synthesize, mock_graph_bridge
):
    """Calling stop() before run() prevents iteration events."""
    from search.deep_research import DeepResearchOrchestrator

    async def _run():
        orch = DeepResearchOrchestrator()
        orch.pipeline = MagicMock()
        orch.stop()

        events = []
        async for event in orch.run("test query", max_iterations=3):
            events.append(event)
        return events

    events = asyncio.run(_run())

    # Should get a done event (from the try block completing) but no phase events
    phase_events = [e for e in events if e.type_ == "phase"]
    assert len(phase_events) == 0

    done_events = [e for e in events if e.type_ == "done"]
    assert len(done_events) == 1


# =====================================================================
# 6. Cache  (2 tests)
# =====================================================================


def test_cache_get_or_none_miss_on_empty():
    """get_or_none returns None on an empty cache."""
    from search import cache

    cache.clear()
    assert cache.get_or_none("anything") is None


@patch("search.cache.get_embedding", create=True)
def test_cache_put_and_size(mock_import):
    """put() increments size; clear() resets to zero."""
    from search import cache

    cache.clear()
    assert cache.size() == 0

    # Mock get_embedding at the point it's imported inside put()
    fake_vec = np.random.randn(768).astype("float32")
    with patch("remme.utils.get_embedding", return_value=fake_vec):
        cache.put("test query", {"answer": "test result"})

    assert cache.size() == 1

    cache.clear()
    assert cache.size() == 0


# =====================================================================
# 7. Graph Bridge  (1 test)
# =====================================================================


def test_graph_bridge_session_lifecycle(tmp_path):
    """Full lifecycle: create -> add search -> add synthesis -> done."""
    from search import graph_bridge

    # Point graph_bridge to tmp_path for filesystem isolation
    original_base = graph_bridge._SESSIONS_BASE
    graph_bridge._SESSIONS_BASE = tmp_path

    try:
        run_id = "test_run_001"

        # Create session
        path = graph_bridge.create_deep_research_session(run_id, "test query")
        assert path.exists()

        data = json.loads(path.read_text())
        assert data["graph"]["research_mode"] == "deep_research"
        assert data["graph"]["status"] == "running"

        # Add search nodes
        graph_bridge.add_search_nodes(run_id, ["sq1", "sq2"], iteration=1)
        data = json.loads(path.read_text())
        node_ids = [n["id"] for n in data["nodes"]]
        assert "I1_Search_1" in node_ids
        assert "I1_Search_2" in node_ids

        # Add synthesis node
        synth_id = graph_bridge.add_synthesis_node(run_id, iteration=1)
        assert synth_id == "I1_Synthesize"

        # Mark iteration done
        graph_bridge.mark_iteration_done(run_id, 1, "synthesis output")
        data = json.loads(path.read_text())
        synth_node = next(n for n in data["nodes"] if n["id"] == "I1_Synthesize")
        assert synth_node["status"] == "completed"

        # Mark session done
        graph_bridge.mark_session_done(run_id)
        data = json.loads(path.read_text())
        assert data["graph"]["status"] == "completed"

    finally:
        graph_bridge._SESSIONS_BASE = original_base


# =====================================================================
# 8. Source Deduplication  (2 tests)
# =====================================================================


def test_deduplicate_sources_removes_duplicate_urls():
    """_deduplicate_sources removes sources with the same URL, keeping first."""
    sources = [
        {"url": "https://example.com/1", "title": "First", "content": "Content A"},
        {"url": "https://example.com/2", "title": "Second", "content": "Content B"},
        {"url": "https://example.com/1", "title": "First Dup", "content": "Content A again"},
        {"url": "https://example.com/3", "title": "Third", "content": "Content C"},
    ]

    result = _deduplicate_sources(sources)

    assert len(result) == 3
    urls = [s["url"] for s in result]
    assert urls == [
        "https://example.com/1",
        "https://example.com/2",
        "https://example.com/3",
    ]
    assert result[0]["title"] == "First"


def test_deduplicate_sources_removes_near_duplicate_content():
    """_deduplicate_sources removes sources with very similar content."""
    base_content = "This is a detailed article about quantum computing " * 50
    similar_content = "This is a detailed article about quantum computing " * 49 + "and more."
    different_content = "Machine learning is a subset of artificial intelligence " * 50

    sources = [
        {"url": "https://a.com", "title": "A", "content": base_content},
        {"url": "https://b.com", "title": "B", "content": similar_content},
        {"url": "https://c.com", "title": "C", "content": different_content},
    ]

    result = _deduplicate_sources(sources)

    assert len(result) == 2
    urls = [s["url"] for s in result]
    assert "https://a.com" in urls
    assert "https://c.com" in urls


# =====================================================================
# 9. Contradiction Resolution (Thinker Agent)  (2 tests)
# =====================================================================


@patch("search.synthesizer._get_gemini_client")
def test_resolve_contradictions_returns_queries(mock_get_client):
    """resolve_contradictions returns targeted search queries for each contradiction."""
    from search.synthesizer import resolve_contradictions

    mock_client = MagicMock()
    mock_client.generate_text = AsyncMock(
        return_value='["is X or Y correct for topic Z", "authoritative source on X vs Y"]'
    )
    mock_get_client.return_value = mock_client

    contradictions = [
        "Source 1 claims X while Source 3 states Y",
        "Source 2 says 100 but Source 4 reports 200",
    ]

    result = asyncio.run(resolve_contradictions("test query", contradictions))

    assert isinstance(result, list)
    assert len(result) == 2
    assert "X or Y" in result[0]


@patch("search.synthesizer._get_gemini_client")
def test_resolve_contradictions_empty_on_no_contradictions(mock_get_client):
    """resolve_contradictions returns [] when no contradictions provided."""
    from search.synthesizer import resolve_contradictions

    result = asyncio.run(resolve_contradictions("test query", []))

    assert result == []
    mock_get_client.assert_not_called()


# =====================================================================
# 10. Final Synthesis (Summarizer Agent)  (2 tests)
# =====================================================================


@patch("search.synthesizer._get_gemini_client")
def test_final_synthesize_produces_result(mock_get_client):
    """final_synthesize returns a SynthesisResult with comprehensive report."""
    from search.synthesizer import final_synthesize

    mock_client = MagicMock()
    raw_response = textwrap.dedent("""\
        # Final Comprehensive Report

        ## Executive Summary
        This is the definitive report covering all sources.

        ## Resolved Contradictions
        The contradiction about X was resolved: Source 1 was more recent.

        ```json
        {
            "executive_summary": "Definitive report on the topic.",
            "key_findings": [{"finding": "Key result", "confidence": "HIGH", "source_count": 5}],
            "citations": [
                {"index": 1, "url": "https://example.com/1", "title": "Source One", "credibility": "HIGH"}
            ],
            "confidence_per_para": ["HIGH"],
            "contradictions": ["resolved: Source 1 claims X was correct based on newer data"],
            "limitations": []
        }
        ```
    """)
    mock_client.generate_text = AsyncMock(return_value=raw_response)
    mock_get_client.return_value = mock_client

    all_sources = [
        {"url": "https://example.com/1", "title": "Source One", "content": "Content 1"},
        {"url": "https://example.com/2", "title": "Source Two", "content": "Content 2"},
    ]
    resolution_sources = [
        {"url": "https://example.com/3", "title": "Resolution Source", "content": "Resolves X"},
    ]
    contradictions = ["Source 1 claims X while Source 2 states Y"]

    result = asyncio.run(final_synthesize(
        query="test query",
        all_sources=all_sources,
        resolution_sources=resolution_sources,
        contradictions=contradictions,
        focus_mode="web",
    ))

    assert isinstance(result, SynthesisResult)
    assert "Final Comprehensive Report" in result.answer_md
    assert result.executive_summary == "Definitive report on the topic."
    assert len(result.contradictions) == 1


@patch("search.synthesizer._get_gemini_client")
def test_final_synthesize_deduplicates_sources(mock_get_client):
    """final_synthesize deduplicates sources before calling the LLM."""
    from search.synthesizer import final_synthesize

    mock_client = MagicMock()
    mock_client.generate_text = AsyncMock(
        return_value="# Report\n\nContent.\n\n```json\n{}\n```"
    )
    mock_get_client.return_value = mock_client

    all_sources = [
        {"url": "https://example.com/1", "title": "Source One", "content": "Content 1"},
        {"url": "https://example.com/2", "title": "Source Two", "content": "Content 2"},
    ]
    resolution_sources = [
        {"url": "https://example.com/1", "title": "Source One Dup", "content": "Content 1"},
        {"url": "https://example.com/3", "title": "New Source", "content": "Content 3"},
    ]

    result = asyncio.run(final_synthesize(
        query="test query",
        all_sources=all_sources,
        resolution_sources=resolution_sources,
        contradictions=[],
        focus_mode="web",
    ))

    # Verify the prompt reports 3 deduped sources (not 4)
    call_args = mock_client.generate_text.call_args[0][0]
    assert "3 source documents" in call_args
    # The ALL SOURCE DOCUMENTS block should have 3 entries (deduped)
    # Extract just the ALL SOURCE DOCUMENTS section
    all_sources_section = call_args.split("ALL SOURCE DOCUMENTS:\n")[1].split("\nREPORT STRUCTURE")[0]
    assert all_sources_section.count("] URL:") == 3


# =====================================================================
# 11. Orchestrator with Thinker + Final Synthesis  (1 test)
# =====================================================================


@patch("search.deep_research.graph_bridge")
@patch("search.deep_research.final_synthesize")
@patch("search.deep_research.resolve_contradictions")
@patch("search.deep_research.synthesize")
@patch("search.deep_research.identify_gaps")
@patch("search.deep_research.decompose")
def test_orchestrator_runs_thinker_and_final_synthesis(
    mock_decompose, mock_gaps, mock_synthesize,
    mock_resolve, mock_final_synth, mock_graph_bridge
):
    """Full pipeline: iterations -> thinker -> resolution search -> final synthesis."""
    from search.deep_research import DeepResearchOrchestrator

    mock_decompose.return_value = ["sub query 1"]
    mock_gaps.return_value = []

    iter_result = SynthesisResult(
        answer_md="# Report\nContent [1].",
        citations=[Citation(index=1, url="https://example.com/1", title="S1")],
        executive_summary="Summary",
        contradictions=["Source 1 claims X while Source 2 states Y"],
    )
    mock_synthesize.return_value = iter_result

    mock_resolve.return_value = ["resolve X vs Y"]

    final_result = SynthesisResult(
        answer_md="# Final Report\nComprehensive content.",
        citations=[Citation(index=1, url="https://example.com/1", title="S1")],
        executive_summary="Final summary",
        contradictions=["resolved: X is correct"],
    )
    mock_final_synth.return_value = final_result

    async def _run():
        orch = DeepResearchOrchestrator()
        mock_doc = SourceDocument(
            url="https://example.com/1", title="S1",
            content="content", rank=1
        )
        orch.pipeline = MagicMock()
        orch.pipeline.search_and_extract = AsyncMock(return_value=[mock_doc])

        events = []
        async for event in orch.run("test query", max_iterations=1):
            events.append(event)
        return events

    events = asyncio.run(_run())

    event_types = [e.type_ for e in events]
    assert "thinking" in event_types
    assert "final_synthesis" in event_types
    assert "done" in event_types

    done_event = [e for e in events if e.type_ == "done"][0]
    assert "Final Report" in done_event.data["final_report"]

    mock_resolve.assert_called_once_with(
        query="test query",
        contradictions=["Source 1 claims X while Source 2 states Y"],
    )
    mock_final_synth.assert_called_once()


# =====================================================================
# 12. Graph Bridge - Thinker & Final Synthesizer Nodes  (1 test)
# =====================================================================


def test_graph_bridge_thinker_and_final_synthesis_nodes(tmp_path):
    """ThinkerAgent and FinalSynthesizerAgent nodes are added correctly."""
    from search import graph_bridge

    original_base = graph_bridge._SESSIONS_BASE
    graph_bridge._SESSIONS_BASE = tmp_path

    try:
        run_id = "test_thinker_001"

        graph_bridge.create_deep_research_session(run_id, "test query")
        graph_bridge.add_search_nodes(run_id, ["sq1"], iteration=1)
        graph_bridge.add_synthesis_node(run_id, iteration=1)
        graph_bridge.mark_iteration_done(run_id, 1, "synthesis output")

        # Add thinker node
        thinker_id = graph_bridge.add_thinker_node(
            run_id,
            contradictions=["Source 1 vs Source 2"],
            resolution_queries=["resolve query 1"],
        )
        assert thinker_id == "ThinkerAgent"

        path = graph_bridge._session_path(run_id)
        data = json.loads(path.read_text())
        node_ids = [n["id"] for n in data["nodes"]]
        assert "ThinkerAgent" in node_ids

        thinker_node = next(n for n in data["nodes"] if n["id"] == "ThinkerAgent")
        assert thinker_node["agent"] == "ThinkerAgent"
        assert thinker_node["status"] == "completed"

        # Add final synthesis node
        final_id = graph_bridge.add_final_synthesis_node(run_id)
        assert final_id == "FinalSynthesizer"

        data = json.loads(path.read_text())
        node_ids = [n["id"] for n in data["nodes"]]
        assert "FinalSynthesizer" in node_ids

        # Mark final synthesis done
        graph_bridge.mark_final_synthesis_done(run_id, "final output")
        data = json.loads(path.read_text())
        final_node = next(n for n in data["nodes"] if n["id"] == "FinalSynthesizer")
        assert final_node["status"] == "completed"
        assert final_node["output"] == "final output"

    finally:
        graph_bridge._SESSIONS_BASE = original_base


# =====================================================================
# 13. Contradiction Extraction from Markdown  (3 tests)
# =====================================================================


def test_extract_contradictions_from_markdown_with_bullets():
    """_extract_contradictions_from_markdown extracts bullet-pointed contradictions."""
    md = textwrap.dedent("""\
        ## Key Findings
        - Finding one

        ## Contradictions & Open Questions
        - Source [1] claims the market grew 15%, while Source [3] states it declined by 2%.
        - Source [2] says the product launched in 2023, but Source [4] reports a 2024 launch.

        ## Limitations
        Limited data available.
    """)
    result = _extract_contradictions_from_markdown(md)

    assert len(result) == 2
    assert "market grew 15%" in result[0]
    assert "product launched in 2023" in result[1]


def test_extract_contradictions_from_markdown_no_contradictions():
    """_extract_contradictions_from_markdown returns [] for boilerplate 'no contradictions'."""
    md = textwrap.dedent("""\
        ## Contradictions & Open Questions
        No significant contradictions were found across sources.

        ## Limitations
        Limited data.
    """)
    result = _extract_contradictions_from_markdown(md)
    assert result == []


def test_extract_contradictions_from_markdown_no_section():
    """_extract_contradictions_from_markdown returns [] when section is missing."""
    md = "## Key Findings\n- Finding one\n\n## Limitations\nNone."
    result = _extract_contradictions_from_markdown(md)
    assert result == []


# =====================================================================
# 14. _parse_synthesis Markdown Fallback  (1 test)
# =====================================================================


def test_parse_synthesis_falls_back_to_markdown_contradictions():
    """_parse_synthesis extracts contradictions from markdown when JSON has none."""
    raw = textwrap.dedent("""\
        # Research Report

        ## Key Findings
        - Finding one [1]

        ## Contradictions & Open Questions
        - Source [1] claims X grew by 50%, while Source [2] reports only 10% growth.

        ## Limitations
        None significant.

        ```json
        {
            "executive_summary": "Summary here.",
            "citations": [
                {"index": 1, "url": "https://example.com/1", "title": "S1", "credibility": "HIGH"}
            ],
            "contradictions": [],
            "limitations": []
        }
        ```
    """)
    result = _parse_synthesis(raw, SAMPLE_SOURCES)

    assert len(result.contradictions) == 1
    assert "X grew by 50%" in result.contradictions[0]
