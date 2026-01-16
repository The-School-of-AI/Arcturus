"""
EvidenceLog - Append-only audit trail of signals.

Tracks what signals created or modified beliefs in the UserModel hubs.
Provides traceability for debugging and preventing hallucinated personalization.
"""

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from remme.schemas.hub_schemas import (
    EvidenceLogSchema,
    EvidenceEvent,
    EvidenceSource,
    SignalType,
    DerivedUpdate,
    SignalTypeTaxonomy,
)


class EvidenceLog:
    """
    Append-only log of evidence events.
    
    Tracks signals from various sources (conversations, notes, browser, etc.)
    that create or modify beliefs in the UserModel hubs.
    """
    
    DEFAULT_PATH = "memory/user_model/evidence_log.json"
    
    def __init__(self, path: Optional[Path] = None):
        if path:
            self.path = Path(path)
        else:
            self.path = Path(__file__).parent.parent.parent / self.DEFAULT_PATH
        
        self.data: EvidenceLogSchema = self._load()
        self._init_taxonomy()
    
    def _load(self) -> EvidenceLogSchema:
        """Load evidence log from disk."""
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text())
                return EvidenceLogSchema(**raw)
            except Exception as e:
                print(f"⚠️ Failed to load EvidenceLog: {e}")
        return EvidenceLogSchema()
    
    def _init_taxonomy(self):
        """Initialize signal type taxonomy if empty."""
        if not self.data.signal_type_taxonomy:
            self.data.signal_type_taxonomy = {
                "explicit_preference": SignalTypeTaxonomy(
                    description="User directly states preference",
                    indicators=["don't", "never", "always", "prefer", "I like", "I hate"],
                    base_confidence=0.5,
                    decay_rate="slow"
                ),
                "implicit_behavior": SignalTypeTaxonomy(
                    description="Inferred from repeated patterns",
                    indicators=["repeated_format", "consistent_choices"],
                    base_confidence=0.3,
                    decay_rate="medium"
                ),
                "correction": SignalTypeTaxonomy(
                    description="User corrects assistant behavior",
                    indicators=["no", "wrong", "that's not what I", "I meant"],
                    base_confidence=0.6,
                    decay_rate="slow"
                ),
                "rejection": SignalTypeTaxonomy(
                    description="User explicitly rejects output",
                    indicators=["I hate when you", "stop doing", "never do this"],
                    base_confidence=0.7,
                    decay_rate="very_slow"
                ),
                "acceptance": SignalTypeTaxonomy(
                    description="User accepts/praises output",
                    indicators=["perfect", "exactly", "this is what I wanted"],
                    base_confidence=0.4,
                    decay_rate="medium"
                ),
                "context_signal": SignalTypeTaxonomy(
                    description="Environmental/system observations",
                    indicators=["I'm using", "my setup is", "I'm on"],
                    base_confidence=0.5,
                    decay_rate="medium"
                ),
                "system_observation": SignalTypeTaxonomy(
                    description="Auto-detected from system/files",
                    indicators=[],
                    base_confidence=0.8,
                    decay_rate="slow"
                )
            }
    
    def save(self):
        """Save evidence log to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.data.model_dump_json(indent=2))
        print(f"💾 Saved EvidenceLog ({len(self.data.events)} events)")
    
    def add_event(
        self,
        source_type: str,
        source_reference: str,
        signal_category: str,
        raw_excerpt: str,
        derived_updates: List[Dict[str, Any]] = None,
        signal_strength: str = "medium",
        confidence_impact: float = 0.1,
        decay_group: str = "recency_sensitive"
    ) -> EvidenceEvent:
        """
        Add a new evidence event to the log.
        
        Args:
            source_type: conversation|notes|browser|project|system|news|manual
            source_reference: session_id, file_path, or url
            signal_category: Type of signal (explicit_preference, correction, etc.)
            raw_excerpt: Minimal text that triggered this (truncated if too long)
            derived_updates: List of hub updates this evidence triggered
            signal_strength: strong|medium|weak
            confidence_impact: How much this affects confidence
            decay_group: stable|recency_sensitive|fast_decay
        
        Returns:
            The created EvidenceEvent
        """
        # Truncate excerpt if too long
        max_length = self.data.retention_policy.max_excerpt_length
        if len(raw_excerpt) > max_length:
            raw_excerpt = raw_excerpt[:max_length] + "..."
        
        # Create hash for deduplication
        excerpt_hash = hashlib.sha256(raw_excerpt.encode()).hexdigest()[:16]
        
        # Check for duplicate
        if self._is_duplicate(excerpt_hash):
            print(f"⏭️ Skipping duplicate evidence: {raw_excerpt[:50]}...")
            return None
        
        # Build derived updates
        updates = []
        for u in (derived_updates or []):
            updates.append(DerivedUpdate(**u))
        
        event = EvidenceEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(),
            source=EvidenceSource(
                type=source_type,
                reference=source_reference
            ),
            signal_type=SignalType(
                category=signal_category,
                strength=signal_strength
            ),
            raw_excerpt=raw_excerpt,
            excerpt_hash=excerpt_hash,
            derived_updates=updates,
            confidence_impact=confidence_impact,
            decay_group=decay_group
        )
        
        self.data.events.append(event)
        self._update_meta(event)
        self._prune_if_needed()
        
        print(f"📝 Added evidence event: {signal_category} from {source_type}")
        return event
    
    def _is_duplicate(self, excerpt_hash: str) -> bool:
        """Check if an event with this hash already exists."""
        for event in self.data.events[-100:]:  # Check recent events
            if event.excerpt_hash == excerpt_hash:
                return True
        return False
    
    def _update_meta(self, event: EvidenceEvent):
        """Update metadata after adding an event."""
        self.data.meta.total_events = len(self.data.events)
        
        # Update by source
        source_type = event.source.type
        if source_type not in self.data.meta.events_by_source:
            self.data.meta.events_by_source[source_type] = 0
        self.data.meta.events_by_source[source_type] += 1
        
        # Update by type
        signal_cat = event.signal_type.category
        if signal_cat not in self.data.meta.events_by_type:
            self.data.meta.events_by_type[signal_cat] = 0
        self.data.meta.events_by_type[signal_cat] += 1
    
    def _prune_if_needed(self):
        """Prune old events if we exceed the limit."""
        max_events = self.data.retention_policy.max_events
        if len(self.data.events) > max_events:
            # Prune based on strategy
            if self.data.retention_policy.prune_strategy == "oldest_first":
                self.data.events = self.data.events[-max_events:]
            else:
                # Sort by confidence impact and remove lowest
                self.data.events.sort(key=lambda e: e.confidence_impact, reverse=True)
                self.data.events = self.data.events[:max_events]
            
            self.data.meta.last_pruned_at = datetime.now()
            print(f"🧹 Pruned evidence log to {max_events} events")
    
    def get_recent(self, count: int = 50) -> List[EvidenceEvent]:
        """Get the most recent events."""
        return self.data.events[-count:]
    
    def get_by_source(self, source_type: str) -> List[EvidenceEvent]:
        """Get events from a specific source type."""
        return [e for e in self.data.events if e.source.type == source_type]
    
    def get_by_hub(self, hub_name: str) -> List[EvidenceEvent]:
        """Get events that affected a specific hub."""
        result = []
        for event in self.data.events:
            for update in event.derived_updates:
                if update.target_hub == hub_name:
                    result.append(event)
                    break
        return result
    
    def get_confidence_for_path(self, hub_name: str, path: str) -> Dict[str, Any]:
        """
        Get confidence information for a specific hub path.
        
        Returns evidence count, last update, and confidence based on
        evidence patterns.
        """
        matching_events = []
        for event in self.data.events:
            for update in event.derived_updates:
                if update.target_hub == hub_name and update.target_path == path:
                    matching_events.append(event)
        
        if not matching_events:
            return {"evidence_count": 0, "confidence": 0.0, "last_update": None}
        
        return {
            "evidence_count": len(matching_events),
            "confidence": min(0.95, 0.3 + 0.1 * len(matching_events)),
            "last_update": matching_events[-1].timestamp.isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Return evidence log as dictionary."""
        return self.data.model_dump()


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_log: Optional[EvidenceLog] = None


def get_evidence_log() -> EvidenceLog:
    """Get or create the global EvidenceLog instance."""
    global _log
    if _log is None:
        _log = EvidenceLog()
    return _log
