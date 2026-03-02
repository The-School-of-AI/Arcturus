from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any
from pathlib import Path
import yaml
import logging

logger = logging.getLogger("bazaar")

class TrustLevel(Enum):
    """
    Security levels for skill verification, from least to most strict.
    
    Each level includes ALL checks from lower levels:
      OPEN      → no checks
      CHECKSUM  → integrity check (SHA-256)
      SIGNED    → integrity + author signature (RSA)  
      VERIFIED  → integrity + signature + trusted author list
    """
    OPEN = 1
    CHECKSUM = 2
    SIGNED = 3
    VERIFIED = 4

@dataclass
class PolicyResult:
    """Result of a trust policy evaluation."""
    allowed: bool
    reason: str
    trust_level_met: Optional[TrustLevel] = None
    warnings: List[str] = field(default_factory=list)

class TrustPolicy:
    """
    Configurable trust policy for the marketplace.
    
    Controls:
    - Required trust level (OPEN → VERIFIED)
    - Trusted authors list (for VERIFIED level)
    - Blocked skills (explicit deny list)
    - Allowed permissions (what skills can request)
    """
    
    def __init__(
        self,
        trust_level: TrustLevel = TrustLevel.CHECKSUM,
        trusted_authors: List[str] = None,
        blocked_skills: List[str] = None,
        allowed_permissions: List[str] = None,
    ):
        self.trust_level = trust_level
        self.trusted_authors: Set[str] = set(trusted_authors or [])
        self.blocked_skills: Set[str] = set(blocked_skills or [])
        self.allowed_permissions: Set[str] = set(
            allowed_permissions or ["network", "filesystem", "execute"]
        )
    
    @classmethod
    def from_config(cls, config_path: Path) -> "TrustPolicy":
        """
        Load trust policy from a YAML config file.
        
        Example config:
            trust_level: SIGNED
            trusted_authors:
              - alice
              - bob
            blocked_skills:
              - known_malware_skill
            allowed_permissions:
              - network
              - filesystem
        """
        if not config_path.exists():
            logger.warning(f"Trust config not found: {config_path}, using defaults")
            return cls()
        
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
        
        # Parse trust level from string
        level_str = data.get("trust_level", "CHECKSUM").upper()
        try:
            level = TrustLevel[level_str]
        except KeyError:
            logger.warning(f"Unknown trust level '{level_str}', defaulting to CHECKSUM")
            level = TrustLevel.CHECKSUM
        
        return cls(
            trust_level=level,
            trusted_authors=data.get("trusted_authors", []),
            blocked_skills=data.get("blocked_skills", []),
            allowed_permissions=data.get("allowed_permissions"),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrustPolicy":
        """Create a policy from a dictionary (for testing)."""
        level_str = data.get("trust_level", "CHECKSUM").upper()
        try:
            level = TrustLevel[level_str]
        except KeyError:
            level = TrustLevel.CHECKSUM
        
        return cls(
            trust_level=level,
            trusted_authors=data.get("trusted_authors", []),
            blocked_skills=data.get("blocked_skills", []),
            allowed_permissions=data.get("allowed_permissions"),
        )

    def evaluate(self, manifest, skill_dir: Path = None, 
                 public_key_path: Path = None) -> PolicyResult:
        """
        Evaluate whether a skill passes the trust policy.
        
        Checks (in order):
        1. Is the skill explicitly blocked?
        2. Does it request disallowed permissions?
        3. Does it meet the required trust level?
        
        Args:
            manifest: SkillManifest to evaluate
            skill_dir: Path to skill directory (needed for CHECKSUM+ levels)
            public_key_path: Path to author's public key (needed for SIGNED+ levels)
            
        Returns:
            PolicyResult with allowed/denied status and reason
        """
        warnings = []
        
        # --- Check 1: Blocked list ---
        if manifest.name in self.blocked_skills:
            return PolicyResult(
                allowed=False,
                reason=f"Skill '{manifest.name}' is explicitly blocked by policy"
            )
        
        # --- Check 2: Permissions ---
        disallowed = set(manifest.permissions) - self.allowed_permissions
        if disallowed:
            return PolicyResult(
                allowed=False,
                reason=f"Skill requests disallowed permissions: {sorted(disallowed)}"
            )
        
        # --- Check 3: Trust level ---
        if self.trust_level == TrustLevel.OPEN:
            return PolicyResult(
                allowed=True,
                reason="Trust level is OPEN — no verification required",
                trust_level_met=TrustLevel.OPEN,
                warnings=warnings
            )
        
        # CHECKSUM level and above
        if self.trust_level.value >= TrustLevel.CHECKSUM.value:
            if not skill_dir:
                return PolicyResult(
                    allowed=False,
                    reason="Skill directory required for checksum verification"
                )
            
            from marketplace.integrity import verify_checksum
            if manifest.checksum and not verify_checksum(skill_dir):
                return PolicyResult(
                    allowed=False,
                    reason="SECURITY: Checksum verification failed — skill may be tampered"
                )
            
            if not manifest.checksum:
                warnings.append("Skill has no checksum (unsigned integrity)")
        
        # SIGNED level and above
        if self.trust_level.value >= TrustLevel.SIGNED.value:
            if not manifest.signature:
                return PolicyResult(
                    allowed=False,
                    reason="Policy requires SIGNED skills, but this skill has no signature"
                )
            
            if not public_key_path or not public_key_path.exists():
                return PolicyResult(
                    allowed=False,
                    reason="Author's public key not found — cannot verify signature"
                )
            
            from marketplace.signing import verify_signature
            if not verify_signature(manifest.checksum, manifest.signature, public_key_path):
                return PolicyResult(
                    allowed=False,
                    reason="SECURITY: Signature verification failed — skill author cannot be verified"
                )
        
        # VERIFIED level
        if self.trust_level.value >= TrustLevel.VERIFIED.value:
            if manifest.author not in self.trusted_authors:
                return PolicyResult(
                    allowed=False,
                    reason=f"Author '{manifest.author}' is not in the trusted authors list"
                )
        
        # Determine what level was achieved
        achieved = TrustLevel.OPEN
        if manifest.checksum:
            achieved = TrustLevel.CHECKSUM
        if manifest.signature:
            achieved = TrustLevel.SIGNED
        if manifest.author in self.trusted_authors:
            achieved = TrustLevel.VERIFIED
        
        return PolicyResult(
            allowed=True,
            reason=f"Skill passes {self.trust_level.name} trust policy",
            trust_level_met=achieved,
            warnings=warnings
        )
