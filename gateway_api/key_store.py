from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from shared.state import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data" / "gateway"
API_KEYS_FILE = DATA_DIR / "api_keys.json"
KEY_AUDIT_FILE = DATA_DIR / "key_audit.jsonl"

_file_locks: Dict[Path, asyncio.Lock] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _get_lock(path: Path) -> asyncio.Lock:
    lock = _file_locks.get(path)
    if lock is None:
        lock = asyncio.Lock()
        _file_locks[path] = lock
    return lock


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


class GatewayKeyStore:
    def __init__(self, keys_file: Path = API_KEYS_FILE, audit_file: Path = KEY_AUDIT_FILE):
        self.keys_file = keys_file
        self.audit_file = audit_file

    async def list_keys(self, include_revoked: bool = False) -> List[Dict[str, Any]]:
        async with _get_lock(self.keys_file):
            payload = _read_json(self.keys_file, {"keys": []})
            keys = payload.get("keys", [])
            if include_revoked:
                return keys
            return [key for key in keys if key.get("status") != "revoked"]

    async def get_key(self, key_id: str) -> Optional[Dict[str, Any]]:
        keys = await self.list_keys(include_revoked=True)
        return next((key for key in keys if key.get("key_id") == key_id), None)

    async def create_key(
        self,
        name: str,
        scopes: List[str],
        rpm_limit: int,
        burst_limit: int,
    ) -> Tuple[Dict[str, Any], str]:
        plaintext = f"arc_{secrets.token_urlsafe(32)}"
        key_hash = _hash_key(plaintext)
        now = _utc_now_iso()
        key_id = f"gwk_{secrets.token_hex(6)}"

        record = {
            "key_id": key_id,
            "name": name,
            "key_hash": key_hash,
            "secret_prefix": plaintext[:12],
            "scopes": scopes,
            "rpm_limit": rpm_limit,
            "burst_limit": burst_limit,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

        async with _get_lock(self.keys_file):
            payload = _read_json(self.keys_file, {"keys": []})
            payload.setdefault("keys", []).append(record)
            _write_json(self.keys_file, payload)

        await self._audit("create", key_id, {"name": name, "scopes": scopes})
        return record, plaintext

    async def update_key(
        self,
        key_id: str,
        *,
        name: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        rpm_limit: Optional[int] = None,
        burst_limit: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        async with _get_lock(self.keys_file):
            payload = _read_json(self.keys_file, {"keys": []})
            keys = payload.get("keys", [])
            for record in keys:
                if record.get("key_id") != key_id:
                    continue
                if name is not None:
                    record["name"] = name
                if scopes is not None:
                    record["scopes"] = scopes
                if rpm_limit is not None:
                    record["rpm_limit"] = rpm_limit
                if burst_limit is not None:
                    record["burst_limit"] = burst_limit
                if status is not None:
                    record["status"] = status
                record["updated_at"] = _utc_now_iso()
                _write_json(self.keys_file, payload)
                await self._audit("update", key_id, {"status": record.get("status")})
                return record

        return None

    async def revoke_key(self, key_id: str) -> Optional[Dict[str, Any]]:
        return await self.update_key(key_id, status="revoked")

    async def rotate_key(self, key_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        plaintext = f"arc_{secrets.token_urlsafe(32)}"
        key_hash = _hash_key(plaintext)

        async with _get_lock(self.keys_file):
            payload = _read_json(self.keys_file, {"keys": []})
            keys = payload.get("keys", [])
            for record in keys:
                if record.get("key_id") != key_id:
                    continue
                record["key_hash"] = key_hash
                record["secret_prefix"] = plaintext[:12]
                record["status"] = "active"
                record["updated_at"] = _utc_now_iso()
                _write_json(self.keys_file, payload)
                await self._audit("rotate", key_id, {})
                return record, plaintext

        return None, None

    async def validate_api_key(self, plaintext: str) -> Optional[Dict[str, Any]]:
        target_hash = _hash_key(plaintext)
        keys = await self.list_keys(include_revoked=True)
        for record in keys:
            if record.get("status") != "active":
                continue
            if hmac.compare_digest(record.get("key_hash", ""), target_hash):
                return record
        return None

    async def _audit(self, event_type: str, key_id: str, metadata: Dict[str, Any]) -> None:
        payload = {
            "timestamp": _utc_now_iso(),
            "event": event_type,
            "key_id": key_id,
            "metadata": metadata,
        }
        async with _get_lock(self.audit_file):
            _append_jsonl(self.audit_file, payload)


_gateway_key_store: Optional[GatewayKeyStore] = None


def get_gateway_key_store() -> GatewayKeyStore:
    global _gateway_key_store
    if _gateway_key_store is None:
        _gateway_key_store = GatewayKeyStore()
    return _gateway_key_store
