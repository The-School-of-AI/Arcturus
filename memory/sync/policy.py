"""
P11 Phase 4 Sync Engine — per-space sync policy.

Resolves sync_policy for space_id; filters entities for push/pull.
Global space (SPACE_ID_GLOBAL) always syncs. Non-global: check Space.sync_policy.
"""

from typing import Callable

from memory.space_constants import (
    SPACE_ID_GLOBAL,
    SYNC_POLICY_SYNC,
    SYNC_POLICY_LOCAL_ONLY,
    SYNC_POLICY_SHARED,
)

# Policies that allow push/pull (shared spaces sync so they can be shared with others)
_SYNCABLE_POLICIES = (SYNC_POLICY_SYNC, SYNC_POLICY_SHARED)


def should_sync_space(
    space_id: str | None,
    get_policy: Callable[[str], str] | None = None,
) -> bool:
    """
    Return True if content in this space should be synced (push/pull).
    Global space always syncs. Otherwise use get_policy(space_id); sync and shared both sync.
    """
    if not space_id or space_id == SPACE_ID_GLOBAL:
        return True
    if get_policy:
        policy = get_policy(space_id)
        return policy in _SYNCABLE_POLICIES
    return True  # default: sync


def filter_spaces_for_sync(
    spaces: list[dict],
    *,
    sync_only: bool = True,
) -> list[dict]:
    """
    Filter space list to those with sync_policy in (sync, shared), or all if sync_only=False.
    """
    if not sync_only:
        return spaces
    return [
        s
        for s in spaces
        if s.get("sync_policy", SYNC_POLICY_SYNC) in _SYNCABLE_POLICIES
    ]
