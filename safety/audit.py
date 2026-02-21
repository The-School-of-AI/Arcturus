"""
safety/audit.py

Provides a simple, structured audit logging service for safety-related events.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal

# Configure a dedicated logger for audit trails
audit_logger = logging.getLogger("safety_audit")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False  # Prevent duplicate logs in the root logger

# Ensure the logs directory exists
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Add a file handler to write audit logs to a specific file
if not audit_logger.handlers:
    file_handler = logging.FileHandler(LOGS_DIR / "aegis_audit.log")
    # Use a simple formatter for the raw log file, as the message is already JSON
    formatter = logging.Formatter('%(asctime)s %(message)s')
    file_handler.setFormatter(formatter)
    audit_logger.addHandler(file_handler)

AuditEventType = Literal[
    "input_blocked",
    "output_redacted",
    "tool_call_blocked",
    "rate_limit_exceeded",
    "canary_token_triggered",
    "jailbreak_detected",
    "policy_violation",
]

class AuditLogger:
    """
    A centralized logger for recording security-sensitive events in a structured format.
    """

    @staticmethod
    def log_event(
        event_type: AuditEventType,
        context: Dict[str, Any],
        metadata: Dict[str, Any] = None,
    ):
        """
        Logs a structured safety event.

        Args:
            event_type: The type of event being logged.
            context: A dictionary containing the core details of the event,
                     such as session ID, user ID, and the content that triggered it.
            metadata: Optional dictionary for additional, non-essential details.
        """
        log_entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "context": context,
            "metadata": metadata or {},
        }

        try:
            # Log as a JSON string
            audit_logger.info(json.dumps(log_entry))
        except TypeError as e:
            # Fallback for non-serializable content
            audit_logger.error(f"Failed to serialize audit log entry: {e}")
            audit_logger.info(str(log_entry))

# Convenience function for easy access
log_safety_event = AuditLogger.log_event
