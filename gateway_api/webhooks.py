from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from shared.state import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data" / "gateway"
WEBHOOK_SUBSCRIPTIONS_FILE = DATA_DIR / "webhook_subscriptions.json"
WEBHOOK_DELIVERIES_FILE = DATA_DIR / "webhook_deliveries.jsonl"
WEBHOOK_DLQ_FILE = DATA_DIR / "webhook_dlq.jsonl"
WEBHOOK_SIGNING_SECRET_ENV = "ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET"
DEFAULT_TIMESTAMP_TOLERANCE_SECONDS = 300


class WebhookSigningNotConfigured(RuntimeError):
    """Raised when inbound signature validation is requested without a configured secret."""


class InvalidWebhookSignature(RuntimeError):
    """Raised when provided webhook signature is invalid."""


class StaleWebhookTimestamp(RuntimeError):
    """Raised when webhook timestamp is out of the accepted tolerance window."""


class WebhookDeliveryError(RuntimeError):
    """Raised for delivery lifecycle errors (not-found, invalid state, etc.)."""


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


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _make_signature(secret: str, timestamp: str, body: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def _signing_secret() -> str | None:
    value = os.getenv(WEBHOOK_SIGNING_SECRET_ENV)
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned


def _latest_delivery_states(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    state: Dict[str, Dict[str, Any]] = {}
    for event in events:
        delivery_id = event.get("delivery_id")
        if not delivery_id:
            continue
        state[delivery_id] = event
    return state


class WebhookService:
    def __init__(
        self,
        subscriptions_file: Path = WEBHOOK_SUBSCRIPTIONS_FILE,
        deliveries_file: Path = WEBHOOK_DELIVERIES_FILE,
        dlq_file: Path = WEBHOOK_DLQ_FILE,
    ):
        self.subscriptions_file = subscriptions_file
        self.deliveries_file = deliveries_file
        self.dlq_file = dlq_file
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

    def validate_inbound_signature(
        self,
        signature_header: str | None,
        timestamp_header: str | None,
        raw_body: str,
        tolerance_seconds: int = DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
    ) -> None:
        secret = _signing_secret()
        if not secret:
            raise WebhookSigningNotConfigured(
                f"{WEBHOOK_SIGNING_SECRET_ENV} is not configured"
            )

        if not signature_header or not timestamp_header:
            raise InvalidWebhookSignature("Missing signature headers")

        try:
            timestamp = int(timestamp_header)
        except ValueError as exc:
            raise InvalidWebhookSignature("Invalid timestamp header") from exc

        now = int(time.time())
        if abs(now - timestamp) > tolerance_seconds:
            raise StaleWebhookTimestamp("Webhook timestamp is outside the allowed window")

        expected = _make_signature(secret, str(timestamp), raw_body)
        if not hmac.compare_digest(signature_header.strip(), expected):
            raise InvalidWebhookSignature("Signature verification failed")

    async def trigger_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        source: str = "manual",
        trace_id: str | None = None,
    ) -> Dict[str, Any]:
        subscriptions = await self.list_subscriptions()
        matching = [
            subscription
            for subscription in subscriptions
            if subscription.get("active")
            and event_type in subscription.get("event_types", [])
        ]

        queued = 0
        async with self._lock:
            for subscription in matching:
                queued += 1
                event = self._build_delivery_event(
                    subscription=subscription,
                    event_type=event_type,
                    payload=payload,
                    source=source,
                    trace_id=trace_id,
                )
                _append_jsonl(self.deliveries_file, event)

        return {"status": "queued", "queued_deliveries": queued}

    async def list_deliveries(
        self,
        status: str | None = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        async with self._lock:
            rows = _read_jsonl(self.deliveries_file)

        latest = _latest_delivery_states(rows)
        deliveries = list(latest.values())
        if status:
            deliveries = [item for item in deliveries if item.get("status") == status]

        deliveries.sort(key=lambda item: item.get("updated_at", item.get("timestamp", "")), reverse=True)
        return deliveries[: max(1, limit)]

    async def dispatch_pending(
        self,
        *,
        limit: int = 100,
        max_attempts: int = 3,
        base_backoff_seconds: int = 5,
    ) -> Dict[str, int]:
        scanned = 0
        delivered = 0
        retried = 0
        dead_lettered = 0

        async with self._lock:
            rows = _read_jsonl(self.deliveries_file)
            latest_map = _latest_delivery_states(rows)

        now = datetime.now(timezone.utc)
        pending: List[Dict[str, Any]] = []
        for item in latest_map.values():
            status = item.get("status")
            if status not in {"queued", "retry_pending"}:
                continue

            next_attempt_at = item.get("next_attempt_at")
            if next_attempt_at:
                try:
                    retry_at = datetime.fromisoformat(next_attempt_at)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    if retry_at > now:
                        continue
                except ValueError:
                    pass

            pending.append(item)

        pending.sort(key=lambda item: item.get("updated_at", item.get("timestamp", "")))

        for delivery in pending[: max(1, limit)]:
            scanned += 1
            attempt = int(delivery.get("attempt", 0)) + 1
            ok, error_message = await self._deliver_once(delivery)
            update_time = _utc_now_iso()

            if ok:
                delivered += 1
                event = {
                    **delivery,
                    "status": "delivered",
                    "attempt": attempt,
                    "updated_at": update_time,
                    "last_error": None,
                    "next_attempt_at": None,
                }
                async with self._lock:
                    _append_jsonl(self.deliveries_file, event)
                continue

            if attempt >= max_attempts:
                dead_lettered += 1
                event = {
                    **delivery,
                    "status": "dead_letter",
                    "attempt": attempt,
                    "updated_at": update_time,
                    "last_error": error_message,
                    "next_attempt_at": None,
                }
                async with self._lock:
                    _append_jsonl(self.deliveries_file, event)
                    _append_jsonl(self.dlq_file, event)
                continue

            retried += 1
            backoff = base_backoff_seconds * (2 ** max(attempt - 1, 0))
            retry_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
            event = {
                **delivery,
                "status": "retry_pending",
                "attempt": attempt,
                "updated_at": update_time,
                "last_error": error_message,
                "next_attempt_at": retry_at.isoformat(),
            }
            async with self._lock:
                _append_jsonl(self.deliveries_file, event)

        return {
            "scanned": scanned,
            "delivered": delivered,
            "retried": retried,
            "dead_lettered": dead_lettered,
        }

    async def replay_dead_letter(self, delivery_id: str) -> Dict[str, Any]:
        async with self._lock:
            rows = _read_jsonl(self.deliveries_file)

        latest_map = _latest_delivery_states(rows)
        current = latest_map.get(delivery_id)
        if current is None:
            raise WebhookDeliveryError(f"Delivery not found: {delivery_id}")

        if current.get("status") != "dead_letter":
            raise WebhookDeliveryError(
                f"Delivery {delivery_id} is not in dead_letter state"
            )

        requeued = {
            **current,
            "status": "queued",
            "attempt": 0,
            "last_error": None,
            "next_attempt_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
            "replayed": True,
        }

        async with self._lock:
            _append_jsonl(self.deliveries_file, requeued)

        return requeued

    def _build_delivery_event(
        self,
        *,
        subscription: Dict[str, Any],
        event_type: str,
        payload: Dict[str, Any],
        source: str,
        trace_id: str | None,
    ) -> Dict[str, Any]:
        now = _utc_now_iso()
        return {
            "timestamp": now,
            "updated_at": now,
            "delivery_id": f"wd_{secrets.token_hex(8)}",
            "subscription_id": subscription["id"],
            "target_url": subscription["target_url"],
            "event_type": event_type,
            "payload": payload,
            "source": source,
            "trace_id": trace_id,
            "status": "queued",
            "attempt": 0,
            "next_attempt_at": now,
            "last_error": None,
        }

    async def _deliver_once(self, delivery: Dict[str, Any]) -> tuple[bool, str | None]:
        secret = ""
        subscription_id = delivery.get("subscription_id", "")
        subscriptions = await self.list_subscriptions()
        for subscription in subscriptions:
            if subscription.get("id") == subscription_id:
                secret = str(subscription.get("secret") or "")
                break

        timestamp = str(int(time.time()))
        envelope = {
            "delivery_id": delivery.get("delivery_id", ""),
            "event_type": delivery.get("event_type", ""),
            "payload": delivery.get("payload", {}),
            "source": delivery.get("source", "gateway"),
            "timestamp": delivery.get("timestamp", _utc_now_iso()),
        }
        body = json.dumps(envelope, separators=(",", ":"), sort_keys=True)

        headers = {
            "content-type": "application/json",
            "x-gateway-delivery-id": str(delivery.get("delivery_id", "")),
            "x-gateway-timestamp": timestamp,
        }
        if secret:
            headers["x-gateway-signature"] = _make_signature(secret, timestamp, body)

        target_url = str(delivery.get("target_url", "")).strip()
        if not target_url:
            return False, "Missing target_url"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(target_url, content=body, headers=headers)
            if 200 <= response.status_code < 300:
                return True, None
            return False, f"HTTP {response.status_code}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)


_webhook_service: Optional[WebhookService] = None


def get_webhook_service() -> WebhookService:
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService()
    return _webhook_service
