"""Enhanced rate limiter with per-user/per-operation limits and persistent storage support."""
import time
import os
import json
from collections import defaultdict
from threading import Lock
from typing import Dict, Any, Optional
from pathlib import Path


class SimpleRateLimiter:
    """
    Enhanced rate limiter with:
    - Per-user and per-operation rate limits
    - Persistent storage option (file-based or Redis)
    - Configurable limits per operation type
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize rate limiter.
        
        Config options:
        - persistent_storage: "file" or "redis" or None (default: None, in-memory)
        - storage_path: Path for file storage (default: "logs/rate_limits.json")
        - redis_url: Redis connection URL (if using Redis)
        - default_limits: Dict of default limits per operation type
        """
        self.config = config or {}
        self._store = defaultdict(lambda: (0, 0))
        self._lock = Lock()
        
        # Operation-specific limits: {operation_type: (limit, window_seconds)}
        self._operation_limits = self.config.get("default_limits", {
            "default": (60, 60),  # 60 requests per 60 seconds
            "sensitive": (10, 60),  # 10 requests per 60 seconds for sensitive operations
            "tool_call": (30, 60),  # 30 tool calls per 60 seconds
            "input_scan": (100, 60),  # 100 scans per 60 seconds
        })
        
        # Persistent storage
        self._persistent = self.config.get("persistent_storage")
        self._storage_path = Path(self.config.get("storage_path", "logs/rate_limits.json"))
        self._redis_client = None
        
        if self._persistent == "file":
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_file()
        elif self._persistent == "redis":
            self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis client if available."""
        try:
            import redis
            redis_url = self.config.get("redis_url", "redis://localhost:6379")
            self._redis_client = redis.from_url(redis_url)
            # Test connection
            self._redis_client.ping()
        except ImportError:
            # Redis not installed, fall back to in-memory
            self._persistent = None
        except Exception as e:
            # Redis connection failed, fall back to in-memory
            self._persistent = None
    
    def _load_from_file(self):
        """Load rate limit state from file."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path, 'r') as f:
                    data = json.load(f)
                    for key, (start, count) in data.items():
                        self._store[key] = (start, count)
            except Exception:
                # File corrupted or invalid, start fresh
                pass
    
    def _save_to_file(self):
        """Save rate limit state to file."""
        try:
            with open(self._storage_path, 'w') as f:
                json.dump(dict(self._store), f)
        except Exception:
            # Save failed, continue with in-memory only
            pass
    
    def _get_redis_key(self, key: str) -> str:
        """Get Redis key for rate limit tracking."""
        return f"rate_limit:{key}"
    
    def allow(
        self,
        key: str,
        limit: Optional[int] = None,
        window_seconds: int = 60,
        operation_type: str = "default"
    ) -> bool:
        """
        Check if request should be allowed.
        
        Args:
            key: Rate limit key (e.g., user_id, session_id)
            limit: Override limit (if None, uses operation_type default)
            window_seconds: Override window (if None, uses operation_type default)
            operation_type: Type of operation ("default", "sensitive", "tool_call", etc.)
            
        Returns:
            True if allowed, False if rate limited
        """
        # Get limits for operation type
        if limit is None or window_seconds == 60:
            op_limit, op_window = self._operation_limits.get(
                operation_type,
                self._operation_limits["default"]
            )
            if limit is None:
                limit = op_limit
            if window_seconds == 60:  # Only use default if not explicitly set
                window_seconds = op_window
        
        now = int(time.time())
        
        # Use Redis if available
        if self._persistent == "redis" and self._redis_client:
            return self._allow_redis(key, limit, window_seconds, now)
        
        # Use in-memory or file storage
        with self._lock:
            start, count = self._store.get(key, (now, 0))
            
            # Reset window if expired
            if now - start >= window_seconds:
                self._store[key] = (now, 1)
                if self._persistent == "file":
                    self._save_to_file()
                return True
            else:
                if count + 1 <= limit:
                    self._store[key] = (start, count + 1)
                    if self._persistent == "file":
                        self._save_to_file()
                    return True
                else:
                    return False
    
    def _allow_redis(self, key: str, limit: int, window_seconds: int, now: int) -> bool:
        """Rate limit check using Redis."""
        redis_key = self._get_redis_key(key)
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = self._redis_client.pipeline()
            pipe.get(redis_key)
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds)
            results = pipe.execute()
            
            current_count = int(results[0] or 0)
            
            if current_count >= limit:
                return False
            
            # Increment was already done in pipeline
            return True
        except Exception:
            # Redis failed, fall back to in-memory
            return self._allow_memory_fallback(key, limit, window_seconds, now)
    
    def _allow_memory_fallback(self, key: str, limit: int, window_seconds: int, now: int) -> bool:
        """Fallback to in-memory if Redis fails."""
        with self._lock:
            start, count = self._store.get(key, (now, 0))
            if now - start >= window_seconds:
                self._store[key] = (now, 1)
                return True
            else:
                if count + 1 <= limit:
                    self._store[key] = (start, count + 1)
                    return True
                else:
                    return False
    
    def get_remaining(self, key: str, operation_type: str = "default") -> Dict[str, Any]:
        """
        Get remaining requests for a key.
        
        Returns:
            Dict with remaining count, limit, window info
        """
        limit, window_seconds = self._operation_limits.get(
            operation_type,
            self._operation_limits["default"]
        )
        
        now = int(time.time())
        
        with self._lock:
            start, count = self._store.get(key, (now, 0))
            
            if now - start >= window_seconds:
                remaining = limit
                reset_at = now + window_seconds
            else:
                remaining = max(0, limit - count)
                reset_at = start + window_seconds
            
            return {
                "remaining": remaining,
                "limit": limit,
                "window_seconds": window_seconds,
                "reset_at": reset_at
            }
    
    def reset(self, key: str):
        """Reset rate limit for a key."""
        with self._lock:
            if key in self._store:
                del self._store[key]
            if self._persistent == "file":
                self._save_to_file()
            elif self._persistent == "redis" and self._redis_client:
                try:
                    self._redis_client.delete(self._get_redis_key(key))
                except Exception:
                    pass