"""
TG4 — Sync API. Add memory, trigger sync, verify push/pull.
"""

import pytest

pytestmark = [
    pytest.mark.p11_automation,
    pytest.mark.integration,
]

from tests.automation.p11_mnemo.conftest import requires_qdrant_neo4j


@requires_qdrant_neo4j
def test_tg4_01_sync_trigger_after_add(client):
    """TG4: Add memory, trigger sync (push+pull). Skips if sync server unreachable."""
    add_res = client.post(
        "/api/remme/add",
        json={"text": "Sync test memory", "category": "general"},
    )
    assert add_res.status_code == 200

    res = client.post("/api/sync/trigger")
    if res.status_code == 503:
        pytest.skip("Sync engine not enabled")
    assert res.status_code == 200, res.text
    body = res.json()
    assert "push" in body
    assert "pull" in body
    # Push may fail (Connection refused) when sync server not running; treat as skip
    if not body["push"].get("accepted", True) and any("Connection refused" in e for e in body["push"].get("errors", [])):
        pytest.skip("Sync server not reachable (SYNC_SERVER_URL)")


@requires_qdrant_neo4j
def test_tg4_02_sync_pull(client):
    """TG4: Pull changes returns 200 and cursor."""
    from tests.automation.p11_mnemo.conftest import AUTH_HEADERS
    user_id = AUTH_HEADERS.get("X-User-Id", "00000000-0000-0000-0000-000000000001")
    res = client.post(
        "/api/sync/pull",
        json={"user_id": user_id, "device_id": "test-device", "since_cursor": "0"},
    )
    if res.status_code == 503:
        pytest.skip("Sync engine not enabled")
    assert res.status_code == 200, res.text
    body = res.json()
    assert "cursor" in body
    assert "changes" in body
    assert isinstance(body["changes"], list)
