import asyncio
from pathlib import Path

from gateway_api.key_store import GatewayKeyStore
from gateway_api.webhooks import WebhookService


def _find_corrupt_copy(path: Path) -> list[Path]:
    return list(path.parent.glob(f"{path.stem}*.corrupt.*"))


def test_key_store_recovers_from_corrupt_json_without_crash(tmp_path):
    keys_file = tmp_path / "api_keys.json"
    keys_file.write_text("{not-json", encoding="utf-8")

    store = GatewayKeyStore(keys_file=keys_file, audit_file=tmp_path / "audit.jsonl")
    keys = asyncio.run(store.list_keys())

    assert keys == []
    assert _find_corrupt_copy(keys_file)


def test_webhook_service_recovers_from_corrupt_jsonl_without_losing_valid_rows(tmp_path):
    deliveries_file = tmp_path / "webhook_deliveries.jsonl"
    deliveries_file.write_text(
        '{"delivery_id":"d1","status":"queued","timestamp":"t","updated_at":"t"}\n'
        'not-json-line\n',
        encoding="utf-8",
    )

    service = WebhookService(
        subscriptions_file=tmp_path / "subs.json",
        deliveries_file=deliveries_file,
        dlq_file=tmp_path / "dlq.jsonl",
    )

    rows = asyncio.run(service.list_deliveries(limit=10))
    assert len(rows) == 1
    assert rows[0]["delivery_id"] == "d1"

    assert _find_corrupt_copy(deliveries_file)
    rewritten = deliveries_file.read_text(encoding="utf-8")
    assert "d1" in rewritten
    assert "not-json-line" not in rewritten
