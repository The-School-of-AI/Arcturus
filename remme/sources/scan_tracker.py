"""
Scan Tracker - Tracks which sources have been scanned.

Prevents re-scanning the same files by tracking modification times.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class ScanTracker:
    """
    Tracks scanned sources to avoid duplicates.
    
    Uses file modification time to detect changes.
    """
    
    DEFAULT_PATH = "memory/remme_scanned_sources.json"
    
    def __init__(self, path: Optional[Path] = None):
        if path:
            self.path = Path(path)
        else:
            self.path = Path(__file__).parent.parent.parent / self.DEFAULT_PATH
        
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Load tracking data from disk."""
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception as e:
                print(f"⚠️ Failed to load scan tracker: {e}")
        return {
            "notes": {},
            "sessions": {},
            "last_full_scan": None
        }
    
    def save(self):
        """Save tracking data to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, default=str))
    
    def is_scanned(self, source_type: str, file_path: Path) -> bool:
        """
        Check if a file has already been scanned.
        
        Returns True if file exists in tracker AND hasn't been modified.
        """
        rel_path = str(file_path.name)  # Use filename as key
        
        if source_type not in self.data:
            return False
        
        if rel_path not in self.data[source_type]:
            return False
        
        # Check if file has been modified since last scan
        try:
            current_mtime = file_path.stat().st_mtime
            tracked_mtime = self.data[source_type][rel_path].get("mtime", 0)
            
            # If modification time is the same, file hasn't changed
            return abs(current_mtime - tracked_mtime) < 1  # 1 second tolerance
        except:
            return False
    
    def mark_scanned(self, source_type: str, file_path: Path):
        """Mark a file as scanned."""
        if source_type not in self.data:
            self.data[source_type] = {}
        
        rel_path = str(file_path.name)
        
        try:
            mtime = file_path.stat().st_mtime
        except:
            mtime = 0
        
        self.data[source_type][rel_path] = {
            "mtime": mtime,
            "scanned_at": datetime.now().isoformat()
        }
    
    def get_unscanned_files(self, source_type: str, files: list) -> list:
        """
        Filter list of files to only unscanned/modified ones.
        
        Args:
            source_type: "notes" or "sessions"
            files: List of Path objects
        
        Returns:
            List of files that need scanning
        """
        unscanned = []
        for f in files:
            if not self.is_scanned(source_type, f):
                unscanned.append(f)
        return unscanned
    
    def clear(self, source_type: str = None):
        """Clear tracking data (for full rescan)."""
        if source_type:
            self.data[source_type] = {}
        else:
            self.data = {"notes": {}, "sessions": {}, "last_full_scan": None}
        self.save()
    
    def get_stats(self) -> Dict:
        """Get tracking statistics."""
        return {
            "notes_tracked": len(self.data.get("notes", {})),
            "sessions_tracked": len(self.data.get("sessions", {})),
            "last_full_scan": self.data.get("last_full_scan")
        }


# Singleton
_tracker: Optional[ScanTracker] = None


def get_scan_tracker() -> ScanTracker:
    """Get or create the global ScanTracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = ScanTracker()
    return _tracker
