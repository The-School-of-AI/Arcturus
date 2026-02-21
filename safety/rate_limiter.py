"""Simple in-memory per-key rate limiter skeleton."""
import time
from collections import defaultdict
from threading import Lock


class SimpleRateLimiter:
    def __init__(self):
        self._store = defaultdict(lambda: (0, 0))
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = int(time.time())
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