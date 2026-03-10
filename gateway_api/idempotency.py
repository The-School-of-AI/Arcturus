from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from gateway_api.storage_utils import read_json_file, write_json_atomic
from shared.state import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data" / "gateway"
IDEMPOTENCY_RECORDS_FILE = DATA_DIR / "idempotency_records.json"
IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60

_file_locks: Dict[Path, asyncio.Lock] = {}


@dataclass
class IdempotencyRequestContext:
    actor: str
    method: str
    path: str
    idempotency_key: str


@dataclass
class IdempotencyStartResult:
    outcome: Literal["created", "replayed", "conflict", "in_progress"]
    record: Dict[str, Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _expires_at_iso(ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS) -> str:
    return (_utc_now() + timedelta(seconds=ttl_seconds)).isoformat()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default: Any) -> Any:
    return read_json_file(path, default)


def _write_json(path: Path, payload: Any) -> None:
    _ensure_parent(path)
    write_json_atomic(path, payload)


def _get_lock(path: Path) -> asyncio.Lock:
    lock = _file_locks.get(path)
    if lock is None:
        lock = asyncio.Lock()
        _file_locks[path] = lock
    return lock


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _normalized_method(method: str) -> str:
    return method.upper().strip()


def _normalized_path(path: str) -> str:
    cleaned = path.strip()
    return cleaned or "/"


def _record_key(actor: str, method: str, path: str, idempotency_key: str) -> str:
    return "|".join([
        actor.strip(),
        _normalized_method(method),
        _normalized_path(path),
        idempotency_key.strip(),
    ])


def _request_hash(actor: str, method: str, path: str, payload: Any) -> str:
    canonical_payload = _canonical_json(payload)
    raw = f"{canonical_payload}|{_normalized_method(method)}|{_normalized_path(path)}|{actor.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_expired(record: Dict[str, Any], now: datetime) -> bool:
    expires_at = record.get("expires_at")
    if not isinstance(expires_at, str) or not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        return True

    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    return expiry <= now


def _cleanup_expired_records(payload: Dict[str, Any], now: datetime) -> bool:
    records = payload.setdefault("records", {})
    if not isinstance(records, dict):
        payload["records"] = {}
        return True

    to_delete = []
    for key, value in records.items():
        if not isinstance(value, dict) or _is_expired(value, now):
            to_delete.append(key)

    for key in to_delete:
        records.pop(key, None)

    return bool(to_delete)


