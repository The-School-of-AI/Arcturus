"""
Oracle Search Module (P2)
Provides deep research pipeline: query decomposition -> parallel web crawl -> synthesis -> citations.
"""
from search.focus_modes import FocusConfig, get_focus_config, list_focus_modes, apply_focus
from search.crawl_pipeline import CrawlPipeline, SourceDocument
from search.query_decomposer import decompose
from search.synthesizer import (
    synthesize, identify_gaps, resolve_contradictions, final_synthesize,
    SynthesisResult, Citation, _deduplicate_sources,
)
from search.deep_research import DeepResearchOrchestrator, DeepResearchEvent
from search.research_utils import (
    fix_citations, extract_sub_queries, extract_followup_queries,
    extract_contradiction_queries, build_source_index, preprocess_sources,
)

__all__ = [
    "FocusConfig", "get_focus_config", "list_focus_modes", "apply_focus",
    "CrawlPipeline", "SourceDocument",
    "decompose",
    "synthesize", "identify_gaps", "resolve_contradictions", "final_synthesize",
    "SynthesisResult", "Citation", "_deduplicate_sources",
    "DeepResearchOrchestrator", "DeepResearchEvent",
    "fix_citations", "extract_sub_queries", "extract_followup_queries",
    "extract_contradiction_queries", "build_source_index", "preprocess_sources",
]
