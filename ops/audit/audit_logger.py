"""
Audit Logger: MongoDB-backed (with JSONL fallback) audit trail for admin actions.

Records every state-changing admin operation with actor, action, resource,
old/new values, and context.  Query interface mirrors HealthRepository patterns.

Usage::

    from ops.audit import audit_logger
    audit_logger.log_action("admin", "feature_toggle", "flag:voice_wake", True, False)
"""

import json
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings_loader import settings

logger = logging.getLogger("watchtower.audit")

_FALLBACK_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "audit_log.jsonl"

Collection = Any  # pymongo collection type


@dataclass
class AuditEntry:
    """Single audit log entry."""

    timestamp: str
    actor: str
    action: str
    resource: str
    old_value: Any = None
    new_value: Any = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AuditRepository:
    """MongoDB persistence for audit log entries."""

    _indexes_ensured: bool = False

    def __init__(self, collection: Collection):
        self._coll = collection
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        if AuditRepository._indexes_ensured:
            return
        try:
            self._coll.create_index([("timestamp", -1)])
            self._coll.create_index([("action", 1), ("timestamp", -1)])
            self._coll.create_index([("resource", 1)])
            AuditRepository._indexes_ensured = True
        except Exception:
            pass

    def log(self, entry: AuditEntry) -> None:
        """Insert one audit entry."""
        doc = entry.to_dict()
        # Convert ISO string to datetime for MongoDB time queries
        try:
            doc["timestamp"] = datetime.fromisoformat(doc["timestamp"])
        except (ValueError, TypeError):
            doc["timestamp"] = datetime.utcnow()
        self._coll.insert_one(doc)

    def query(
        self,
        hours: int = 24,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query audit entries within a time window."""
        since = datetime.utcnow() - timedelta(hours=hours)
        match: Dict[str, Any] = {"timestamp": {"$gte": since}}
        if action:
            match["action"] = action
        if resource:
            match["resource"] = {"$regex": resource, "$options": "i"}

        cursor = self._coll.find(match, {"_id": 0}).sort("timestamp", -1).limit(limit)
        entries = []
        for doc in cursor:
            if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
                doc["timestamp"] = doc["timestamp"].isoformat()
            # Ensure old_value/new_value are JSON-serializable
            for key in ("old_value", "new_value"):
                if key in doc and not isinstance(doc[key], (str, int, float, bool, list, dict, type(None))):
                    doc[key] = str(doc[key])
            entries.append(doc)
        return entries

    def delete_by_resource(self, resource_pattern: str) -> int:
        """Delete audit entries matching a resource pattern. Returns count deleted."""
        result = self._coll.delete_many({"resource": {"$regex": resource_pattern}})
        return result.deleted_count


class AuditLogger:
    """
    Unified audit logger: MongoDB when watchtower enabled, JSONL fallback otherwise.

    Thread-safe singleton — import and use the module-level `audit_logger`.
    """

    def __init__(self, fallback_path: Optional[Path] = None):
        self._fallback_path = fallback_path or _FALLBACK_LOG_PATH
        self._lock = threading.Lock()
        self._repo: Optional[AuditRepository] = None

    def _get_repo(self) -> Optional[AuditRepository]:
        """Lazily initialize MongoDB repository if watchtower is enabled."""
        if self._repo is not None:
            return self._repo
        try:
            wt = settings.get("watchtower", {})
            if not wt.get("enabled", False):
                return None
            from pymongo import MongoClient
            uri = wt.get("mongodb_uri", "mongodb://localhost:27017")
            client = MongoClient(uri, serverSelectionTimeoutMS=2000)
            self._repo = AuditRepository(client["watchtower"]["audit_log"])
            return self._repo
        except Exception as e:
            logger.debug("MongoDB audit unavailable, using JSONL fallback: %s", e)
            return None

    def log_action(
        self,
        actor: str,
        action: str,
        resource: str,
        old_value: Any = None,
        new_value: Any = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log a state-changing action. Always succeeds (falls back to JSONL)."""
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat(),
            actor=actor,
            action=action,
            resource=resource,
            old_value=old_value,
            new_value=new_value,
            context=context or {},
        )

        repo = self._get_repo()
        if repo:
            try:
                repo.log(entry)
                logger.info("Audit: %s %s %s", actor, action, resource)
                return entry
            except Exception as e:
                logger.warning("MongoDB audit write failed, falling back to JSONL: %s", e)

        # JSONL fallback
        self._write_jsonl(entry)
        return entry

    def query(
        self,
        hours: int = 24,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query audit log. Uses MongoDB if available, else reads JSONL."""
        repo = self._get_repo()
        if repo:
            try:
                return repo.query(hours=hours, action=action, resource=resource, limit=limit)
            except Exception:
                pass

        # JSONL fallback query
        return self._read_jsonl(hours=hours, action=action, resource=resource, limit=limit)

    def _write_jsonl(self, entry: AuditEntry) -> None:
        """Append entry to JSONL file (fallback)."""
        with self._lock:
            self._fallback_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._fallback_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), default=str) + "\n")
        logger.info("Audit (JSONL): %s %s %s", entry.actor, entry.action, entry.resource)

    def _read_jsonl(
        self,
        hours: int = 24,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Read from JSONL file with optional filters."""
        if not self._fallback_path.exists():
            return []
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        entries = []
        with open(self._fallback_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry.get("timestamp", ""))
                    if ts < cutoff:
                        continue
                    if action and entry.get("action") != action:
                        continue
                    if resource and resource.lower() not in entry.get("resource", "").lower():
                        continue
                    entries.append(entry)
                except (json.JSONDecodeError, ValueError):
                    continue
        # Newest first
        entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return entries[:limit]


# Module-level singleton
audit_logger = AuditLogger()
