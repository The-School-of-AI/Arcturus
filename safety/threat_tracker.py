"""
Session-based threat tracking for prompt injection attempts.

Tracks injection attempts per session/user and implements progressive blocking:
- Warn: First attempt
- Rate limit: Multiple attempts
- Block: Repeated attempts
"""
import time
from collections import defaultdict
from threading import Lock
from typing import Dict, Any, List, Optional
from datetime import datetime


class ThreatLevel:
    """Threat level enumeration."""
    SAFE = "safe"
    WARN = "warn"
    RATE_LIMIT = "rate_limit"
    BLOCK = "block"


class ThreatTracker:
    """
    Tracks injection attempts per session/user with progressive blocking.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize threat tracker.
        
        Config options:
        - warn_threshold: Number of attempts before warning (default: 1)
        - rate_limit_threshold: Number of attempts before rate limiting (default: 3)
        - block_threshold: Number of attempts before blocking (default: 5)
        - window_seconds: Time window for tracking attempts (default: 300 = 5 minutes)
        - block_duration_seconds: How long to block after threshold (default: 3600 = 1 hour)
        """
        self.config = config or {}
        self.warn_threshold = self.config.get("warn_threshold", 1)
        self.rate_limit_threshold = self.config.get("rate_limit_threshold", 3)
        self.block_threshold = self.config.get("block_threshold", 5)
        self.window_seconds = self.config.get("window_seconds", 300)  # 5 minutes
        self.block_duration_seconds = self.config.get("block_duration_seconds", 3600)  # 1 hour
        
        # Store: {session_id: [(timestamp, pattern_detected, user_id), ...]}
        self._attempts: Dict[str, List[tuple]] = defaultdict(list)
        # Store blocked sessions: {session_id: block_until_timestamp}
        self._blocked: Dict[str, float] = {}
        self._lock = Lock()
    
    def record_attempt(
        self,
        session_id: str,
        pattern_detected: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record an injection attempt.
        
        Args:
            session_id: Session identifier
            pattern_detected: Type of pattern detected (e.g., "injection_pattern", "jailbreak")
            user_id: Optional user identifier
            
        Returns:
            Dict with threat assessment:
            - threat_level: "safe", "warn", "rate_limit", or "block"
            - attempt_count: Number of attempts in current window
            - blocked_until: Timestamp if blocked, None otherwise
            - action: Recommended action
        """
        now = time.time()
        
        with self._lock:
            # Check if session is currently blocked
            if session_id in self._blocked:
                block_until = self._blocked[session_id]
                if now < block_until:
                    return {
                        "threat_level": ThreatLevel.BLOCK,
                        "attempt_count": len(self._attempts.get(session_id, [])),
                        "blocked_until": block_until,
                        "action": "block",
                        "message": f"Session blocked until {datetime.fromtimestamp(block_until).isoformat()}"
                    }
                else:
                    # Block expired, remove it
                    del self._blocked[session_id]
            
            # Clean old attempts outside the window
            attempts = self._attempts[session_id]
            cutoff_time = now - self.window_seconds
            attempts[:] = [(ts, pat, uid) for ts, pat, uid in attempts if ts > cutoff_time]
            
            # Record new attempt
            attempts.append((now, pattern_detected, user_id))
            attempt_count = len(attempts)
            
            # Determine threat level
            threat_level = ThreatLevel.SAFE
            action = "allow"
            
            if attempt_count >= self.block_threshold:
                threat_level = ThreatLevel.BLOCK
                action = "block"
                # Block the session
                self._blocked[session_id] = now + self.block_duration_seconds
            elif attempt_count >= self.rate_limit_threshold:
                threat_level = ThreatLevel.RATE_LIMIT
                action = "rate_limit"
            elif attempt_count >= self.warn_threshold:
                threat_level = ThreatLevel.WARN
                action = "warn"
            
            return {
                "threat_level": threat_level,
                "attempt_count": attempt_count,
                "blocked_until": self._blocked.get(session_id),
                "action": action,
                "patterns_detected": list(set([pat for _, pat, _ in attempts])),
                "window_start": cutoff_time
            }
    
    def get_threat_level(self, session_id: str) -> Dict[str, Any]:
        """
        Get current threat level for a session without recording a new attempt.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dict with current threat assessment
        """
        now = time.time()
        
        with self._lock:
            # Check if blocked
            if session_id in self._blocked:
                block_until = self._blocked[session_id]
                if now < block_until:
                    return {
                        "threat_level": ThreatLevel.BLOCK,
                        "attempt_count": len(self._attempts.get(session_id, [])),
                        "blocked_until": block_until,
                        "action": "block"
                    }
                else:
                    del self._blocked[session_id]
            
            # Count attempts in window
            attempts = self._attempts.get(session_id, [])
            cutoff_time = now - self.window_seconds
            recent_attempts = [a for a in attempts if a[0] > cutoff_time]
            attempt_count = len(recent_attempts)
            
            threat_level = ThreatLevel.SAFE
            action = "allow"
            
            if attempt_count >= self.block_threshold:
                threat_level = ThreatLevel.BLOCK
                action = "block"
            elif attempt_count >= self.rate_limit_threshold:
                threat_level = ThreatLevel.RATE_LIMIT
                action = "rate_limit"
            elif attempt_count >= self.warn_threshold:
                threat_level = ThreatLevel.WARN
                action = "warn"
            
            return {
                "threat_level": threat_level,
                "attempt_count": attempt_count,
                "action": action,
                "patterns_detected": list(set([pat for _, pat, _ in recent_attempts]))
            }
    
    def clear_session(self, session_id: str):
        """Clear all tracking data for a session."""
        with self._lock:
            if session_id in self._attempts:
                del self._attempts[session_id]
            if session_id in self._blocked:
                del self._blocked[session_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        with self._lock:
            total_sessions = len(self._attempts)
            total_blocked = len(self._blocked)
            total_attempts = sum(len(attempts) for attempts in self._attempts.values())
            
            return {
                "total_sessions_tracked": total_sessions,
                "total_blocked_sessions": total_blocked,
                "total_attempts_recorded": total_attempts,
                "blocked_sessions": list(self._blocked.keys())
            }


# Global instance
_threat_tracker = ThreatTracker()


def get_threat_tracker(config: Dict[str, Any] = None) -> ThreatTracker:
    """Get or create global threat tracker instance."""
    global _threat_tracker
    if config is not None:
        _threat_tracker = ThreatTracker(config)
    return _threat_tracker
