"""
Session Replay with Decision Overlay

Full session recording with synchronized timeline:
- DOM snapshots
- Screenshots
- Actions executed
- LLM reasoning traces
- Confidence scores
- Decision overlay (which elements considered, why selected)

Enables forensic debugging and stakeholder validation.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import base64
import json


class ReplayEventType(Enum):
    """Types of replay events"""
    DOM_SNAPSHOT = "dom_snapshot"
    SCREENSHOT = "screenshot"
    ACTION_EXECUTED = "action_executed"
    REASONING_TRACE = "reasoning_trace"
    DECISION_POINT = "decision_point"
    ERROR = "error"


@dataclass
class DOMSnapshot:
    """Captured DOM state"""
    timestamp: datetime
    html: str
    url: str
    title: str
    element_tree: Dict[str, Any]  # Simplified element structure
    interactive_elements: List[Dict[str, Any]]


@dataclass
class ReplayEvent:
    """Single event in session replay"""
    id: str
    type: ReplayEventType
    timestamp: datetime
    content: Dict[str, Any]
    duration_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return {
            'id': self.id,
            'type': self.type.value,
            'timestamp': self.timestamp.isoformat(),
            'content': self.content,
            'duration_ms': self.duration_ms,
        }


@dataclass
class DecisionOverlay:
    """Decision context for an action"""
    elements_considered: List[Dict[str, Any]]  # Elements analyzed
    elements_scores: Dict[str, float]  # Element ID -> confidence
    selected_element: Dict[str, Any]  # Chosen element
    reasoning: str  # Why this element was chosen
    confidence: float  # Overall confidence (0.0-1.0)
    alternative_paths: List[str]  # Other possible actions


class SessionRecorder:
    """Records all session activity for replay and debugging"""
    
    def __init__(self, session_id: str, workflow_id: str):
        self.session_id = session_id
        self.workflow_id = workflow_id
        self.start_time = datetime.utcnow()
        self.events: List[ReplayEvent] = []
        self.dom_snapshots: List[DOMSnapshot] = []
        self.screenshots: Dict[str, str] = {}  # timestamp -> base64 image
        self.decision_overlays: Dict[str, DecisionOverlay] = {}  # event_id -> overlay
    
    def record_dom_snapshot(
        self,
        url: str,
        title: str,
        html: str,
        element_tree: Dict[str, Any],
        interactive_elements: List[Dict[str, Any]],
    ) -> str:
        """Record a DOM snapshot"""
        snapshot = DOMSnapshot(
            timestamp=datetime.utcnow(),
            url=url,
            title=title,
            html=html,
            element_tree=element_tree,
            interactive_elements=interactive_elements,
        )
        self.dom_snapshots.append(snapshot)
        
        # Create replay event
        event_id = f"dom_{len(self.dom_snapshots)}"
        event = ReplayEvent(
            id=event_id,
            type=ReplayEventType.DOM_SNAPSHOT,
            timestamp=snapshot.timestamp,
            content={
                'url': snapshot.url,
                'title': snapshot.title,
                'element_count': len(snapshot.interactive_elements),
            },
        )
        self.events.append(event)
        
        return event_id
    
    def record_screenshot(self, image_data: bytes, event_id: Optional[str] = None) -> str:
        """Record a screenshot (base64 encoded)"""
        timestamp = datetime.utcnow().isoformat()
        
        if event_id is None:
            event_id = f"screenshot_{len(self.screenshots)}"
        
        # Encode as base64
        b64_image = base64.b64encode(image_data).decode('utf-8')
        self.screenshots[event_id] = b64_image
        
        # Create replay event
        event = ReplayEvent(
            id=event_id,
            type=ReplayEventType.SCREENSHOT,
            timestamp=datetime.utcnow(),
            content={'size_bytes': len(image_data)},
        )
        self.events.append(event)
        
        return event_id
    
    def record_action(
        self,
        action_type: str,
        target_element: Optional[Dict[str, Any]],
        parameters: Dict[str, Any],
        result: str,
        duration_ms: int,
    ) -> str:
        """Record an action execution"""
        event_id = f"action_{len([e for e in self.events if e.type == ReplayEventType.ACTION_EXECUTED])}"
        
        event = ReplayEvent(
            id=event_id,
            type=ReplayEventType.ACTION_EXECUTED,
            timestamp=datetime.utcnow(),
            content={
                'action_type': action_type,
                'target': target_element.get('id') if target_element else None,
                'parameters': parameters,
                'result': result,
            },
            duration_ms=duration_ms,
        )
        self.events.append(event)
        
        return event_id
    
    def record_reasoning_trace(
        self,
        llm_input: Dict[str, Any],
        llm_output: str,
        reasoning_steps: List[str],
        confidence: float,
    ) -> str:
        """Record LLM reasoning trace"""
        event_id = f"reasoning_{len([e for e in self.events if e.type == ReplayEventType.REASONING_TRACE])}"
        
        event = ReplayEvent(
            id=event_id,
            type=ReplayEventType.REASONING_TRACE,
            timestamp=datetime.utcnow(),
            content={
                'input_tokens': len(str(llm_input)),
                'output': llm_output,
                'steps': reasoning_steps,
                'confidence': confidence,
            },
        )
        self.events.append(event)
        
        return event_id
    
    def add_decision_overlay(
        self,
        event_id: str,
        overlay: DecisionOverlay,
    ):
        """Associate decision context with an action"""
        self.decision_overlays[event_id] = overlay
    
    def record_decision_point(
        self,
        goal: str,
        elements_considered: List[Dict[str, Any]],
        selected_element: Dict[str, Any],
        reasoning: str,
        confidence: float,
    ) -> str:
        """Record a decision point with overlay data"""
        event_id = f"decision_{len([e for e in self.events if e.type == ReplayEventType.DECISION_POINT])}"
        
        event = ReplayEvent(
            id=event_id,
            type=ReplayEventType.DECISION_POINT,
            timestamp=datetime.utcnow(),
            content={
                'goal': goal,
                'elements_considered': len(elements_considered),
                'selected_element_id': selected_element.get('id'),
                'confidence': confidence,
            },
        )
        self.events.append(event)
        
        # Create overlay
        overlay = DecisionOverlay(
            elements_considered=elements_considered,
            elements_scores={e.get('id'): e.get('score', 0.0) for e in elements_considered},
            selected_element=selected_element,
            reasoning=reasoning,
            confidence=confidence,
            alternative_paths=[],
        )
        self.decision_overlays[event_id] = overlay
        
        return event_id
    
    def record_error(
        self,
        error_type: str,
        message: str,
        context: Dict[str, Any],
    ) -> str:
        """Record an error"""
        event_id = f"error_{len([e for e in self.events if e.type == ReplayEventType.ERROR])}"
        
        event = ReplayEvent(
            id=event_id,
            type=ReplayEventType.ERROR,
            timestamp=datetime.utcnow(),
            content={
                'error_type': error_type,
                'message': message,
                'context': context,
            },
        )
        self.events.append(event)
        
        return event_id
    
    def get_timeline(self) -> List[Dict[str, Any]]:
        """Get synchronized timeline of all events"""
        timeline = []
        
        for event in self.events:
            item = event.to_dict()
            
            # Add screenshot if available
            if event.id in self.screenshots:
                item['screenshot'] = self.screenshots[event.id][:100] + "..."  # Truncate for preview
            
            # Add decision overlay if available
            if event.id in self.decision_overlays:
                overlay = self.decision_overlays[event.id]
                item['decision_overlay'] = {
                    'reasoning': overlay.reasoning,
                    'confidence': overlay.confidence,
                    'elements_considered': len(overlay.elements_considered),
                }
            
            timeline.append(item)
        
        return timeline
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get session statistics"""
        now = datetime.utcnow()
        duration = (now - self.start_time).total_seconds()
        
        event_counts = {}
        for event in self.events:
            key = event.type.value
            event_counts[key] = event_counts.get(key, 0) + 1
        
        return {
            'session_id': self.session_id,
            'workflow_id': self.workflow_id,
            'duration_seconds': duration,
            'total_events': len(self.events),
            'event_types': event_counts,
            'screenshots_count': len(self.screenshots),
            'decision_overlays_count': len(self.decision_overlays),
        }


