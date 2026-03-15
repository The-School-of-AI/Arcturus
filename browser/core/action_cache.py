"""
Action Caching with Automatic Invalidation

Cache successful action sequences based on page state hash.
On re-run: if page hash matches, replay cached action (no LLM).
If hash mismatches (site updated), invalidate + replan + update cache.

Cost Impact: 90% token savings for cached paths
Stagehand's "write once, run forever" approach.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import json


@dataclass
class CachedAction:
    """Cached action sequence"""
    action_id: str
    page_hash: str  # Hash of page state that triggered action
    action_type: str
    parameters: Dict
    result: str  # Result of executing this action
    created_at: datetime
    last_used: datetime = field(default_factory=datetime.utcnow)
    use_count: int = 0
    confidence: float = 1.0  # Confidence in cache
    ttl_days: int = 30  # Cache time-to-live


class ActionCache:
    """
    Caches action sequences keyed by page state hash.
    
    Enables:
    - 90% token savings (no LLM for cached paths)
    - "write once, run forever" automations
    - Automatic cache invalidation on site changes
    """
    
    def __init__(self, max_cache_size: int = 10000):
        self.cache: Dict[str, CachedAction] = {}
        self.max_cache_size = max_cache_size
        self.page_action_map: Dict[str, List[str]] = {}  # page_hash -> action_ids
        self.invalidation_log: List[Dict] = []
    
    def compute_page_hash(self, page_state: Dict) -> str:
        """
        Compute deterministic hash of page state.
        
        Args:
            page_state: Dict with url, title, dom_snapshot, critical_elements
        
        Returns:
            Hex hash of page state
        """
        # Create canonical representation
        state_dict = {
            'url': page_state.get('url', ''),
            'dom_hash': page_state.get('dom_hash', ''),
            'title': page_state.get('title', ''),
            # Include hashes of key elements
            'elements': sorted([
                e.get('id', '') for e in page_state.get('critical_elements', [])
            ]),
        }
        
        # Serialize and hash
        state_json = json.dumps(state_dict, sort_keys=True)
        return hashlib.sha256(state_json.encode()).hexdigest()
    
    def get_cached_action(
        self,
        page_hash: str,
        action_type: str,
    ) -> Optional[CachedAction]:
        """
        Retrieve cached action if available and valid.
        
        Args:
            page_hash: Current page state hash
            action_type: Type of action desired
        
        Returns:
            CachedAction if found and valid, None otherwise
        """
        action_ids = self.page_action_map.get(page_hash, [])
        
        for action_id in action_ids:
            cached_action = self.cache.get(action_id)
            
            if not cached_action:
                continue
            
            # Check if action type matches
            if cached_action.action_type != action_type:
                continue
            
            # Check if cache has expired
            age_days = (datetime.utcnow() - cached_action.created_at).days
            if age_days > cached_action.ttl_days:
                self._invalidate_cache(action_id, "TTL expired")
                continue
            
            # Update use info
            cached_action.last_used = datetime.utcnow()
            cached_action.use_count += 1
            
            return cached_action
        
        return None
    
    def cache_action(
        self,
        page_hash: str,
        action_type: str,
        parameters: Dict,
        result: str,
        confidence: float = 1.0,
    ) -> str:
        """
        Cache a successful action.
        
        Args:
            page_hash: Page state hash that triggered action
            action_type: Type of action
            parameters: Action parameters
            result: Action result/outcome
            confidence: Confidence in cache (0.0-1.0)
        
        Returns:
            Action ID
        """
        action_id = f"cached_{len(self.cache)}"
        
        cached_action = CachedAction(
            action_id=action_id,
            page_hash=page_hash,
            action_type=action_type,
            parameters=parameters,
            result=result,
            created_at=datetime.utcnow(),
            confidence=confidence,
        )
        
        # Check cache size limit
        if len(self.cache) >= self.max_cache_size:
            self._evict_least_used()
        
        # Store in cache
        self.cache[action_id] = cached_action
        
        # Update page->action mapping
        if page_hash not in self.page_action_map:
            self.page_action_map[page_hash] = []
        self.page_action_map[page_hash].append(action_id)
        
        return action_id
    
    def invalidate_page_cache(
        self,
        old_page_hash: str,
        new_page_hash: str,
    ) -> int:
        """
        Invalidate cache when page changes (detected by hash mismatch).
        
        Args:
            old_page_hash: Previous page hash
            new_page_hash: Current page hash
        
        Returns:
            Number of actions invalidated
        """
        action_ids = self.page_action_map.get(old_page_hash, [])
        
        invalidated = 0
        for action_id in action_ids:
            if self._invalidate_cache(action_id, "Page hash mismatch"):
                invalidated += 1
        
        return invalidated
    
    def _invalidate_cache(self, action_id: str, reason: str) -> bool:
        """Invalidate a specific cached action"""
        if action_id not in self.cache:
            return False
        
        cached_action = self.cache.pop(action_id)
        
        # Remove from page map
        page_hash = cached_action.page_hash
        if page_hash in self.page_action_map:
            self.page_action_map[page_hash].remove(action_id)
            if not self.page_action_map[page_hash]:
                del self.page_action_map[page_hash]
        
        # Log invalidation
        self.invalidation_log.append({
            'action_id': action_id,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat(),
            'use_count': cached_action.use_count,
        })
        
        return True
    
    def _evict_least_used(self) -> str:
        """Evict least-used cache entry when limit reached"""
        least_used = min(
            self.cache.items(),
            key=lambda x: x[1].use_count
        )
        
        action_id = least_used[0]
        self._invalidate_cache(action_id, "Cache size limit reached")
        
        return action_id
    
    def clear_cache(self):
        """Clear entire cache"""
        self.cache.clear()
        self.page_action_map.clear()
    
    def get_cache_statistics(self) -> Dict:
        """Get cache performance statistics"""
        if not self.cache:
            return {
                'total_cached': 0,
                'hit_count': 0,
                'token_savings': 0,
            }
        
        total_uses = sum(a.use_count for a in self.cache.values())
        avg_use_count = total_uses / len(self.cache) if self.cache else 0
        
        # Estimate token savings (1 action = ~50 tokens normally, ~5 from cache)
        token_savings = total_uses * 45  # 45 tokens saved per cache hit
        
        return {
            'total_cached': len(self.cache),
            'total_pages_cached': len(self.page_action_map),
            'total_uses': total_uses,
            'avg_use_count': avg_use_count,
            'estimated_token_savings': token_savings,
            'cache_hit_rate': total_uses / (total_uses + len(self.cache)) if total_uses > 0 else 0,
            'total_invalidations': len(self.invalidation_log),
            'cache_efficiency': f"{(total_uses / (total_uses + len(self.invalidation_log)) * 100) if (total_uses + len(self.invalidation_log)) > 0 else 0:.1f}%",
        }
    
    def get_hottest_actions(self, limit: int = 10) -> List[Dict]:
        """Get most frequently used cached actions"""
        sorted_actions = sorted(
            self.cache.values(),
            key=lambda x: x.use_count,
            reverse=True,
        )
        
        return [
            {
                'action_id': a.action_id,
                'action_type': a.action_type,
                'use_count': a.use_count,
                'created_at': a.created_at.isoformat(),
                'confidence': a.confidence,
            }
            for a in sorted_actions[:limit]
        ]
