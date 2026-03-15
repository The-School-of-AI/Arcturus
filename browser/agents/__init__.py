"""
Phantom Browser Agent - Multi-Agent Systems

Advanced reasoning through agent debate and voting systems.

Features:
- Kura Multi-Agent Debate: Planner-Executor-Critic voting
- Decision validation through multiple perspectives
- Self-healing via Critic-triggered backtracking
- Confidence-weighted consensus
"""

from .kura_agent import (
    KuraAgent,
    AgentRole,
    AgentVote,
    DebateResult,
)

__all__ = [
    "KuraAgent",
    "AgentRole",
    "AgentVote",
    "DebateResult",
]
