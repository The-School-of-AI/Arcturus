"""
In-memory LLM response cache with LRU eviction.

When the ``semantic_cache`` feature flag is enabled, identical prompts sent to
the same model are served from this cache instead of hitting the LLM provider.
"""

import hashlib
import logging
import threading
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger("watchtower.semantic_cache")

_DEFAULT_MAX_ENTRIES = 128


class LLMResponseCache:
    """Thread-safe, in-memory LRU cache for LLM responses.

    Keyed by ``(prompt_hash, model_key)`` so identical prompts to different
    models are cached separately.
    """

    def __init__(self, max_entries: int = _DEFAULT_MAX_ENTRIES):
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._store: OrderedDict[str, str] = OrderedDict()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(prompt: str, model_key: str, cache_key: Optional[str] = None) -> str:
        base = (cache_key if cache_key is not None else prompt).encode("utf-8")
        prompt_hash = hashlib.sha256(base).hexdigest()[:16]
        return f"{model_key}:{prompt_hash}"

    def get(self, prompt: str, model_key: str, cache_key: Optional[str] = None) -> Optional[str]:
        """Return cached response or ``None`` on miss. Use cache_key for invariant lookup when prompt varies by run_id etc."""
        key = self._make_key(prompt, model_key, cache_key)
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._hits += 1
                logger.debug("Cache HIT for model=%s", model_key)
                return self._store[key]
            self._misses += 1
            return None

    def put(self, prompt: str, model_key: str, response: str, cache_key: Optional[str] = None) -> None:
        """Store a response, evicting the oldest entry if at capacity."""
        key = self._make_key(prompt, model_key, cache_key)
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = response
            if len(self._store) > self._max_entries:
                self._store.popitem(last=False)

    def clear(self) -> int:
        """Flush all entries. Returns the number of entries removed."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            self._hits = 0
            self._misses = 0
        logger.info("Semantic cache cleared (%d entries)", count)
        return count

    def stats(self) -> dict:
        """Return cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "entries": len(self._store),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 4) if total > 0 else 0,
            }


llm_cache = LLMResponseCache()
