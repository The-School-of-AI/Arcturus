"""
Phantom Browser Agent - Core Features

Production-grade browser automation with LLM reasoning.

Features:
- Three-Tier Execution Router (cost optimization)
- Secrets Vault (credential management)
- Immutable Audit Trail (compliance)
- Session Replay (debugging)
- State Backtracking (error recovery)
- Confidence Gates (safety)
- Prompt Injection Defense (security)
- Semantic Selector Healing (robustness)
- Action Caching (cost reduction)
- Decision Traces (analytics)
- Behavioral Biometrics (stealth)
- Kura Multi-Agent Debate (accuracy)
"""

from .router import ExecutionRouter, ExecutionTier
from .vault import SecretsVault, VaultBackend, CredentialType
from .audit import AuditTrail, AuditEvent, EventType
from .session_replay import (
    SessionRecorder,
    SessionReplayer,
    DOMSnapshot,
    ReplayEvent,
    DecisionOverlay,
)
from .backtracking import StateCheckpoint, BacktrackManager, BacktrackEvent
from .confidence_gates import ConfidenceGate, GateManager, ActionCategory, GateDecision
from .injection_defense import PromptInjectionDefense, InjectionRiskLevel
from .selector_healing import SelectorHealer, SelectorMatch
from .action_cache import ActionCache, CachedAction
from .decision_traces import (
    StructuredDecisionTrace,
    DecisionTracer,
    ElementScore,
    DecisionStatus,
)
from .biometrics import BehavioralBiometrics, MouseMove, KeyPress

__all__ = [
    # Router
    "ExecutionRouter",
    "ExecutionTier",
    
    # Vault
    "SecretsVault",
    "VaultBackend",
    "CredentialType",
    
    # Audit
    "AuditTrail",
    "AuditEvent",
    "EventType",
    
    # Session Replay
    "SessionRecorder",
    "SessionReplayer",
    "DOMSnapshot",
    "ReplayEvent",
    "DecisionOverlay",
    
    # Backtracking
    "StateCheckpoint",
    "BacktrackManager",
    "BacktrackEvent",
    
    # Confidence Gates
    "ConfidenceGate",
    "GateManager",
    "ActionCategory",
    "GateDecision",
    
    # Injection Defense
    "PromptInjectionDefense",
    "InjectionRiskLevel",
    
    # Selector Healing
    "SelectorHealer",
    "SelectorMatch",
    
    # Action Cache
    "ActionCache",
    "CachedAction",
    
    # Decision Traces
    "StructuredDecisionTrace",
    "DecisionTracer",
    "ElementScore",
    "DecisionStatus",
    
    # Biometrics
    "BehavioralBiometrics",
    "MouseMove",
    "KeyPress",
]
