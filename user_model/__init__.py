# User Model Module
# Provides structured user preference, context, and identity management

from user_model.hubs.preferences_hub import PreferencesHub, get_preferences_hub
from user_model.hubs.operating_context_hub import OperatingContextHub, get_operating_context_hub
from user_model.hubs.soft_identity_hub import SoftIdentityHub, get_soft_identity_hub
from user_model.engines.evidence_log import EvidenceLog, get_evidence_log
from user_model.engines.belief_update import BeliefUpdateEngine, get_belief_engine

__all__ = [
    "PreferencesHub",
    "OperatingContextHub", 
    "SoftIdentityHub",
    "EvidenceLog",
    "BeliefUpdateEngine",
    "get_preferences_hub",
    "get_operating_context_hub",
    "get_soft_identity_hub",
    "get_evidence_log",
    "get_belief_engine",
]
