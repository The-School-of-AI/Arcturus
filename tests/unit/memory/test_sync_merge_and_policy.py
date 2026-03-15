"""Unit tests for P11 Phase 4 Sync Engine: merge (LWW) and policy."""

import pytest

from memory.space_constants import SPACE_ID_GLOBAL, SYNC_POLICY_LOCAL_ONLY, SYNC_POLICY_SYNC
from memory.sync.merge import lww_wins, merge_memory_change, merge_space_change
from memory.sync.policy import filter_spaces_for_sync, should_sync_space


class TestLwwWins:
    """lww_wins(local_ts, local_dev, remote_ts, remote_dev) -> True if local wins."""

    def test_local_newer_wins(self):
        assert lww_wins("2025-03-10T12:00:00", "dev-a", "2025-03-10T11:00:00", "dev-b") is True

    def test_remote_newer_wins(self):
        assert lww_wins("2025-03-10T11:00:00", "dev-a", "2025-03-10T12:00:00", "dev-b") is False

    def test_same_time_tiebreak_by_device_id(self):
        # Lexicographic: "b" >= "a" -> local (b) wins
        assert lww_wins("2025-03-10T12:00:00", "dev-b", "2025-03-10T12:00:00", "dev-a") is True
        assert lww_wins("2025-03-10T12:00:00", "dev-a", "2025-03-10T12:00:00", "dev-b") is False

    def test_same_time_same_device_local_wins(self):
        # >= so equal -> True (keep local)
        assert lww_wins("2025-03-10T12:00:00", "dev-a", "2025-03-10T12:00:00", "dev-a") is True

    def test_empty_timestamps_treated_as_epoch(self):
        assert lww_wins("", "", "2025-03-10T12:00:00", "dev-b") is False
        assert lww_wins("2025-03-10T12:00:00", "dev-a", "", "") is True


class TestMergeMemoryChange:
    """merge_memory_change(local, remote) returns winning record."""

    def test_none_local_returns_remote(self):
        remote = {"memory_id": "m1", "text": "hi", "updated_at": "2025-03-10T12:00:00", "device_id": "d1"}
        assert merge_memory_change(None, remote) is remote

    def test_local_wins_when_newer(self):
        local = {"memory_id": "m1", "text": "local", "updated_at": "2025-03-10T13:00:00", "device_id": "d1"}
        remote = {"memory_id": "m1", "text": "remote", "updated_at": "2025-03-10T12:00:00", "device_id": "d2"}
        assert merge_memory_change(local, remote) == local

    def test_remote_wins_when_newer(self):
        local = {"memory_id": "m1", "text": "local", "updated_at": "2025-03-10T12:00:00", "device_id": "d1"}
        remote = {"memory_id": "m1", "text": "remote", "updated_at": "2025-03-10T13:00:00", "device_id": "d2"}
        assert merge_memory_change(local, remote) == remote

    def test_tiebreak_by_device_id(self):
        local = {"memory_id": "m1", "text": "local", "updated_at": "2025-03-10T12:00:00", "device_id": "dev-z"}
        remote = {"memory_id": "m1", "text": "remote", "updated_at": "2025-03-10T12:00:00", "device_id": "dev-a"}
        assert merge_memory_change(local, remote) == local


class TestMergeSpaceChange:
    """merge_space_change delegates to merge_memory_change."""

    def test_none_local_returns_remote(self):
        remote = {"space_id": "s1", "name": "R", "updated_at": "2025-03-10T12:00:00", "device_id": "d1"}
        assert merge_space_change(None, remote) is remote

    def test_remote_wins_when_newer(self):
        local = {"space_id": "s1", "name": "L", "updated_at": "2025-03-10T12:00:00", "device_id": "d1"}
        remote = {"space_id": "s1", "name": "R", "updated_at": "2025-03-10T13:00:00", "device_id": "d2"}
        assert merge_space_change(local, remote) == remote


class TestShouldSyncSpace:
    """should_sync_space(space_id, get_policy) -> True if content should sync."""

    def test_none_or_global_always_syncs(self):
        assert should_sync_space(None) is True
        assert should_sync_space("") is True
        assert should_sync_space(SPACE_ID_GLOBAL) is True

    def test_with_policy_sync_returns_true(self):
        assert should_sync_space("space-1", get_policy=lambda _: SYNC_POLICY_SYNC) is True

    def test_with_policy_local_only_returns_false(self):
        assert should_sync_space("space-1", get_policy=lambda _: SYNC_POLICY_LOCAL_ONLY) is False

    def test_no_get_policy_defaults_to_sync(self):
        assert should_sync_space("space-1") is True

    def test_get_policy_called_with_space_id(self):
        seen = []

        def capture(sid):
            seen.append(sid)
            return SYNC_POLICY_SYNC

        assert should_sync_space("my-space-id", get_policy=capture) is True
        assert seen == ["my-space-id"]


class TestFilterSpacesForSync:
    """filter_spaces_for_sync(spaces, sync_only=...) filters by sync_policy."""

    def test_sync_only_true_keeps_only_sync(self):
        spaces = [
            {"space_id": "s1", "sync_policy": SYNC_POLICY_SYNC},
            {"space_id": "s2", "sync_policy": SYNC_POLICY_LOCAL_ONLY},
            {"space_id": "s3"},  # default sync
        ]
        out = filter_spaces_for_sync(spaces, sync_only=True)
        assert len(out) == 2
        assert out[0]["space_id"] == "s1"
        assert out[1]["space_id"] == "s3"

    def test_sync_only_false_returns_all(self):
        spaces = [
            {"space_id": "s1", "sync_policy": SYNC_POLICY_SYNC},
            {"space_id": "s2", "sync_policy": SYNC_POLICY_LOCAL_ONLY},
        ]
        out = filter_spaces_for_sync(spaces, sync_only=False)
        assert len(out) == 2

    def test_empty_list(self):
        assert filter_spaces_for_sync([], sync_only=True) == []
        assert filter_spaces_for_sync([], sync_only=False) == []
