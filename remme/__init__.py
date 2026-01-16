"""
REMME - "Remember Me"

The single source of truth for user knowledge and preferences.

REMME collects signals from multiple sources (conversations, notes, sessions, news),
extracts structured preferences, and serves all agents with user context.

Uses a two-LLM pipeline:
1. Extractor (frequent) - Free-form preference extraction to staging
2. Normalizer (batched) - Maps to schema via LLM + BeliefUpdateEngine

Usage:
    from remme import get_preferences_hub, get_staging_store
    from remme.normalizer import run_normalizer
"""

# Core stores
from remme.store import RemmeStore
from remme.extractor import RemmeExtractor
from remme.staging import StagingStore, get_staging_store

# Structured preference hubs
from remme.hubs import (
    get_preferences_hub,
    get_operating_context_hub,
    get_soft_identity_hub,
    PreferencesHub,
    OperatingContextHub,
    SoftIdentityHub,
)

# Engines
from remme.engines import (
    get_evidence_log,
    get_belief_engine,
    EvidenceLog,
    BeliefUpdateEngine,
)

# Bootstrap
from remme.bootstrap import (
    bootstrap_from_remme,
    extract_from_memories,
    apply_extraction_to_hubs,
)

# Normalizer
from remme.normalizer import Normalizer, run_normalizer

__all__ = [
    # Core
    "RemmeStore",
    "RemmeExtractor",
    "StagingStore",
    "get_staging_store",
    # Hubs
    "get_preferences_hub",
    "get_operating_context_hub", 
    "get_soft_identity_hub",
    "PreferencesHub",
    "OperatingContextHub",
    "SoftIdentityHub",
    # Engines
    "get_evidence_log",
    "get_belief_engine",
    "EvidenceLog",
    "BeliefUpdateEngine",
    # Bootstrap
    "bootstrap_from_remme",
    "extract_from_memories",
    "apply_extraction_to_hubs",
    # Normalizer
    "Normalizer",
    "run_normalizer",
]