def _idempotency_error(code: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return {"error": payload}


class IdempotencyStore:
    def __init__(
        self,
        records_file: Path = IDEMPOTENCY_RECORDS_FILE,
        ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS,
    ) -> None:
        self.records_file = records_file
        self.ttl_seconds = ttl_seconds

    async def start_request(
        self,
        *,
        actor: str,
        method: str,
        path: str,
        idempotency_key: str,
        payload: Any,
    ) -> IdempotencyStartResult:
        actor_clean = actor.strip()
        method_clean = _normalized_method(method)
        path_clean = _normalized_path(path)
        key_clean = idempotency_key.strip()

        request_hash = _request_hash(actor_clean, method_clean, path_clean, payload)
        record_id = _record_key(actor_clean, method_clean, path_clean, key_clean)

        now = _utc_now()
        now_iso = now.isoformat()

        async with _get_lock(self.records_file):
            store_payload = _read_json(self.records_file, {"records": {}})
            cleaned = _cleanup_expired_records(store_payload, now)
            records = store_payload.setdefault("records", {})

            existing = records.get(record_id)
            if isinstance(existing, dict):
                existing_hash = str(existing.get("request_hash", ""))
                state = str(existing.get("state", ""))

                if existing_hash and existing_hash != request_hash:
                    if cleaned:
                        _write_json(self.records_file, store_payload)
                    return IdempotencyStartResult(outcome="conflict", record=existing)

                if state == "in_progress":
                    if cleaned:
                        _write_json(self.records_file, store_payload)
                    return IdempotencyStartResult(outcome="in_progress", record=existing)

                if state in {"completed", "failed"}:
                    if cleaned:
                        _write_json(self.records_file, store_payload)
                    return IdempotencyStartResult(outcome="replayed", record=existing)

            record = {
                "actor": actor_clean,
                "method": method_clean,
                "path": path_clean,
                "idempotency_key": key_clean,
                "request_hash": request_hash,
                "state": "in_progress",
                "status_code": None,
                "response_body": None,
                "response_headers": {},
                "created_at": now_iso,
                "updated_at": now_iso,
                "expires_at": _expires_at_iso(self.ttl_seconds),
            }
            records[record_id] = record
            _write_json(self.records_file, store_payload)
            return IdempotencyStartResult(outcome="created", record=record)

    async def finalize(
        self,
        *,
        actor: str,
        method: str,
        path: str,
        idempotency_key: str,
        state: Literal["completed", "failed"],
        status_code: int,
        response_body: Any,
        response_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        actor_clean = actor.strip()
        method_clean = _normalized_method(method)
        path_clean = _normalized_path(path)
        key_clean = idempotency_key.strip()
        record_id = _record_key(actor_clean, method_clean, path_clean, key_clean)

        now = _utc_now()
        now_iso = now.isoformat()

        async with _get_lock(self.records_file):
            store_payload = _read_json(self.records_file, {"records": {}})
            _cleanup_expired_records(store_payload, now)
            records = store_payload.setdefault("records", {})

            record = records.get(record_id)
            if not isinstance(record, dict):
                record = {
                    "actor": actor_clean,
                    "method": method_clean,
                    "path": path_clean,
                    "idempotency_key": key_clean,
                    "request_hash": "",
                    "state": state,
                    "status_code": int(status_code),
                    "response_body": jsonable_encoder(response_body),
                    "response_headers": response_headers or {},
                    "created_at": now_iso,
                    "updated_at": now_iso,
                    "expires_at": _expires_at_iso(self.ttl_seconds),
                }
                records[record_id] = record
            else:
                record["state"] = state
                record["status_code"] = int(status_code)
                record["response_body"] = jsonable_encoder(response_body)
                record["response_headers"] = {
                    str(key): str(value) for key, value in (response_headers or {}).items()
                }
                record["updated_at"] = now_iso
                record["expires_at"] = _expires_at_iso(self.ttl_seconds)

            _write_json(self.records_file, store_payload)
            return record


_idempotency_store: Optional[IdempotencyStore] = None


def get_idempotency_store() -> IdempotencyStore:
    global _idempotency_store
    if _idempotency_store is None:
        _idempotency_store = IdempotencyStore()
    return _idempotency_store


async def begin_idempotent_request(
    *,
    request: Request,
    actor: str,
    idempotency_key: Optional[str],
    payload: Any,
    response: Optional[Response] = None,
) -> tuple[Optional[IdempotencyRequestContext], Optional[JSONResponse]]:
    key = (idempotency_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_idempotency_error(
                "idempotency_key_required",
                "Idempotency-Key header is required",
            ),
        )

    result = await get_idempotency_store().start_request(
        actor=actor,
        method=request.method,
        path=request.url.path,
        idempotency_key=key,
        payload=jsonable_encoder(payload),
    )

    if result.outcome == "conflict":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_idempotency_error(
                "idempotency_key_conflict",
                "Idempotency key reused with a different request payload",
            ),
        )

    if result.outcome == "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_idempotency_error(
                "idempotency_request_in_progress",
                "An idempotent request with this key is already in progress",
                details={"retry_after_seconds": 1},
            ),
        )

    if result.outcome == "replayed":
        record = result.record
        replay_headers = {
            str(k): str(v)
            for k, v in (record.get("response_headers") or {}).items()
            if str(k).strip()
        }
        replay_headers["X-Idempotency-Status"] = "replayed"
        replay_headers["X-Idempotency-Key"] = key

        status_code = int(record.get("status_code") or 200)
        body = record.get("response_body")
        if body is None:
            body = {}

        replay_response = JSONResponse(
            status_code=status_code,
            content=body,
            headers=replay_headers,
        )
        return None, replay_response

    if response is not None:
        response.headers["X-Idempotency-Status"] = "created"
        response.headers["X-Idempotency-Key"] = key

    return (
        IdempotencyRequestContext(
            actor=actor,
            method=request.method,
            path=request.url.path,
            idempotency_key=key,
        ),
        None,
    )


async def finalize_idempotent_success(
    context: IdempotencyRequestContext,
    *,
    status_code: int,
    response_body: Any,
    response_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return await get_idempotency_store().finalize(
        actor=context.actor,
        method=context.method,
        path=context.path,
        idempotency_key=context.idempotency_key,
        state="completed",
        status_code=status_code,
        response_body=response_body,
        response_headers=response_headers,
    )


async def finalize_idempotent_failure(
    context: IdempotencyRequestContext,
    *,
    status_code: int,
    detail: Any,
    response_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return await get_idempotency_store().finalize(
        actor=context.actor,
        method=context.method,
        path=context.path,
        idempotency_key=context.idempotency_key,
        state="failed",
        status_code=status_code,
        response_body={"detail": jsonable_encoder(detail)},
        response_headers=response_headers,
    )


def derive_inbound_idempotency_key(
    *,
    source: str,
    signature_header: Optional[str],
    timestamp_header: Optional[str],
    raw_body: str,
    external_event_id: Optional[str] = None,
) -> str:
    source_clean = source.strip().lower()
    event_id = (external_event_id or "").strip()
    if event_id:
        base = f"{source_clean}|event_id|{event_id}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    signature = (signature_header or "").strip()
    timestamp = (timestamp_header or "").strip()
    # Fallback path keeps the key stable for the same source and request body
    # even when connector signatures/timestamps rotate across retries.
    if raw_body.strip():
        base = f"{source_clean}|body|{raw_body}"
    else:
        base = f"{source_clean}|{signature}|{timestamp}|{raw_body}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()