class SessionReplayer:
    """Replays recorded sessions for debugging and analysis"""
    
    def __init__(self, recorder: SessionRecorder):
        self.recorder = recorder
    
    def get_event_at_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Get event at specific index"""
        if 0 <= index < len(self.recorder.events):
            event = self.recorder.events[index]
            return event.to_dict()
        return None
    
    def get_decision_overlay(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get decision overlay for event"""
        overlay = self.recorder.decision_overlays.get(event_id)
        if overlay:
            return {
                'elements_considered': overlay.elements_considered,
                'elements_scores': overlay.elements_scores,
                'selected_element': overlay.selected_element,
                'reasoning': overlay.reasoning,
                'confidence': overlay.confidence,
                'alternative_paths': overlay.alternative_paths,
            }
        return None
    
    def highlight_session(self, index: int) -> Dict[str, Any]:
        """Get detailed highlight at session point"""
        if index >= len(self.recorder.events):
            return {}
        
        event = self.recorder.events[index]
        
        highlight = {
            'event': event.to_dict(),
            'context': {
                'previous_events': len([e for e in self.recorder.events[:index] 
                                       if e.type == ReplayEventType.ACTION_EXECUTED]),
                'next_events': len([e for e in self.recorder.events[index:] 
                                   if e.type == ReplayEventType.ACTION_EXECUTED]),
            },
        }
        
        if event.id in self.recorder.decision_overlays:
            highlight['decision_overlay'] = self.get_decision_overlay(event.id)
        
        return highlight
    
    def export_session(self, format: str = "json") -> str:
        """Export session for storage/sharing"""
        data = {
            'metadata': {
                'session_id': self.recorder.session_id,
                'workflow_id': self.recorder.workflow_id,
                'start_time': self.recorder.start_time.isoformat(),
                'duration': (datetime.utcnow() - self.recorder.start_time).total_seconds(),
            },
            'timeline': self.recorder.get_timeline(),
            'statistics': self.recorder.get_statistics(),
        }
        
        if format == "json":
            return json.dumps(data, indent=2, default=str)
        
        return ""
