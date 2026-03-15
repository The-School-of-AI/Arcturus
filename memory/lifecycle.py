from __future__ import annotations

"""
Lifecycle manager for memories.

Phase 5 goals (initial implementation):
- Track basic usage metrics for memories (access count, last_accessed_at).
- Maintain an importance score derived from recency and frequency.
- Support archival via a simple threshold so low-importance memories can be
  excluded from active retrieval (but remain in the store).

This module is intentionally backend-agnostic: it operates on a generic
VectorStore-like interface (`get`, `update`) and plain payload dictionaries.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from typing import Any, Dict, Iterable, Optional, Sequence

from core.utils import log_error


ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"


@dataclass
class LifecycleConfig:
    """Tunable knobs for importance scoring and archival."""

    # Half-life for recency decay (in days)
    recency_half_life_days: float = 30.0
    # How many days of inactivity before a memory is eligible for archival
    archive_inactive_days: float = 180.0
    # Importance score below which a memory can be archived
    archive_importance_threshold: float = 0.1
    # Maximum access count considered for frequency normalization
    freq_normalization_cap: int = 50


DEFAULT_CONFIG = LifecycleConfig()


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    ts_str = str(ts)
    try:
        # Handle common ISO8601 forms; strip trailing Z if present
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1]
        # datetime.fromisoformat handles microseconds if present
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None


def _days_between(a: datetime, b: datetime) -> float:
    return (a - b).total_seconds() / 86400.0


def compute_importance(
    created_at: Optional[str],
    last_accessed_at: Optional[str],
    access_count: int,
    *,
    config: LifecycleConfig = DEFAULT_CONFIG,
    now: Optional[datetime] = None,
) -> float:
    """
    Compute a bounded importance score in [0, 1] based on:
    - How recently the memory was accessed (recency decay).
    - How frequently it has been accessed (log-scaled frequency).
    """
    now_dt = now or datetime.utcnow()
    created_dt = _parse_iso(created_at) or now_dt
    last_accessed_dt = _parse_iso(last_accessed_at) or created_dt

    # Recency: exponential decay based on days since last access.
    days_since_access = max(0.0, _days_between(now_dt, last_accessed_dt))
    if config.recency_half_life_days <= 0:
        recency_score = 1.0
    else:
        recency_score = 0.5 ** (days_since_access / config.recency_half_life_days)

    # Frequency: log-scaled access count, normalized to [0, 1].
    capped = max(0, min(access_count, config.freq_normalization_cap))
    if capped <= 0:
        freq_score = 0.0
    else:
        # log10(1) -> 0, log10(cap) -> 1
        denom = math.log10(config.freq_normalization_cap) if config.freq_normalization_cap > 1 else 1.0
        freq_score = min(1.0, math.log10(capped + 1) / denom)

    # Weighted combination. Recency has slightly higher weight so that very old
    # but frequently used memories still decay over time.
    importance = 0.6 * recency_score + 0.4 * freq_score
    if importance < 0.0:
        importance = 0.0
    if importance > 1.0:
        importance = 1.0
    return importance


def initialize_payload(payload: Dict[str, Any], *, now: Optional[datetime] = None) -> None:
    """
    Initialize lifecycle-related fields on a freshly created memory payload.
    This is idempotent: existing values are preserved.
    """
    now_dt = now or datetime.utcnow()
    now_iso = now_dt.isoformat()
    created_at = str(payload.get("created_at") or now_iso)
    if "created_at" not in payload:
        payload["created_at"] = created_at

    if "access_count" not in payload:
        payload["access_count"] = 0
    if "last_accessed_at" not in payload:
        payload["last_accessed_at"] = created_at
    if "importance" not in payload:
        payload["importance"] = compute_importance(
            created_at=created_at,
            last_accessed_at=payload.get("last_accessed_at"),
            access_count=int(payload.get("access_count") or 0),
            now=now_dt,
        )
    if "archived" not in payload:
        payload["archived"] = False


def _compute_archived_flag(
    created_at: Optional[str],
    last_accessed_at: Optional[str],
    importance: float,
    *,
    config: LifecycleConfig = DEFAULT_CONFIG,
    now: Optional[datetime] = None,
) -> bool:
    """
    Decide whether a memory should be marked archived, based on:
    - Very low importance.
    - Long inactivity window.

    This is intentionally conservative so we don't aggressively hide memories.
    """
    if importance >= config.archive_importance_threshold:
        return False

    now_dt = now or datetime.utcnow()
    last_accessed_dt = _parse_iso(last_accessed_at) or _parse_iso(created_at) or now_dt
    inactive_days = max(0.0, _days_between(now_dt, last_accessed_dt))

    return inactive_days >= config.archive_inactive_days


def update_payload_on_access(
    payload: Dict[str, Any],
    *,
    config: LifecycleConfig = DEFAULT_CONFIG,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Given an existing memory payload, return a dict of lifecycle fields that
    should be updated after an access (read in retrieval context).
    """
    now_dt = now or datetime.utcnow()
    now_iso = now_dt.isoformat()
    created_at = str(payload.get("created_at") or now_iso)

    try:
        prev_count = int(payload.get("access_count") or 0)
    except (TypeError, ValueError):
        prev_count = 0
    access_count = prev_count + 1

    last_accessed_at = payload.get("last_accessed_at") or created_at
    importance = compute_importance(
        created_at=created_at,
        last_accessed_at=now_iso,
        access_count=access_count,
        config=config,
        now=now_dt,
    )

    archived = bool(payload.get("archived") or False)
    if not archived:
        archived = _compute_archived_flag(
            created_at=created_at,
            last_accessed_at=last_accessed_at,
            importance=importance,
            config=config,
            now=now_dt,
        )

    return {
        "access_count": access_count,
        "last_accessed_at": now_iso,
        "importance": importance,
        "archived": archived,
    }


