"""Policy engine with YAML-based configuration: PII detection + redaction."""
import re
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CC_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
PHONE_RE = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


class PolicyEngine:
    """
    Policy engine with YAML-based configuration.
    
    Loads policies from config/safety_policies.yaml and supports:
    - PII detection and redaction
    - Configurable patterns
    - Organization/user-specific overrides
    """
    
    def __init__(self, config: Dict[str, Any] = None, policy_file: Optional[Path] = None):
        """
        Initialize policy engine.
        
        Args:
            config: Optional runtime config override
            policy_file: Path to YAML policy file (default: config/safety_policies.yaml)
        """
        self.config = config or {}
        self.policy_file = policy_file or Path(__file__).parent.parent / "config" / "safety_policies.yaml"
        self.policies = self._load_policies()
        
        # PII detection settings from policies
        pii_config = self.policies.get("default", {}).get("pii_detection", {})
        self.pii_enabled = pii_config.get("enabled", True)
        self.pii_patterns = pii_config.get("patterns", {
            "email": True,
            "ssn": True,
            "credit_card": True,
            "phone": False,
            "ip_address": False
        })
    
    def _load_policies(self) -> Dict[str, Any]:
        """Load policies from YAML file."""
        try:
            if self.policy_file.exists():
                with open(self.policy_file, 'r') as f:
                    policies = yaml.safe_load(f)
                    return policies or {}
        except Exception as e:
            # If loading fails, use defaults
            print(f"Warning: Failed to load policies from {self.policy_file}: {e}")
        
        return {
            "default": {
                "pii_detection": {
                    "enabled": True,
                    "patterns": {
                        "email": True,
                        "ssn": True,
                        "credit_card": True
                    }
                }
            }
        }
    
    def _get_user_policy(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get policy for specific user/organization from context."""
        if not context:
            return self.policies.get("default", {})
        
        # Check for user-specific policy
        user_id = context.get("user_id") or context.get("session", {}).get("user_id")
        if user_id and "users" in self.policies:
            user_policy = self.policies["users"].get(user_id)
            if user_policy:
                return user_policy
        
        # Check for organization-specific policy
        org_id = context.get("organization_id") or context.get("session", {}).get("organization_id")
        if org_id and "organizations" in self.policies:
            org_policy = self.policies["organizations"].get(org_id)
            if org_policy:
                return org_policy
        
        return self.policies.get("default", {})
    
    def evaluate_output(self, output: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Evaluate output against policies.
        
        Args:
            output: Output to evaluate
            context: Context with user/org info
            
        Returns:
            Dict with action, reason, and redacted_output if needed
        """
        if not self.pii_enabled:
            return {"action": "allow", "reason": "pii_detection_disabled"}
        
        try:
            # Get user-specific policy
            user_policy = self._get_user_policy(context)
            pii_config = user_policy.get("pii_detection", self.policies.get("default", {}).get("pii_detection", {}))
            pii_patterns = pii_config.get("patterns", self.pii_patterns)
            
            txt = ""
            if isinstance(output, dict):
                txt = output.get("text") or output.get("content") or str(output)
            else:
                txt = str(output)
            
            hits = []
            redacted = txt
            
            # Check each PII pattern if enabled
            if pii_patterns.get("email", True) and EMAIL_RE.search(txt):
                hits.append("email")
                redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
            
            if pii_patterns.get("ssn", True) and SSN_RE.search(txt):
                hits.append("ssn")
                redacted = SSN_RE.sub("[REDACTED_SSN]", redacted)
            
            if pii_patterns.get("credit_card", True) and CC_RE.search(txt):
                hits.append("credit_card")
                redacted = CC_RE.sub("[REDACTED_CC]", redacted)
            
            if pii_patterns.get("phone", False) and PHONE_RE.search(txt):
                hits.append("phone")
                redacted = PHONE_RE.sub("[REDACTED_PHONE]", redacted)
            
            if pii_patterns.get("ip_address", False) and IP_RE.search(txt):
                hits.append("ip_address")
                redacted = IP_RE.sub("[REDACTED_IP]", redacted)
            
            if hits:
                return {
                    "action": "redact",
                    "reason": "pii_detected:" + ",".join(hits),
                    "redacted_output": redacted
                }
            
            return {"action": "allow", "reason": "ok"}
        except Exception as e:
            return {"action": "allow", "reason": f"policy_error:{e}"}
    
    def reload_policies(self):
        """Reload policies from file (for runtime updates)."""
        self.policies = self._load_policies()
        pii_config = self.policies.get("default", {}).get("pii_detection", {})
        self.pii_enabled = pii_config.get("enabled", True)
        self.pii_patterns = pii_config.get("patterns", {
            "email": True,
            "ssn": True,
            "credit_card": True
        })