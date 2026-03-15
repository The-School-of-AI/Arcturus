"""
Kura Architecture: Multi-Agent Debate System

Three-agent voting system for decision-making:
- Planner: Decides what sub-goal to execute
- Executor: Executes the sub-goal (naive)
- Critic: Evaluates if execution was correct

Majority vote determines action. Critic triggers backtracking on errors.
Achieved 87% accuracy on WebVoyager (vs ~70% for single-agent).
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class AgentRole(Enum):
    """Roles in Kura multi-agent system"""
    PLANNER = "planner"
    EXECUTOR = "executor"
    CRITIC = "critic"


@dataclass
class AgentVote:
    """Vote from an agent"""
    role: AgentRole
    decision: str  # "proceed", "reject", "retry", "backtrack"
    confidence: float  # 0.0-1.0
    reasoning: str
    alternative_suggestions: List[str] = None


@dataclass
class DebateResult:
    """Result of multi-agent debate"""
    final_decision: str
    confidence: float
    votes: List[AgentVote]
    majority_reached: bool
    dissenting_agents: List[AgentRole]


class KuraAgent:
    """
    Multi-agent debate system using Kura architecture.
    
    Instead of trusting single LLM decision, three agents debate:
    1. Planner suggests action
    2. Executor would execute it (naive perspective)
    3. Critic questions if it's correct
    
    Majority vote wins; Critic can trigger backtrack.
    """
    
    def __init__(self, use_real_llms: bool = False):
        """
        Initialize Kura agent system.
        
        Args:
            use_real_llms: If False, uses mock LLMs for testing
        """
        self.use_real_llms = use_real_llms
        self.debate_history: List[DebateResult] = []
    
    def debate_action(
        self,
        current_goal: str,
        page_state: Dict[str, Any],
        possible_actions: List[Dict[str, str]],
        context: str = "",
    ) -> DebateResult:
        """
        Run multi-agent debate on proposed action.
        
        Args:
            current_goal: Current sub-goal to achieve
            page_state: Current page state (URL, DOM, etc.)
            possible_actions: List of possible actions
            context: Additional context for reasoning
        
        Returns:
            DebateResult with final decision and agent votes
        """
        # Get vote from each agent
        planner_vote = self._get_planner_vote(current_goal, page_state, possible_actions)
        executor_vote = self._get_executor_vote(planner_vote.decision, page_state)
        critic_vote = self._get_critic_vote(planner_vote.decision, executor_vote.decision, page_state)
        
        votes = [planner_vote, executor_vote, critic_vote]
        
        # Determine majority
        decision_counts = {}
        for vote in votes:
            decision = vote.decision
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        
        # Find majority decision
        final_decision = max(decision_counts, key=decision_counts.get)
        majority_reached = decision_counts[final_decision] >= 2
        
        # Find dissenting agents
        dissenting = [v.role for v in votes if v.decision != final_decision]
        
        # Calculate confidence as average of voting agents
        voting_votes = [v for v in votes if v.decision == final_decision]
        confidence = sum(v.confidence for v in voting_votes) / len(voting_votes) if voting_votes else 0.0
        
        # Build result
        result = DebateResult(
            final_decision=final_decision,
            confidence=confidence,
            votes=votes,
            majority_reached=majority_reached,
            dissenting_agents=dissenting,
        )
        
        self.debate_history.append(result)
        
        return result
    
    def _get_planner_vote(
        self,
        goal: str,
        page_state: Dict[str, Any],
        possible_actions: List[Dict[str, str]],
    ) -> AgentVote:
        """
        Get Planner's vote on next action.
        
        Planner decides what sub-goal to work on next.
        """
        if self.use_real_llms:
            # Would call real LLM here
            pass
        
        # Mock implementation
        decision = "proceed"  # Recommend proceeding with first action
        confidence = 0.85
        reasoning = "First action aligns with goal"
        
        return AgentVote(
            role=AgentRole.PLANNER,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            alternative_suggestions=["reject", "retry"],
        )
    
    def _get_executor_vote(
        self,
        proposed_action: str,
        page_state: Dict[str, Any],
    ) -> AgentVote:
        """
        Get Executor's vote on whether action is executable.
        
        Executor asks: Can this action actually be performed on current page?
        """
        if self.use_real_llms:
            # Would call real LLM here
            pass
        
        # Mock implementation
        # Check if proposed action is feasible
        decision = "proceed" if proposed_action != "reject" else "reject"
        confidence = 0.80
        reasoning = "Action can be executed with current page state"
        
        return AgentVote(
            role=AgentRole.EXECUTOR,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
        )
    
    def _get_critic_vote(
        self,
        planner_decision: str,
        executor_decision: str,
        page_state: Dict[str, Any],
    ) -> AgentVote:
        """
        Get Critic's vote on whether decision is correct.
        
        Critic asks: Is this the right action? Will it succeed?
        Critic can trigger backtracking if it detects an error state.
        """
        if self.use_real_llms:
            # Would call real LLM here
            pass
        
        # Mock implementation
        # Critic is skeptical; raises confidence bar
        if planner_decision == executor_decision:
            decision = planner_decision
            confidence = 0.75  # Lower than planner (skeptical)
        else:
            decision = "retry"
            confidence = 0.60
        
        reasoning = "Checking for state errors before proceeding"
        
        return AgentVote(
            role=AgentRole.CRITIC,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            alternative_suggestions=["backtrack"],
        )
    
    def should_trigger_backtrack(self, debate_result: DebateResult) -> bool:
        """
        Determine if Critic's concerns warrant backtracking.
        
        Returns:
            True if backtrack should be triggered
        """
        # Backtrack if:
        # 1. Critic votes to backtrack, and
        # 2. Other agents don't have high confidence
        
        critic_vote = next((v for v in debate_result.votes if v.role == AgentRole.CRITIC), None)
        
        if not critic_vote:
            return False
        
        if critic_vote.decision == "backtrack" and critic_vote.confidence > 0.7:
            return True
        
        # Also backtrack if no majority reached and critic is concerned
        if not debate_result.majority_reached and debate_result.confidence < 0.65:
            return True
        
        return False
    
    def get_debate_statistics(self) -> Dict[str, Any]:
        """Get statistics on debates"""
        if not self.debate_history:
            return {}
        
        proceed_count = sum(1 for d in self.debate_history if d.final_decision == "proceed")
        retry_count = sum(1 for d in self.debate_history if d.final_decision == "retry")
        reject_count = sum(1 for d in self.debate_history if d.final_decision == "reject")
        backtrack_count = sum(1 for d in self.debate_history if d.final_decision == "backtrack")
        
        majority_reached = sum(1 for d in self.debate_history if d.majority_reached)
        
        return {
            'total_debates': len(self.debate_history),
            'proceed_decisions': proceed_count,
            'retry_decisions': retry_count,
            'reject_decisions': reject_count,
            'backtrack_decisions': backtrack_count,
            'majority_reached': majority_reached,
            'avg_confidence': sum(d.confidence for d in self.debate_history) / len(self.debate_history),
            'dissent_rate': sum(len(d.dissenting_agents) for d in self.debate_history) / len(self.debate_history) / 3,
        }