def _store_get_many(store: Any, ids: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """
    Helper to batch-fetch memories when the underlying store supports it.
    Mirrors the logic in memory_retriever for efficiency.
    """
    ids = [i for i in ids if i]
    if not store or not ids:
        return {}
    try:
        if hasattr(store, "get_many"):
            items = store.get_many(ids)
            if isinstance(items, dict):
                return items
            if isinstance(items, list):
                out: Dict[str, Dict[str, Any]] = {}
                for it in items:
                    if isinstance(it, dict) and it.get("id"):
                        out[it["id"]] = it
                return out
        if hasattr(store, "get_batch"):
            items = store.get_batch(ids)
            if isinstance(items, dict):
                return items
            if isinstance(items, list):
                out2: Dict[str, Dict[str, Any]] = {}
                for it in items:
                    if isinstance(it, dict) and it.get("id"):
                        out2[it["id"]] = it
                return out2
    except Exception:
        # Fall back below
        pass

    out3: Dict[str, Dict[str, Any]] = {}
    for mid in ids:
        try:
            m = store.get(mid)
            if m:
                out3[mid] = m
        except Exception:
            continue
    return out3


def record_access(store: Any, memory_ids: Iterable[str]) -> None:
    """
    Record access for the given memory ids:
    - Increment access_count.
    - Update last_accessed_at.
    - Recompute importance.
    - Optionally mark archived when very cold and low importance.

    Best-effort only: failures are logged but do not break the caller.
    """
    ids = [mid for mid in memory_ids if mid]
    if not store or not ids:
        return

    try:
        batch = _store_get_many(store, ids)
        for mid in ids:
            payload = batch.get(mid)
            if not payload:
                continue
            updates = update_payload_on_access(payload)
            try:
                store.update(mid, metadata=updates)
            except Exception as e:
                log_error(f"Lifecycle: failed to update lifecycle fields for memory {mid[:8]}: {e}")
    except Exception as e:
        log_error(f"Lifecycle: record_access failed: {e}")


