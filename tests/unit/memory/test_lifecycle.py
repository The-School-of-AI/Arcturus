from datetime import datetime, timedelta

from memory.lifecycle import (
    LifecycleConfig,
    compute_importance,
    initialize_payload,
    update_payload_on_access,
)


class TestLifecycleScoring:
    def test_compute_importance_recency_and_frequency(self):
        now = datetime(2025, 1, 1)
        cfg = LifecycleConfig(recency_half_life_days=10.0, freq_normalization_cap=10)

        # Very recent, low frequency -> medium importance
        created = (now - timedelta(days=1)).isoformat()
        last = now.isoformat()
        score_recent = compute_importance(created, last, access_count=1, config=cfg, now=now)
        assert 0.2 <= score_recent <= 1.0

        # Old, never accessed -> very low importance
        created_old = (now - timedelta(days=365)).isoformat()
        last_old = created_old
        score_old = compute_importance(created_old, last_old, access_count=0, config=cfg, now=now)
        assert 0.0 <= score_old < 0.2

        # Frequently accessed and recent -> higher importance than recent/low frequency
        score_hot = compute_importance(created, last, access_count=20, config=cfg, now=now)
        assert score_hot > score_recent


class TestLifecyclePayload:
    def test_initialize_payload_sets_defaults(self):
        now = datetime(2025, 1, 1)
        payload: dict = {"text": "hello world"}

        initialize_payload(payload, now=now)

        assert payload["access_count"] == 0
        assert "created_at" in payload  # created_at should be present from qdrant_store.add
        assert "last_accessed_at" in payload
        assert payload["importance"] >= 0.0
        assert payload["archived"] is False

    def test_update_payload_on_access_increments_and_updates(self):
        now = datetime(2025, 1, 10)
        created = (now - timedelta(days=5)).isoformat()
        payload = {
            "created_at": created,
            "last_accessed_at": created,
            "access_count": 1,
            "importance": 0.3,
            "archived": False,
        }

        updates = update_payload_on_access(payload, now=now)

        assert updates["access_count"] == 2
        assert updates["last_accessed_at"].startswith(now.isoformat()[:19])
        assert 0.0 <= updates["importance"] <= 1.0
        # Should remain unarchived for a fairly recent, used memory
        assert updates["archived"] is False

