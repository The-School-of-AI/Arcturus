"""
Oracle Search Module (P2)
Provides deep research pipeline: query decomposition -> parallel web crawl -> synthesis -> citations.
"""
from search.focus_modes import FocusConfig, get_focus_config, list_focus_modes, apply_focus
from search.crawl_pipeline import CrawlPipeline, SourceDocument
from search.query_decomposer import decompose
from search.synthesizer import synthesize, identify_gaps, SynthesisResult, Citation
from search.deep_research import DeepResearchOrchestrator, DeepResearchEvent

__all__ = [
    "FocusConfig", "get_focus_config", "list_focus_modes", "apply_focus",
    "CrawlPipeline", "SourceDocument",
    "decompose",
    "synthesize", "identify_gaps", "SynthesisResult", "Citation",
    "DeepResearchOrchestrator", "DeepResearchEvent",
]
