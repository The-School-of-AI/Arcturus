import json
import os
import time
import hmac
import hashlib
from datetime import datetime
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("phantom-telemetry")

class BrowserTelemetry:
    """
    Handles audit logging and telemetry for the browser agent.
    Ensures all actions are recorded in an append-only, 'immutable' log.
    Uses HMAC signing to prevent tampering.
    Integration point for Project 14.
    """
    
    def __init__(self, log_dir: Optional[str] = None, secret_key: Optional[str] = None):
        self.log_dir = log_dir or os.path.join(os.getcwd(), "data", "audit_logs")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, f"audit_{datetime.now().strftime('%Y-%m-%d')}.jsonl")
        self.secret_key = secret_key or os.environ.get("PHANTOM_AUDIT_SECRET", "super-secret-key").encode()
        
    def _sign_entry(self, entry_dict: Dict[str, Any]) -> str:
        """Create an HMAC-SHA256 signature for a log entry."""
        message = json.dumps(entry_dict, sort_keys=True).encode()
        return hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()

    def log_action(self, action_type: str, details: Dict[str, Any]):
        """Append a signed action to the audit log."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action_type,
            "details": details,
            "session_id": os.environ.get("PHANTOM_SESSION_ID", "default")
        }
        
        # Add signature for immutability check
        entry["signature"] = self._sign_entry(entry)
        
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
            logger.info(f"Audit Log (Signed): {action_type}")
        except Exception as e:
            logger.error(f"Failed to write to audit log: {e}")

    def verify_log(self, file_path: Optional[str] = None) -> bool:
        """Verify the integrity of a signed log file."""
        target_file = file_path or self.log_file
        if not os.path.exists(target_file):
            return True
            
        try:
            with open(target_file, "r") as f:
                for line in f:
                    entry = json.loads(line)
                    signature = entry.pop("signature", None)
                    if not signature:
                        logger.error("Missing signature in log entry")
                        return False
                    
                    expected = self._sign_entry(entry)
                    if not hmac.compare_digest(signature, expected):
                        logger.error(f"Signature mismatch at {entry.get('timestamp')}")
                        return False
            return True
        except Exception as e:
            logger.error(f"Log verification error: {e}")
            return False

    def log_telemetry(self, metric: str, value: Any):
        """Log performance or usage metrics (P14 hook)."""
        # Integration point for Project 14 Observation Hub
        self.log_action("telemetry", {"metric": metric, "value": value})

# Audit logging and telemetry integration for P10/P14.
