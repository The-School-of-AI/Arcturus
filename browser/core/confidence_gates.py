"""
Confidence-Threshold Gates

Safety mechanism for autonomous execution:
- Per-action confidence thresholds
- Pause execution when confidence drops below threshold
- Send approval requests via notification channels
- Dial autonomy-safety tradeoff per workflow
"""

from typing import Dict, Callable, Optional, List, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio


class ActionCategory(Enum):
    """Categories of actions with different risk levels"""
    NAVIGATION = "navigation"  # Low risk
    DATA_ENTRY = "data_entry"  # Medium risk
    FORM_SUBMISSION = "form_submission"  # Medium-high risk
    DELETION = "deletion"  # High risk
    PAYMENT = "payment"  # Critical risk
    OTHER = "other"  # Default


@dataclass
class GateThreshold:
    """Confidence threshold for action category"""
    category: ActionCategory
    min_confidence: float  # 0.0-1.0
    requires_human_approval: bool = False


@dataclass
class GateDecision:
    """Result of gate evaluation"""
    passed: bool  # True if action can proceed
    confidence: float
    threshold: float
    category: ActionCategory
    reason: str
    approval_request_id: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


class ConfidenceGate:
    """
    Individual gate for a specific action.
    
    Evaluates whether action confidence meets threshold.
    """
    
    def __init__(
        self,
        category: ActionCategory,
        min_confidence: float = 0.80,
    ):
        self.category = category
        self.min_confidence = min_confidence
    
    def evaluate(
        self,
        action_confidence: float,
    ) -> tuple[bool, str]:
        """
        Evaluate if action passes gate.
        
        Args:
            action_confidence: Confidence score from LLM (0.0-1.0)
        
        Returns:
            (passes, reason)
        """
        if action_confidence >= self.min_confidence:
            return True, f"Confidence {action_confidence:.2f} >= threshold {self.min_confidence}"
        else:
            return False, f"Confidence {action_confidence:.2f} < threshold {self.min_confidence}"


