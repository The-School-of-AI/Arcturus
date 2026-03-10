import asyncio

from gateway_api.idempotency import IdempotencyStore, derive_inbound_idempotency_key


def test_idempotency_store_created_replay_and_conflict(tmp_path):
    store = IdempotencyStore(records_file=tmp_path / "idempotency.json")

    created = asyncio.run(
        store.start_request(
            actor="gwk_test",
            method="POST",
            path="/api/v1/pages/generate",
            idempotency_key="idem-1",
            payload={"query": "alpha"},
        )
    )
    assert created.outcome == "created"

    asyncio.run(
        store.finalize(
            actor="gwk_test",
            method="POST",
            path="/api/v1/pages/generate",
            idempotency_key="idem-1",
            state="completed",
            status_code=200,
            response_body={"status": "ok"},
            response_headers={"x-test": "1"},
        )
    )

    replay = asyncio.run(
        store.start_request(
            actor="gwk_test",
            method="POST",
            path="/api/v1/pages/generate",
            idempotency_key="idem-1",
            payload={"query": "alpha"},
        )
    )
    assert replay.outcome == "replayed"
    assert replay.record["status_code"] == 200

    conflict = asyncio.run(
        store.start_request(
            actor="gwk_test",
            method="POST",
            path="/api/v1/pages/generate",
            idempotency_key="idem-1",
            payload={"query": "beta"},
        )
    )
    assert conflict.outcome == "conflict"


def test_idempotency_store_in_progress_and_ttl_expiry(tmp_path):
    store = IdempotencyStore(records_file=tmp_path / "idempotency.json", ttl_seconds=3600)

    first = asyncio.run(
        store.start_request(
            actor="gwk_test",
            method="POST",
            path="/api/v1/webhooks/dispatch",
            idempotency_key="idem-2",
            payload={"limit": 10},
        )
    )
    assert first.outcome == "created"

    second = asyncio.run(
        store.start_request(
            actor="gwk_test",
            method="POST",
            path="/api/v1/webhooks/dispatch",
            idempotency_key="idem-2",
            payload={"limit": 10},
        )
    )
    assert second.outcome == "in_progress"

    expiring_store = IdempotencyStore(records_file=tmp_path / "idempotency_expire.json", ttl_seconds=0)
    created = asyncio.run(
        expiring_store.start_request(
            actor="gwk_test",
            method="POST",
            path="/api/v1/cron/jobs",
            idempotency_key="idem-3",
            payload={"name": "daily"},
        )
    )
    assert created.outcome == "created"

    recreated = asyncio.run(
        expiring_store.start_request(
            actor="gwk_test",
            method="POST",
            path="/api/v1/cron/jobs",
            idempotency_key="idem-3",
            payload={"name": "daily"},
        )
    )
    assert recreated.outcome == "created"


def test_derive_inbound_idempotency_key_is_stable_and_sensitive():
    key_a1 = derive_inbound_idempotency_key(
        source="github",
        signature_header="sha256=abc",
        timestamp_header="1700000000",
        raw_body='{"event_type":"task.complete"}',
    )
    key_a2 = derive_inbound_idempotency_key(
        source="github",
        signature_header="sha256=abc",
        timestamp_header="1700000000",
        raw_body='{"event_type":"task.complete"}',
    )
    key_b = derive_inbound_idempotency_key(
        source="github",
        signature_header="sha256=different",
        timestamp_header="1700000000",
        raw_body='{"event_type":"task.complete"}',
    )
    key_c = derive_inbound_idempotency_key(
        source="github",
        signature_header="sha256=different",
        timestamp_header="1700000000",
        raw_body='{"event_type":"task.error"}',
    )

    assert key_a1 == key_a2
    assert key_a1 == key_b
    assert key_a1 != key_c
