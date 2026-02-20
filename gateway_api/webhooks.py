from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.state import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data" / "gateway"
WEBHOOK_SUBSCRIPTIONS_FILE = DATA_DIR / "webhook_subscriptions.json"
WEBHOOK_DELIVERIES_FILE = DATA_DIR / "webhook_deliveries.jsonl"
WEBHOOK_DLQ_FILE = DATA_DIR / "webhook_dlq.jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: Any) -> None:
    _ensure_parent(path)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _make_signature(secret: str, timestamp: str, body: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


class WebhookService:
    def __init__(self, subscriptions_file: Path = WEBHOOK_SUBSCRIPTIONS_FILE):
        self.subscriptions_file = subscriptions_file
        self._lock = asyncio.Lock()

    async def list_subscriptions(self) -> List[Dict[str, Any]]:
        async with self._lock:
            payload = _read_json(self.subscriptions_file, {"subscriptions": []})
            return payload.get("subscriptions", [])

    async def create_subscription(
        self,
        target_url: str,
        event_types: List[str],
        secret: Optional[str] = None,
        active: bool = True,
    ) -> Dict[str, Any]:
        subscription = {
            "id": f"wh_{secrets.token_hex(6)}",
            "target_url": target_url,
            "event_types": event_types,
            "secret": secret or secrets.token_hex(16),
            "active": active,
            "created_at": _utc_now_iso(),
        }

        async with self._lock:
            payload = _read_json(self.subscriptions_file, {"subscriptions": []})
            payload.setdefault("subscriptions", []).append(subscription)
            _write_json(self.subscriptions_file, payload)

        return subscription

    async def delete_subscription(self, subscription_id: str) -> bool:
        async with self._lock:
            payload = _read_json(self.subscriptions_file, {"subscriptions": []})
            before = len(payload.get("subscriptions", []))
            payload["subscriptions"] = [
                item
                for item in payload.get("subscriptions", [])
                if item.get("id") != subscription_id
            ]
            after = len(payload["subscriptions"])
            if after == before:
                return False
            _write_json(self.subscriptions_file, payload)
            return True

    async def trigger_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        subscriptions = await self.list_subscriptions()
        matching = [
            subscription
            for subscription in subscriptions
            if subscription.get("active")
            and event_type in subscription.get("event_types", [])
        ]

        now = _utc_now_iso()
        body = json.dumps(payload, sort_keys=True)
        queued = 0

        async with self._lock:
            for subscription in matching:
                queued += 1
                delivery = {
                    "timestamp": now,
                    "delivery_id": f"wd_{secrets.token_hex(8)}",
                    "subscription_id": subscription["id"],
                    "target_url": subscription["target_url"],
                    "event_type": event_type,
                    "payload": payload,
                    "signature": _make_signature(subscription["secret"], now, body),
                    "status": "queued",
                    "attempt": 0,
                    "note": "Contract-only webhook skeleton. Delivery worker not implemented yet.",
                }
                _append_jsonl(WEBHOOK_DELIVERIES_FILE, delivery)

        return {"status": "queued", "queued_deliveries": queued}


_webhook_service: Optional[WebhookService] = None


def get_webhook_service() -> WebhookService:
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService()
    return _webhook_service
