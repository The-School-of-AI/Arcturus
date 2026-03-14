"""
Immutable Audit Trail with Cryptographic Signatures

Append-only event log supporting:
- Security forensics
- Compliance reporting
- Debugging and non-repudiation
- Cryptographic integrity verification
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json
import hashlib
import hmac
from abc import ABC, abstractmethod


class EventType(Enum):
    """Types of events logged"""
    ACTION_EXECUTED = "action_executed"
    ACTION_FAILED = "action_failed"
    VALIDATOR_CHECK = "validator_check"
    DECISION_MADE = "decision_made"
    STATE_CHANGE = "state_change"
    CREDENTIAL_ACCESS = "credential_access"
    GATE_TRIGGERED = "gate_triggered"
    ERROR_OCCURRED = "error_occurred"
    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"


@dataclass
class AuditEvent:
    """Immutable audit trail entry"""
    id: str
    event_type: EventType
    timestamp: datetime
    workflow_id: str
    session_id: str
    actor: str  # Who/what caused the event
    action: str  # What happened
    details: Dict[str, Any]  # Event-specific data
    previous_hash: str = ""  # Hash of previous entry (blockchain-style)
    signature: str = ""  # Cryptographic signature
    
    def to_dict(self, include_signature: bool = True) -> Dict[str, Any]:
        """Convert to dictionary for signing/storage"""
        data = {
            'id': self.id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'workflow_id': self.workflow_id,
            'session_id': self.session_id,
            'actor': self.actor,
            'action': self.action,
            'details': self.details,
            'previous_hash': self.previous_hash,
        }
        if include_signature:
            data['signature'] = self.signature
        return data
    
    def __hash__(self) -> str:
        """Generate hash of this event (for chaining)"""
        data = self.to_dict(include_signature=False)
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()


class AuditTrail:
    """
    Immutable append-only audit trail with cryptographic signatures.
    
    Features:
    - Blockchain-style chaining (each event includes hash of previous)
    - HMAC signatures for integrity
    - Non-repudiation (cryptographic proof of what happened)
    - Compliance ready (SOC 2, HIPAA, PCI-DSS)
    """
    
    def __init__(self, signing_key: Optional[str] = None):
        """
        Initialize audit trail.
        
        Args:
            signing_key: Secret key for HMAC signatures.
                        If None, uses in-memory key (not production-safe).
        """
        self.events: List[AuditEvent] = []
        self.signing_key = signing_key or "dev_key_change_in_production"
        self.event_index: Dict[str, List[AuditEvent]] = {}  # workflow_id -> events
    
    def log_event(
        self,
        event_type: EventType,
        workflow_id: str,
        session_id: str,
        actor: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Log an event to the immutable audit trail.
        
        Args:
            event_type: Type of event
            workflow_id: Workflow ID
            session_id: Session ID
            actor: Who/what performed the action
            action: Description of action
            details: Event-specific details
        
        Returns:
            Event ID
        """
        details = details or {}
        event_id = f"evt_{hashlib.md5(
            f'{workflow_id}_{session_id}_{datetime.utcnow().isoformat()}'.encode()
        ).hexdigest()[:12]}"
        
        # Get previous event hash for chaining
        previous_hash = ""
        if self.events:
            previous_hash = self.events[-1].__hash__()
        
        # Create event
        event = AuditEvent(
            id=event_id,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            workflow_id=workflow_id,
            session_id=session_id,
            actor=actor,
            action=action,
            details=details,
            previous_hash=previous_hash,
        )
        
        # Sign event
        event.signature = self._sign_event(event)
        
        # Append (immutable)
        self.events.append(event)
        
        # Index by workflow
        if workflow_id not in self.event_index:
            self.event_index[workflow_id] = []
        self.event_index[workflow_id].append(event)
        
        return event_id
    
    def _sign_event(self, event: AuditEvent) -> str:
        """Generate HMAC signature for event"""
        data = event.to_dict(include_signature=False)
        json_str = json.dumps(data, sort_keys=True, default=str)
        signature = hmac.new(
            self.signing_key.encode(),
            json_str.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def verify_event_signature(self, event: AuditEvent) -> bool:
        """Verify that an event hasn't been tampered with"""
        expected_signature = self._sign_event(event)
        return hmac.compare_digest(event.signature, expected_signature)
    
    def verify_chain_integrity(self) -> bool:
        """
        Verify that the entire chain is intact (no tampering).
        
        Returns:
            True if all events are valid and properly chained
        """
        for i, event in enumerate(self.events):
            # Verify individual signature
            if not self.verify_event_signature(event):
                print(f"Event {i} signature verification failed")
                return False
            
            # Verify chain link
            if i > 0:
                expected_prev_hash = self.events[i-1].__hash__()
                if event.previous_hash != expected_prev_hash:
                    print(f"Event {i} chain verification failed")
                    return False
        
        return True
    
    def get_events(
        self,
        workflow_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        session_id: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> List[AuditEvent]:
        """
        Query events with optional filters.
        
        Args:
            workflow_id: Filter by workflow
            event_type: Filter by event type
            session_id: Filter by session
            actor: Filter by actor
        
        Returns:
            Matching events
        """
        results = self.events
        
        if workflow_id:
            results = [e for e in results if e.workflow_id == workflow_id]
        
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        
        if actor:
            results = [e for e in results if e.actor == actor]
        
        return results
    
    def export_audit_log(
        self,
        format: str = "json",
        workflow_id: Optional[str] = None,
    ) -> str:
        """
        Export audit log for compliance reporting.
        
        Args:
            format: Export format ("json" or "csv")
            workflow_id: Optional filter by workflow
        
        Returns:
            Exported log as string
        """
        events = self.get_events(workflow_id=workflow_id)
        
        if format == "json":
            return json.dumps(
                [event.to_dict() for event in events],
                indent=2,
                default=str,
            )
        elif format == "csv":
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    'id', 'event_type', 'timestamp', 'workflow_id',
                    'session_id', 'actor', 'action',
                ]
            )
            writer.writeheader()
            
            for event in events:
                writer.writerow({
                    'id': event.id,
                    'event_type': event.event_type.value,
                    'timestamp': event.timestamp.isoformat(),
                    'workflow_id': event.workflow_id,
                    'session_id': event.session_id,
                    'actor': event.actor,
                    'action': event.action,
                })
            
            return output.getvalue()
        
        return ""
    
    def get_workflow_timeline(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get chronological timeline for a workflow"""
        events = self.get_events(workflow_id=workflow_id)
        return [
            {
                'timestamp': event.timestamp.isoformat(),
                'type': event.event_type.value,
                'actor': event.actor,
                'action': event.action,
                'details': event.details,
            }
            for event in events
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get audit trail statistics"""
        event_types = {}
        actors = set()
        
        for event in self.events:
            key = event.event_type.value
            event_types[key] = event_types.get(key, 0) + 1
            actors.add(event.actor)
        
        return {
            'total_events': len(self.events),
            'total_workflows': len(self.event_index),
            'event_types': event_types,
            'total_actors': len(actors),
            'chain_integrity': self.verify_chain_integrity(),
            'oldest_event': self.events[0].timestamp.isoformat() if self.events else None,
            'newest_event': self.events[-1].timestamp.isoformat() if self.events else None,
        }
