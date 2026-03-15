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

from gateway_api.storage_utils import (
    append_jsonl,
    read_json_file,
    read_jsonl_file,
    write_json_atomic,
)
from shared.state import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data" / "gateway"
WEBHOOK_SUBSCRIPTIONS_FILE = DATA_DIR / "webhook_subscriptions.json"
WEBHOOK_DELIVERIES_FILE = DATA_DIR / "webhook_deliveries.jsonl"
WEBHOOK_DLQ_FILE = DATA_DIR / "webhook_dlq.jsonl"
WEBHOOK_SIGNING_SECRET_ENV = "ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET"
GITHUB_WEBHOOK_SECRET_ENV = "ARCTURUS_GATEWAY_GITHUB_WEBHOOK_SECRET"
JIRA_WEBHOOK_TOKEN_ENV = "ARCTURUS_GATEWAY_JIRA_WEBHOOK_TOKEN"
GMAIL_CHANNEL_TOKEN_ENV = "ARCTURUS_GATEWAY_GMAIL_CHANNEL_TOKEN"
DEFAULT_TIMESTAMP_TOLERANCE_SECONDS = 300
DEFAULT_DISPATCH_LEASE_SECONDS = 30


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
    return read_json_file(path, default)


def _write_json(path: Path, payload: Any) -> None:
    _ensure_parent(path)
    write_json_atomic(path, payload)


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    append_jsonl(path, payload)


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    return read_jsonl_file(path)


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


def _env_secret(env_name: str) -> str | None:
    value = os.getenv(env_name)
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned


def _required_env_secret(env_name: str) -> str:
    value = _env_secret(env_name)
    if not value:
        raise WebhookSigningNotConfigured(f"{env_name} is not configured")
    return value


def _header_value(headers: Dict[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def _latest_delivery_states(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    state: Dict[str, Dict[str, Any]] = {}
    for event in events:
        delivery_id = event.get("delivery_id")
        if not delivery_id:
            continue
        state[delivery_id] = event
    return state


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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

    def _validate_github_signature(self, headers: Dict[str, str], raw_body: str) -> str:
        secret = _required_env_secret(GITHUB_WEBHOOK_SECRET_ENV)
        signature_header = _header_value(headers, "x-hub-signature-256")
        if not signature_header:
            raise InvalidWebhookSignature("Missing x-hub-signature-256 header")
        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"),
            raw_body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature_header.strip(), expected):
            raise InvalidWebhookSignature("GitHub signature verification failed")
        return "github_signature"

    def _validate_jira_token(self, headers: Dict[str, str]) -> str:
        token = _required_env_secret(JIRA_WEBHOOK_TOKEN_ENV)
        provided = _header_value(headers, "x-atlassian-webhook-token")
        if not provided:
            raise InvalidWebhookSignature("Missing x-atlassian-webhook-token header")
        if not hmac.compare_digest(provided.strip(), token):
            raise InvalidWebhookSignature("Jira webhook token verification failed")
        return "jira_token"

    def _validate_gmail_token(self, headers: Dict[str, str]) -> str:
        token = _required_env_secret(GMAIL_CHANNEL_TOKEN_ENV)
        provided = _header_value(headers, "x-goog-channel-token")
        if not provided:
            raise InvalidWebhookSignature("Missing x-goog-channel-token header")
        if not hmac.compare_digest(provided.strip(), token):
            raise InvalidWebhookSignature("Gmail channel token verification failed")
        return "gmail_token"

    def validate_inbound_connector_auth(
        self,
        *,
        source: str,
        headers: Dict[str, str],
        raw_body: str,
    ) -> str:
        source_key = source.strip().lower()
        if source_key == "github":
            return self._validate_github_signature(headers=headers, raw_body=raw_body)
        if source_key == "jira":
            return self._validate_jira_token(headers=headers)
        if source_key == "gmail":
            return self._validate_gmail_token(headers=headers)
        raise InvalidWebhookSignature(f"Unsupported connector source: {source_key}")

    def validate_inbound_auth(
        self,
        *,
        source: str,
        headers: Dict[str, str],
        raw_body: str,
    ) -> str:
        gateway_signature = _header_value(headers, "x-gateway-signature")
        gateway_timestamp = _header_value(headers, "x-gateway-timestamp")
        if gateway_signature or gateway_timestamp:
            self.validate_inbound_signature(
                signature_header=gateway_signature,
                timestamp_header=gateway_timestamp,
                raw_body=raw_body,
            )
            return "gateway_signature"
        return self.validate_inbound_connector_auth(
            source=source,
            headers=headers,
            raw_body=raw_body,
        )

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
        selected: List[Dict[str, Any]] = []
        dispatch_owner = f"dispatch_{secrets.token_hex(6)}"
        now = datetime.now(timezone.utc)
        lease_expires_at = now + timedelta(seconds=DEFAULT_DISPATCH_LEASE_SECONDS)
        lease_expires_at_iso = lease_expires_at.isoformat()

        async with self._lock:
            rows = _read_jsonl(self.deliveries_file)
            latest_map = _latest_delivery_states(rows)

            candidates: List[Dict[str, Any]] = []
            for item in latest_map.values():
                status = item.get("status")
                if status not in {"queued", "retry_pending", "in_progress"}:
                    continue

                if status == "in_progress":
                    lease_until = _parse_datetime(item.get("lease_expires_at"))
                    if lease_until is not None and lease_until > now:
                        continue

                next_attempt_at = item.get("next_attempt_at")
                retry_at = _parse_datetime(next_attempt_at)
                if retry_at is not None and retry_at > now:
                    continue

                candidates.append(item)

            candidates.sort(
                key=lambda item: item.get("updated_at", item.get("timestamp", ""))
            )

            for delivery in candidates[: max(1, limit)]:
                leased = {
                    **delivery,
                    "status": "in_progress",
                    "lease_owner": dispatch_owner,
                    "lease_expires_at": lease_expires_at_iso,
                    "updated_at": _utc_now_iso(),
                }
                _append_jsonl(self.deliveries_file, leased)
                selected.append(leased)

        for delivery in selected:
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
                    "lease_owner": None,
                    "lease_expires_at": None,
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
                    "lease_owner": None,
                    "lease_expires_at": None,
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
                "lease_owner": None,
                "lease_expires_at": None,
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
            "lease_owner": None,
            "lease_expires_at": None,
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
            "lease_owner": None,
            "lease_expires_at": None,
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
