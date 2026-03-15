"""
P11 Phase 4 Sync Engine — LWW (last-writer-wins) merge logic.

For memories and spaces: compare (updated_at, device_id). Winner overwrites.
"""

from datetime import datetime
from typing import Any


def _parse_iso(s: str) -> datetime:
    """Parse ISO8601 string; return epoch on failure."""
    from datetime import timezone
    if not s:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        # Handle cases like Z or +00:00
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            # Assume UTC if naive
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def lww_wins(
    local_updated_at: str,
    local_device_id: str,
    remote_updated_at: str,
    remote_device_id: str,
) -> bool:
    """
    Return True if local wins (should keep local), False if remote wins.
    Compare updated_at; tiebreak by device_id (lexicographic).
    """
    lt = _parse_iso(local_updated_at or "")
    rt = _parse_iso(remote_updated_at or "")
    if lt > rt:
        return True
    if lt < rt:
        return False
    return (local_device_id or "") >= (remote_device_id or "")


def merge_memory_change(
    local: dict[str, Any] | None,
    remote: dict[str, Any],
) -> dict[str, Any]:
    """
    LWW merge for memory. Remote overwrites local if remote wins.
    Returns the winning record (full payload for apply).
    """
    if local is None:
        return remote
    l_ts = local.get("updated_at", "")
    l_dev = local.get("device_id", "")
    r_ts = remote.get("updated_at", "")
    r_dev = remote.get("device_id", "")
    if lww_wins(l_ts, l_dev, r_ts, r_dev):
        return local
    return remote


def merge_space_change(
    local: dict[str, Any] | None,
    remote: dict[str, Any],
) -> dict[str, Any]:
    """LWW merge for space metadata."""
    return merge_memory_change(local, remote)
