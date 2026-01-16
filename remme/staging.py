"""
REMME Staging Store - Temporary storage for extracted preferences before normalization.

The staging queue holds raw extracted preferences until the normalizer processes them.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class StagingStore:
    """
    Staging queue for raw extracted preferences.
    
    Stores preferences in a simple JSON file until they're
    normalized and applied to hubs by the normalizer.
    """
    
    DEFAULT_PATH = "memory/remme_staging.json"
    BATCH_THRESHOLD = 10  # Run normalizer after this many items
    
    def __init__(self, path: Optional[Path] = None):
        if path:
            self.path = Path(path)
        else:
            self.path = Path(__file__).parent.parent / self.DEFAULT_PATH
        
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Load staging data from disk."""
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception as e:
                print(f"⚠️ Failed to load staging store: {e}")
        return {
            "pending": [],
            "last_normalized": None
        }
    
    def save(self):
        """Save staging data to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, default=str))
    
    def add(self, raw_preferences: Dict, source: str = "unknown"):
        """
        Add raw extracted preferences to staging queue.
        
        Args:
            raw_preferences: Dict of preference key-value pairs (any format)
            source: Source identifier (e.g., "session_123", "manual", "notes")
        """
        if not raw_preferences:
            return
        
        entry = {
            "raw": raw_preferences,
            "source": source,
            "timestamp": datetime.now().isoformat()
        }
        
        self.data["pending"].append(entry)
        self.save()
        
        print(f"📥 Staged {len(raw_preferences)} raw preferences from {source}")
    
    def get_pending(self) -> List[Dict]:
        """Get all pending entries."""
        return self.data["pending"]
    
    def get_pending_count(self) -> int:
        """Get count of pending entries."""
        return len(self.data["pending"])
    
    def should_normalize(self) -> bool:
        """Check if normalizer should run based on thresholds."""
        # Threshold: batch size
        if len(self.data["pending"]) >= self.BATCH_THRESHOLD:
            return True
        
        # Threshold: time since last normalization (6 hours)
        if self.data["last_normalized"]:
            try:
                last = datetime.fromisoformat(self.data["last_normalized"])
                hours_elapsed = (datetime.now() - last).total_seconds() / 3600
                if hours_elapsed >= 6 and len(self.data["pending"]) > 0:
                    return True
            except:
                pass
        
        return False
    
    def clear_pending(self):
        """Clear pending entries after normalization."""
        self.data["pending"] = []
        self.data["last_normalized"] = datetime.now().isoformat()
        self.save()
        print("🧹 Cleared staging queue")
    
    def get_all_raw_values(self) -> Dict[str, List[Any]]:
        """
        Aggregate all raw values by key for normalization.
        
        Returns:
            Dict mapping raw keys to list of values with metadata
        """
        aggregated = {}
        
        for entry in self.data["pending"]:
            raw = entry.get("raw", {})
            source = entry.get("source", "unknown")
            timestamp = entry.get("timestamp")
            
            for key, value in raw.items():
                if key not in aggregated:
                    aggregated[key] = []
                aggregated[key].append({
                    "value": value,
                    "source": source,
                    "timestamp": timestamp
                })
        
        return aggregated


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_staging: Optional[StagingStore] = None


def get_staging_store() -> StagingStore:
    """Get or create the global StagingStore instance."""
    global _staging
    if _staging is None:
        _staging = StagingStore()
    return _staging
