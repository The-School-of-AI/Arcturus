"""
State Backtracking and Recovery

Checkpoint-based state restoration:
- Save browser session state at known-good points
- Detect incorrect states (wrong page, modal, content)
- Rewind to last checkpoint and replan
- Different from retry (reverses incorrect progress)
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import json


@dataclass
class StateCheckpoint:
    """Snapshot of browser/execution state"""
    checkpoint_id: str
    timestamp: datetime
    url: str
    page_title: str
    dom_hash: str  # Hash of page DOM
    cookies: Dict[str, str]  # Session cookies
    local_storage: Dict[str, str]
    session_storage: Dict[str, str]
    execution_state: Dict[str, Any]  # Planner state, variables, etc.
    step_number: int  # Which step in workflow
    completed_actions: List[str]  # Actions completed up to this point
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def serialize(self) -> bytes:
        """Serialize checkpoint for storage"""
        return pickle.dumps(self)
    
    @staticmethod
    def deserialize(data: bytes) -> 'StateCheckpoint':
        """Restore checkpoint from storage"""
        return pickle.loads(data)


@dataclass
class BacktrackEvent:
    """Record of a backtrack operation"""
    timestamp: datetime
    from_checkpoint: StateCheckpoint
    to_checkpoint: StateCheckpoint
    reason: str  # Why backtrack was triggered
    actions_rolled_back: List[str]


class BacktrackManager:
    """
    Manages checkpoint creation and backtracking.
    
    Enables workflows to recover from incorrect states by:
    1. Creating checkpoints at safe points
    2. Detecting invalid states
    3. Reverting to last good state
    4. Replanning from checkpoint
    """
    
    def __init__(self, max_checkpoints: int = 20):
        self.checkpoints: List[StateCheckpoint] = []
        self.current_checkpoint_index = -1
        self.max_checkpoints = max_checkpoints
        self.backtrack_history: List[BacktrackEvent] = []
        self.backtrack_count = 0
    
    def create_checkpoint(
        self,
        checkpoint_id: str,
        url: str,
        page_title: str,
        dom_hash: str,
        cookies: Dict[str, str],
        local_storage: Dict[str, str],
        session_storage: Dict[str, str],
        execution_state: Dict[str, Any],
        step_number: int,
        completed_actions: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StateCheckpoint:
        """
        Create a checkpoint at current state.
        
        Args:
            checkpoint_id: Unique identifier
            url: Current URL
            page_title: Page title
            dom_hash: Hash of DOM (for state comparison)
            cookies: Session cookies
            local_storage: localStorage contents
            session_storage: sessionStorage contents
            execution_state: Planner/workflow state
            step_number: Step count
            completed_actions: List of actions completed
            metadata: Optional additional metadata
        
        Returns:
            Created checkpoint
        """
        checkpoint = StateCheckpoint(
            checkpoint_id=checkpoint_id,
            timestamp=datetime.utcnow(),
            url=url,
            page_title=page_title,
            dom_hash=dom_hash,
            cookies=cookies,
            local_storage=local_storage,
            session_storage=session_storage,
            execution_state=execution_state,
            step_number=step_number,
            completed_actions=completed_actions,
            metadata=metadata or {},
        )
        
        # Manage checkpoint limit
        if len(self.checkpoints) >= self.max_checkpoints:
            self.checkpoints.pop(0)  # Remove oldest
        
        self.checkpoints.append(checkpoint)
        self.current_checkpoint_index = len(self.checkpoints) - 1
        
        return checkpoint
    
    def get_current_checkpoint(self) -> Optional[StateCheckpoint]:
        """Get the current/latest checkpoint"""
        if self.current_checkpoint_index >= 0:
            return self.checkpoints[self.current_checkpoint_index]
        return None
    
    def get_last_good_checkpoint(self) -> Optional[StateCheckpoint]:
        """Get previous checkpoint (last known-good state)"""
        if len(self.checkpoints) >= 2:
            return self.checkpoints[-2]
        return None
    
    def should_backtrack(
        self,
        current_url: str,
        current_dom_hash: str,
        expected_state: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if backtracking is needed.
        
        Args:
            current_url: Current page URL
            current_dom_hash: Current DOM hash
            expected_state: Expected state details for validation
        
        Returns:
            (should_backtrack, reason)
        """
        current = self.get_current_checkpoint()
        
        if not current:
            return False, None
        
        # Check for unexpected URL change
        if expected_state and 'expected_url' in expected_state:
            if current_url != expected_state['expected_url']:
                return True, f"URL mismatch: expected {expected_state['expected_url']}, got {current_url}"
        
        # Check for page content change (likely navigation away)
        if current_dom_hash != current.dom_hash:
            # Content changed; could be successful action or wrong page
            # Validator should have caught this; alert for potential error
            return True, "DOM changed unexpectedly (possible navigation)"
        
        return False, None
    
    def backtrack(self, reason: str) -> bool:
        """
        Backtrack to previous checkpoint.
        
        Args:
            reason: Why backtracking was triggered
        
        Returns:
            True if successful, False if no previous checkpoint
        """
        last_good = self.get_last_good_checkpoint()
        current = self.get_current_checkpoint()
        
        if not last_good:
            return False
        
        # Record backtrack event
        if current:
            event = BacktrackEvent(
                timestamp=datetime.utcnow(),
                from_checkpoint=current,
                to_checkpoint=last_good,
                reason=reason,
                actions_rolled_back=current.completed_actions[
                    len(last_good.completed_actions):
                ],
            )
            self.backtrack_history.append(event)
        
        # Move back
        self.current_checkpoint_index = len(self.checkpoints) - 2
        self.backtrack_count += 1
        
        return True
    
    def restore_checkpoint(self, checkpoint_index: int) -> bool:
        """
        Restore to specific checkpoint.
        
        Args:
            checkpoint_index: Index of checkpoint to restore
        
        Returns:
            True if successful
        """
        if 0 <= checkpoint_index < len(self.checkpoints):
            self.current_checkpoint_index = checkpoint_index
            return True
        return False
    
    def get_checkpoint_chain(self) -> List[Dict[str, Any]]:
        """Get readable representation of checkpoint chain"""
        return [
            {
                'id': cp.checkpoint_id,
                'step': cp.step_number,
                'url': cp.url,
                'timestamp': cp.timestamp.isoformat(),
                'actions': len(cp.completed_actions),
            }
            for cp in self.checkpoints
        ]
    
    def get_backtrack_statistics(self) -> Dict[str, Any]:
        """Get backtracking statistics"""
        total_actions_rolled_back = sum(
            len(event.actions_rolled_back)
            for event in self.backtrack_history
        )
        
        return {
            'total_backtracks': self.backtrack_count,
            'total_checkpoints': len(self.checkpoints),
            'current_index': self.current_checkpoint_index,
            'total_actions_rolled_back': total_actions_rolled_back,
            'recent_backtracks': [
                {
                    'timestamp': event.timestamp.isoformat(),
                    'reason': event.reason,
                    'actions_rolled_back': len(event.actions_rolled_back),
                }
                for event in self.backtrack_history[-10:]
            ],
        }
    
    def clear_history(self):
        """Clear backtrack history (not checkpoints)"""
        self.backtrack_history.clear()
        self.backtrack_count = 0
