"""
Browser Module - Unified Browser Automation Framework

Production-grade browser automation with enterprise-class features.

Combines original browser module capabilities with advanced Phantom Browser features:

Original Capabilities:
- Authentication & session management
- Browser control & navigation
- Web content extraction
- Session recording & replay
- Workflow orchestration
- Telemetry & monitoring

Phantom Browser Features (New):
- Three-Tier Execution Router (HTTP/Headless/Headful)
- Enterprise Secrets Vault (TTL, encryption, scoping)
- Immutable Audit Trail (cryptographic signatures)
- State Backtracking (checkpoint-based recovery)
- Confidence Gates (safety validation)
- Prompt Injection Defense (security)
- Semantic Selector Healing (resilience across redesigns)
- Action Caching (90% token savings)
- Decision Traces (structured logging)
- Behavioral Biometrics (human-like inputs)
- Multi-Agent Debate System (Kura)
- SDK Primitives (act, extract, agent)
- MCP Server Integration (Claude, Cursor, Copilot)

Example Usage:
    from browser import act, extract, agent, BrowserController, ExecutionRouter, SecretsVault
    
    # Single action
    result = await act("Click login button")
    
    # Extract structured data
    products = await extract("Get product listings", Product)
    
    # Multi-step workflow
    result = await agent("Complete checkout")
    
    # Manual control
    controller = BrowserController()
    await controller.start()
    
    # Advanced features
    router = ExecutionRouter()
    vault = SecretsVault()
"""

__version__ = "3.0.0"
__author__ = "Browser Team"

# ============================================================================
# ORIGINAL BROWSER CAPABILITIES
# ============================================================================

from .auth import AuthHandler
from .controller import BrowserController
from .extractor import PageExtractor
from .logic import AgentLoop, LLMClassifier, TaskComplexity
from .recorder import ActionRecorder
from .telemetry import BrowserTelemetry
from .workflow import WorkflowSequencer

# ============================================================================
# CORE PHANTOM BROWSER FEATURES
# ============================================================================

from .core.router import ExecutionRouter, ExecutionTier, RouteDecision
from .core.vault import SecretsVault, CredentialType, Credential
from .core.audit import AuditTrail, AuditEvent
from .core.backtracking import BacktrackManager, StateCheckpoint, BacktrackEvent
from .core.confidence_gates import ConfidenceGate, GateDecision, GateManager
from .core.injection_defense import PromptInjectionDefense, InjectionRiskLevel
from .core.selector_healing import SelectorHealer, SelectorMatch
from .core.action_cache import ActionCache, CachedAction
from .core.decision_traces import DecisionTracer, StructuredDecisionTrace
from .core.biometrics import BehavioralBiometrics, MouseMove, KeyPress
from .core.session_replay import SessionRecorder, SessionReplayer, ReplayEvent

# ============================================================================
# SDK LAYER - SIMPLIFIED PRIMITIVES
# ============================================================================

from .sdk.primitives import act, extract, agent

# ============================================================================
# MCP SERVER - IDE INTEGRATION
# ============================================================================

from .sdk.mcp_server import MCPServer, MCPTool, MCPToolType, get_mcp_server

# ============================================================================
# MULTI-AGENT SYSTEM
# ============================================================================

from .agents.kura_agent import KuraAgent, AgentRole, AgentVote, DebateResult

# ============================================================================
# PUBLIC API - EXPORTS
# ============================================================================

__all__ = [
    # Original Browser Capabilities
    "AuthHandler",
    "BrowserController",
    "PageExtractor",
    "AgentLoop",
    "LLMClassifier",
    "TaskComplexity",
    "ActionRecorder",
    "BrowserTelemetry",
    "WorkflowSequencer",
    
    # Core Features
    "ExecutionRouter",
    "ExecutionTier",
    "RouteDecision",
    "SecretsVault",
    "CredentialType",
    "Credential",
    "AuditTrail",
    "AuditEvent",
    "BacktrackManager",
    "StateCheckpoint",
    "BacktrackEvent",
    "ConfidenceGate",
    "GateDecision",
    "GateManager",
    "PromptInjectionDefense",
    "InjectionRiskLevel",
    "SelectorHealer",
    "SelectorMatch",
    "ActionCache",
    "CachedAction",
    "DecisionTracer",
    "StructuredDecisionTrace",
    "BehavioralBiometrics",
    "MouseMove",
    "KeyPress",
    "SessionRecorder",
    "SessionReplayer",
    "ReplayEvent",
    
    # SDK Primitives
    "act",
    "extract",
    "agent",
    
    # MCP Integration
    "MCPServer",
    "MCPTool",
    "MCPToolType",
    "get_mcp_server",
    
    # Multi-Agent System
    "KuraAgent",
    "AgentRole",
    "AgentVote",
    "DebateResult",
]

# ============================================================================
# MODULE METADATA
# ============================================================================

FEATURES = {
    "original": [
        "authentication",
        "browser_control",
        "content_extraction",
        "session_recording",
        "workflow_orchestration",
        "telemetry",
    ],
    "core": [
        "execution_routing",
        "secrets_management",
        "audit_trail",
        "state_backtracking",
        "confidence_gates",
        "injection_defense",
        "selector_healing",
        "action_caching",
        "decision_traces",
        "behavioral_biometrics",
        "session_replay",
    ],
    "advanced": [
        "sdk_primitives",
        "mcp_integration",
        "multi_agent_debate",
    ],
}

def get_capabilities():
    """Get available features and capabilities"""
    return FEATURES

def get_version():
    """Get module version"""
    return __version__
