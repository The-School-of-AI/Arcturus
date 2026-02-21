"""Minimal policy engine: PII detection + redaction contract."""
import re
from typing import Any, Dict

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CC_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

class PolicyEngine:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    def evaluate_output(self, output: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            txt = ""
            if isinstance(output, dict):
                txt = output.get("text") or output.get("content") or str(output)
            else:
                txt = str(output)
            hits = []
            if EMAIL_RE.search(txt):
                hits.append("email")
            if SSN_RE.search(txt):
                hits.append("ssn")
            if CC_RE.search(txt):
                hits.append("credit_card")
            if hits:
                redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", txt)
                redacted = SSN_RE.sub("[REDACTED_SSN]", redacted)
                redacted = CC_RE.sub("[REDACTED_CC]", redacted)
                return {"action": "redact", "reason": "pii_detected:" + ",".join(hits), "redacted_output": redacted}
            return {"action": "allow", "reason": "ok"}
        except Exception as e:
            return {"action": "allow", "reason": f"policy_error:{e}"}