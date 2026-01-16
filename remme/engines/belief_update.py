"""
BeliefUpdateEngine - Confidence and decay calculations for UserModel.

Manages how beliefs change over time:
- Confidence updates based on evidence
- Recency-based decay
- Conflict resolution between beliefs
"""

import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from remme.schemas.hub_schemas import (
    BeliefUpdateEngineSchema,
    ConfidenceConfig,
    RecencyDecayConfig,
    HubConfig,
)


class BeliefUpdateEngine:
    """
    Engine for updating beliefs with confidence and decay.
    
    Provides methods for:
    - Calculating confidence updates from new evidence
    - Applying recency decay to beliefs
    - Resolving conflicts between beliefs
    """
    
    DEFAULT_PATH = "memory/user_model/belief_engine_config.json"
    
    def __init__(self, path: Optional[Path] = None):
        if path:
            self.path = Path(path)
        else:
            self.path = Path(__file__).parent.parent.parent / self.DEFAULT_PATH
        
        self.config: BeliefUpdateEngineSchema = self._load()
    
    def _load(self) -> BeliefUpdateEngineSchema:
        """Load engine config from disk."""
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text())
                return BeliefUpdateEngineSchema(**raw)
            except Exception as e:
                print(f"⚠️ Failed to load BeliefUpdateEngine config: {e}")
        return BeliefUpdateEngineSchema()
    
    def save(self):
        """Save engine config to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.config.model_dump_json(indent=2))
        print(f"💾 Saved BeliefUpdateEngine config")
    
    def get_hub_config(self, hub_name: str) -> HubConfig:
        """Get configuration for a specific hub."""
        if hub_name in self.config.per_hub_config:
            return self.config.per_hub_config[hub_name]
        # Return default config
        return HubConfig()
    
    # =========================================================================
    # CONFIDENCE UPDATES
    # =========================================================================
    
    def calculate_confidence_update(
        self,
        hub_name: str,
        current_confidence: float,
        is_reinforcement: bool = True,
        evidence_strength: str = "medium"
    ) -> float:
        """
        Calculate new confidence after an evidence update.
        
        Args:
            hub_name: Name of the hub being updated
            current_confidence: Current confidence value (0-1)
            is_reinforcement: True if evidence supports the belief, False if contradicts
            evidence_strength: strong|medium|weak
        
        Returns:
            New confidence value
        """
        hub_config = self.get_hub_config(hub_name)
        conf_config = hub_config.confidence
        
        # Strength multiplier
        strength_mult = {"strong": 1.5, "medium": 1.0, "weak": 0.5}.get(evidence_strength, 1.0)
        
        if is_reinforcement:
            # Asymptotic increase: new = old + (cap - old) * increment * strength
            increment = conf_config.increment_per_evidence * strength_mult
            new_conf = current_confidence + (conf_config.cap - current_confidence) * increment
        else:
            # Contradiction: direct decrement
            decrement = conf_config.decrement_on_contradiction * strength_mult
            new_conf = current_confidence - decrement
        
        # Clamp to [floor, cap]
        new_conf = max(conf_config.floor, min(conf_config.cap, new_conf))
        
        return new_conf
    
    def get_base_confidence(self, hub_name: str) -> float:
        """Get base confidence for a new belief in a hub."""
        hub_config = self.get_hub_config(hub_name)
        return hub_config.confidence.base
    
    # =========================================================================
    # RECENCY DECAY
    # =========================================================================
    
    def calculate_decay(
        self,
        hub_name: str,
        current_confidence: float,
        last_updated: datetime,
        priority: str = "soft"
    ) -> float:
        """
        Calculate decayed confidence based on time since last update.
        
        Uses exponential decay with half-life from config.
        
        Args:
            hub_name: Name of the hub
            current_confidence: Current confidence value
            last_updated: When the belief was last updated
            priority: Priority level of the belief (hard beliefs may be immune)
        
        Returns:
            Decayed confidence value
        """
        hub_config = self.get_hub_config(hub_name)
        decay_config = hub_config.recency_decay
        
        # Check if decay is enabled
        if not decay_config.enabled:
            return current_confidence
        
        # Check if this priority is excluded from decay
        if priority in decay_config.exclude_priorities:
            return current_confidence
        
        # Calculate days since update
        days_elapsed = (datetime.now() - last_updated).total_seconds() / 86400
        
        # Apply exponential decay: conf * (0.5 ^ (days / half_life))
        half_life = decay_config.half_life_days
        decay_factor = math.pow(0.5, days_elapsed / half_life)
        decayed_conf = current_confidence * decay_factor
        
        # Ensure minimum
        minimum = decay_config.minimum_after_decay
        decayed_conf = max(minimum, decayed_conf)
        
        return decayed_conf
    
    def should_decay(self, hub_name: str, last_updated: datetime) -> bool:
        """Check if a belief should be decayed (has significant time elapsed)."""
        hub_config = self.get_hub_config(hub_name)
        half_life = hub_config.recency_decay.half_life_days
        
        days_elapsed = (datetime.now() - last_updated).total_seconds() / 86400
        
        # Consider decay significant if more than 10% of half-life has passed
        return days_elapsed > (half_life * 0.1)
    
    # =========================================================================
    # CONFLICT RESOLUTION
    # =========================================================================
    
    def resolve_conflict(
        self,
        belief_a: Dict[str, Any],
        belief_b: Dict[str, Any]
    ) -> str:
        """
        Resolve conflict between two beliefs.
        
        Returns 'a', 'b', or 'both' (if they can coexist as scoped variants).
        
        Each belief should have:
        - priority: hard|soft|situational
        - scope: the scope/domain of the belief
        - timestamp: when the belief was created/updated
        - confidence: current confidence value
        """
        order = self.config.global_rules.conflict_resolution_order
        
        for criterion in order:
            if criterion == "prefer_higher_priority":
                priority_rank = {"hard": 3, "soft": 2, "situational": 1}
                rank_a = priority_rank.get(belief_a.get("priority", "soft"), 2)
                rank_b = priority_rank.get(belief_b.get("priority", "soft"), 2)
                if rank_a > rank_b:
                    return "a"
                elif rank_b > rank_a:
                    return "b"
            
            elif criterion == "prefer_more_specific_scope":
                scope_a = belief_a.get("scope", "global")
                scope_b = belief_b.get("scope", "global")
                scope_rank = self.config.scope_hierarchy.levels
                try:
                    idx_a = scope_rank.index(scope_a) if scope_a in scope_rank else -1
                    idx_b = scope_rank.index(scope_b) if scope_b in scope_rank else -1
                    if idx_a > idx_b:  # Higher index = more specific
                        return "a"
                    elif idx_b > idx_a:
                        return "b"
                except ValueError:
                    pass
            
            elif criterion == "prefer_more_recent":
                ts_a = belief_a.get("timestamp")
                ts_b = belief_b.get("timestamp")
                if ts_a and ts_b:
                    if ts_a > ts_b:
                        return "a"
                    elif ts_b > ts_a:
                        return "b"
            
            elif criterion == "prefer_higher_confidence":
                conf_a = belief_a.get("confidence", 0)
                conf_b = belief_b.get("confidence", 0)
                if conf_a > conf_b:
                    return "a"
                elif conf_b > conf_a:
                    return "b"
        
        # If still tied, check if we can keep both as scoped variants
        scope_a = belief_a.get("scope", "global")
        scope_b = belief_b.get("scope", "global")
        if scope_a != scope_b:
            return "both"
        
        # Default: prefer more recent
        return "b"
    
    # =========================================================================
    # EVIDENCE THRESHOLDS
    # =========================================================================
    
    def get_confidence_level(
        self,
        hub_name: str,
        evidence_count: int
    ) -> str:
        """
        Get the confidence level label based on evidence count.
        
        Returns: tentative|established|confident
        """
        hub_config = self.get_hub_config(hub_name)
        thresholds = hub_config.evidence_thresholds
        
        if evidence_count >= thresholds.confident:
            return "confident"
        elif evidence_count >= thresholds.established:
            return "established"
        else:
            return "tentative"
    
    def to_dict(self) -> Dict[str, Any]:
        """Return engine config as dictionary."""
        return self.config.model_dump()


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_engine: Optional[BeliefUpdateEngine] = None


def get_belief_engine() -> BeliefUpdateEngine:
    """Get or create the global BeliefUpdateEngine instance."""
    global _engine
    if _engine is None:
        _engine = BeliefUpdateEngine()
    return _engine
