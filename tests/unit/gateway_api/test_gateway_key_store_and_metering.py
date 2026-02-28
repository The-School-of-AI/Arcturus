import asyncio
from datetime import datetime, timezone

from gateway_api.key_store import GatewayKeyStore
from gateway_api.metering import GatewayMeteringStore


def test_key_store_create_rotate_revoke_persists_json_and_audit(tmp_path):
    keys_file = tmp_path / "api_keys.json"
    audit_file = tmp_path / "key_audit.jsonl"
    store = GatewayKeyStore(keys_file=keys_file, audit_file=audit_file)

    record, plaintext = asyncio.run(
        store.create_key(
            name="Test Key",
            scopes=["search:read"],
            rpm_limit=120,
            burst_limit=60,
        )
    )
    assert record["key_id"].startswith("gwk_")
    assert plaintext.startswith("arc_")

    validated = asyncio.run(store.validate_api_key(plaintext))
    assert validated is not None
    assert validated["key_id"] == record["key_id"]

    rotated_record, rotated_plaintext = asyncio.run(store.rotate_key(record["key_id"]))
    assert rotated_record is not None
    assert rotated_plaintext is not None
    assert asyncio.run(store.validate_api_key(plaintext)) is None
    assert asyncio.run(store.validate_api_key(rotated_plaintext)) is not None

    revoked = asyncio.run(store.revoke_key(record["key_id"]))
    assert revoked is not None
    assert revoked["status"] == "revoked"
    assert asyncio.run(store.validate_api_key(rotated_plaintext)) is None

    assert keys_file.exists()
    assert audit_file.exists()
    assert len(audit_file.read_text(encoding="utf-8").strip().splitlines()) >= 3


def test_metering_writes_event_and_rollup(tmp_path):
    events_file = tmp_path / "metering_events.jsonl"
    metering = GatewayMeteringStore(events_file=events_file, data_dir=tmp_path)

    asyncio.run(
        metering.record(
            key_id="gwk_test",
            method="POST",
            path="/api/v1/search",
            status_code=200,
            latency_ms=12.5,
            units=1,
        )
    )

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    rollup_file = tmp_path / f"metering_rollup_{month}.json"

    assert events_file.exists()
    assert rollup_file.exists()

    usage = asyncio.run(metering.get_usage_for_key("gwk_test", month))
    assert usage["requests"] == 1
    assert usage["status_counts"]["200"] == 1
    assert usage["endpoints"]["POST /api/v1/search"] == 1
