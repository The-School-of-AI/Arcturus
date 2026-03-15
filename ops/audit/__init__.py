"""
ops.audit — Audit logging and GDPR data management for P14.5.

Provides:
- AuditLogger / audit_logger: state-change audit trail (MongoDB + JSONL fallback)
- SessionDataManager: GDPR export and deletion across all data stores
"""

from ops.audit.audit_logger import (
    AuditEntry,
    AuditLogger,
    AuditRepository,
    audit_logger,
)
from ops.audit.data_manager import SessionDataManager

__all__ = [
    "AuditEntry",
    "AuditLogger",
    "AuditRepository",
    "SessionDataManager",
    "audit_logger",
]