class GateManager:
    """
    Manages confidence gates for safe autonomous execution.
    
    Features:
    - Per-category confidence thresholds
    - Human approval workflow integration
    - Audit trail of gate decisions
    - Real-time override capability
    """
    
    def __init__(self, config: Optional[Dict[ActionCategory, float]] = None):
        """
        Initialize gate manager.
        
        Args:
            config: Dict of ActionCategory -> min_confidence threshold
        """
        # Default thresholds (can be overridden)
        self.thresholds = {
            ActionCategory.NAVIGATION: 0.80,
            ActionCategory.DATA_ENTRY: 0.85,
            ActionCategory.FORM_SUBMISSION: 0.85,
            ActionCategory.DELETION: 0.95,
            ActionCategory.PAYMENT: 1.0,  # Always require approval
            ActionCategory.OTHER: 0.80,
        }
        
        # Override with provided config
        if config:
            self.thresholds.update(config)
        
        self.gates: Dict[ActionCategory, ConfidenceGate] = {
            cat: ConfidenceGate(cat, threshold)
            for cat, threshold in self.thresholds.items()
        }
        
        self.decisions: List[GateDecision] = []
        self.approval_callbacks: Dict[str, Callable] = {}  # approval_id -> callback
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}  # approval_id -> details
    
    def evaluate_action(
        self,
        category: ActionCategory,
        confidence: float,
        action_description: str,
    ) -> GateDecision:
        """
        Evaluate if action should proceed based on confidence.
        
        Args:
            category: Action category
            confidence: Confidence score from LLM
            action_description: Human-readable action description
        
        Returns:
            GateDecision with pass/fail and reasons
        """
        gate = self.gates.get(category, self.gates[ActionCategory.OTHER])
        threshold = self.thresholds.get(category, 0.80)
        
        passed, reason = gate.evaluate(confidence)
        
        # Determine if human approval is needed
        requires_approval = (
            not passed or  # Failed gate check
            category == ActionCategory.PAYMENT or  # Always approve payments
            category == ActionCategory.DELETION and confidence < 0.98  # High-risk deletions
        )
        
        approval_id = None
        if requires_approval:
            approval_id = self._create_approval_request(
                category,
                confidence,
                action_description,
            )
        
        decision = GateDecision(
            passed=passed,
            confidence=confidence,
            threshold=threshold,
            category=category,
            reason=reason,
            approval_request_id=approval_id,
        )
        
        self.decisions.append(decision)
        
        return decision
    
    def _create_approval_request(
        self,
        category: ActionCategory,
        confidence: float,
        action_description: str,
    ) -> str:
        """Create human approval request"""
        approval_id = f"approval_{len(self.pending_approvals)}"
        
        self.pending_approvals[approval_id] = {
            'category': category.value,
            'confidence': confidence,
            'action': action_description,
            'created_at': datetime.utcnow(),
            'status': 'pending',
        }
        
        return approval_id
    
    def approve_action(
        self,
        approval_id: str,
        approved_by: str,
    ) -> bool:
        """
        Approve a pending action.
        
        Args:
            approval_id: ID of approval request
            approved_by: Who approved (user ID or system)
        
        Returns:
            True if approved successfully
        """
        if approval_id not in self.pending_approvals:
            return False
        
        approval = self.pending_approvals[approval_id]
        approval['status'] = 'approved'
        approval['approved_by'] = approved_by
        approval['approved_at'] = datetime.utcnow()
        
        # Call any registered callback
        if approval_id in self.approval_callbacks:
            callback = self.approval_callbacks[approval_id]
            callback(approval_id, True, approved_by)
        
        return True
    
    def reject_action(
        self,
        approval_id: str,
        rejected_by: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Reject a pending action"""
        if approval_id not in self.pending_approvals:
            return False
        
        approval = self.pending_approvals[approval_id]
        approval['status'] = 'rejected'
        approval['rejected_by'] = rejected_by
        approval['rejection_reason'] = reason
        approval['rejected_at'] = datetime.utcnow()
        
        # Call any registered callback
        if approval_id in self.approval_callbacks:
            callback = self.approval_callbacks[approval_id]
            callback(approval_id, False, rejected_by)
        
        return True
    
    def set_approval_callback(
        self,
        approval_id: str,
        callback: Callable,
    ):
        """Register callback for approval decision"""
        self.approval_callbacks[approval_id] = callback
    
    def update_threshold(
        self,
        category: ActionCategory,
        new_threshold: float,
    ):
        """Update confidence threshold for category"""
        if 0.0 <= new_threshold <= 1.0:
            self.thresholds[category] = new_threshold
            self.gates[category] = ConfidenceGate(category, new_threshold)
    
    def get_thresholds(self) -> Dict[str, float]:
        """Get current thresholds"""
        return {cat.value: threshold for cat, threshold in self.thresholds.items()}
    
    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get list of pending approvals"""
        return [
            {
                'approval_id': approval_id,
                **approval,
            }
            for approval_id, approval in self.pending_approvals.items()
            if approval['status'] == 'pending'
        ]
    
    def get_decision_statistics(self) -> Dict[str, Any]:
        """Get gate decision statistics"""
        passed_count = sum(1 for d in self.decisions if d.passed)
        failed_count = sum(1 for d in self.decisions if not d.passed)
        
        by_category = {}
        for decision in self.decisions:
            cat = decision.category.value
            if cat not in by_category:
                by_category[cat] = {'passed': 0, 'failed': 0}
            
            if decision.passed:
                by_category[cat]['passed'] += 1
            else:
                by_category[cat]['failed'] += 1
        
        return {
            'total_decisions': len(self.decisions),
            'passed': passed_count,
            'failed': failed_count,
            'pass_rate': passed_count / len(self.decisions) if self.decisions else 0,
            'by_category': by_category,
            'pending_approvals': len(self.get_pending_approvals()),
        }
