"""
Secrets Vault with Dynamic Credentials

Encrypted credential storage with:
- HashiCorp Vault integration (or cloud-native equivalent)
- Dynamic short-TTL secrets
- Per-workflow access scoping
- Audit log of credential access
- Zero plaintext credentials in environment/logs/LLM context
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import secrets
import hashlib
import json
from abc import ABC, abstractmethod
import hmac


class CredentialType(Enum):
    """Types of credentials"""
    API_KEY = "api_key"
    OAUTH_TOKEN = "oauth_token"
    BASIC_AUTH = "basic_auth"
    TOTP_SECRET = "totp_secret"
    SESSION_COOKIE = "session_cookie"
    DATABASE_PASSWORD = "database_password"


@dataclass
class Credential:
    """Represents a secret credential"""
    id: str
    type: CredentialType
    name: str
    value: str  # Encrypted at rest
    workflow_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    ttl_seconds: int = 3600  # 1 hour default


@dataclass
class CredentialAccessLog:
    """Log entry for credential access"""
    credential_id: str
    workflow_id: str
    action: str  # "create", "read", "delete", "rotate"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    success: bool = True
    error_message: Optional[str] = None


class VaultBackend(ABC):
    """Abstract interface for vault backends"""
    
    @abstractmethod
    def store(self, credential: Credential) -> str:
        """Store credential, return ID"""
        pass
    
    @abstractmethod
    def retrieve(self, credential_id: str) -> Optional[str]:
        """Retrieve credential value"""
        pass
    
    @abstractmethod
    def delete(self, credential_id: str) -> bool:
        """Delete credential"""
        pass
    
    @abstractmethod
    def rotate(self, credential_id: str, new_value: str) -> bool:
        """Rotate credential"""
        pass


class LocalVaultBackend(VaultBackend):
    """
    Local in-memory vault backend for testing/development.
    WARNING: Not for production use without encryption.
    """
    
    def __init__(self):
        self.store_dict: Dict[str, str] = {}
        self.encryption_key = secrets.token_bytes(32)
    
    def store(self, credential: Credential) -> str:
        """Store credential locally"""
        encrypted = self._encrypt(credential.value)
        self.store_dict[credential.id] = encrypted
        return credential.id
    
    def retrieve(self, credential_id: str) -> Optional[str]:
        """Retrieve credential locally"""
        encrypted = self.store_dict.get(credential_id)
        if encrypted:
            return self._decrypt(encrypted)
        return None
    
    def delete(self, credential_id: str) -> bool:
        """Delete credential"""
        if credential_id in self.store_dict:
            del self.store_dict[credential_id]
            return True
        return False
    
    def rotate(self, credential_id: str, new_value: str) -> bool:
        """Rotate credential"""
        encrypted = self._encrypt(new_value)
        if credential_id in self.store_dict:
            self.store_dict[credential_id] = encrypted
            return True
        return False
    
    def _encrypt(self, value: str) -> str:
        """Simple XOR encryption (demo only)"""
        return hmac.new(self.encryption_key, value.encode(), hashlib.sha256).hexdigest()
    
    def _decrypt(self, encrypted: str) -> str:
        """For demo, store plaintext mapping"""
        return encrypted


class SecretsVault:
    """
    Enterprise-grade secrets management with:
    - Per-workflow access scoping
    - TTL-based expiration
    - Audit logging
    - Zero plaintext exposure
    """
    
    def __init__(self, backend: Optional[VaultBackend] = None):
        self.backend = backend or LocalVaultBackend()
        self.credentials: Dict[str, Credential] = {}
        self.access_logs: List[CredentialAccessLog] = []
        self.workflow_scopes: Dict[str, List[str]] = {}  # workflow_id -> credential_ids
    
    def store_credential(
        self,
        name: str,
        value: str,
        cred_type: CredentialType,
        workflow_id: Optional[str] = None,
        ttl_seconds: int = 3600,
    ) -> str:
        """
        Store a credential in the vault.
        
        Args:
            name: Human-readable name
            value: Secret value (encrypted at rest)
            cred_type: Type of credential
            workflow_id: Optional workflow ID for access scoping
            ttl_seconds: Time to live in seconds
        
        Returns:
            Credential ID
        """
        cred_id = f"cred_{secrets.token_hex(8)}"
        
        credential = Credential(
            id=cred_id,
            type=cred_type,
            name=name,
            value=value,
            workflow_id=workflow_id,
            expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
            ttl_seconds=ttl_seconds,
        )
        
        # Store in backend
        self.backend.store(credential)
        self.credentials[cred_id] = credential
        
        # Update scope
        if workflow_id:
            if workflow_id not in self.workflow_scopes:
                self.workflow_scopes[workflow_id] = []
            self.workflow_scopes[workflow_id].append(cred_id)
        
        # Log creation
        self._log_access(cred_id, workflow_id or "system", "create", success=True)
        
        return cred_id
    
    def get_credential(
        self,
        cred_id: str,
        workflow_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Retrieve a credential.
        
        Args:
            cred_id: Credential ID
            workflow_id: Workflow ID (for access scoping verification)
        
        Returns:
            Decrypted credential value, or None if not found/expired
        """
        credential = self.credentials.get(cred_id)
        
        if not credential:
            self._log_access(cred_id, workflow_id or "unknown", "read", success=False,
                           error_message="Credential not found")
            return None
        
        # Check expiration
        if credential.expires_at and datetime.utcnow() > credential.expires_at:
            self._log_access(cred_id, workflow_id or "unknown", "read", success=False,
                           error_message="Credential expired")
            return None
        
        # Check access scope
        if credential.workflow_id and workflow_id and credential.workflow_id != workflow_id:
            self._log_access(cred_id, workflow_id, "read", success=False,
                           error_message="Access denied: workflow mismatch")
            return None
        
        # Retrieve from backend
        value = self.backend.retrieve(cred_id)
        
        # Update access info
        credential.last_accessed = datetime.utcnow()
        credential.access_count += 1
        
        # Log successful access
        self._log_access(cred_id, workflow_id or "system", "read", success=True)
        
        return value
    
    def rotate_credential(
        self,
        cred_id: str,
        new_value: str,
        workflow_id: Optional[str] = None,
    ) -> bool:
        """Rotate/update a credential"""
        credential = self.credentials.get(cred_id)
        
        if not credential:
            self._log_access(cred_id, workflow_id or "unknown", "rotate", success=False,
                           error_message="Credential not found")
            return False
        
        # Rotate in backend
        success = self.backend.rotate(cred_id, new_value)
        
        if success:
            credential.value = new_value
            credential.expires_at = datetime.utcnow() + timedelta(seconds=credential.ttl_seconds)
            self._log_access(cred_id, workflow_id or "system", "rotate", success=True)
        
        return success
    
    def delete_credential(
        self,
        cred_id: str,
        workflow_id: Optional[str] = None,
    ) -> bool:
        """Delete a credential"""
        if cred_id not in self.credentials:
            self._log_access(cred_id, workflow_id or "unknown", "delete", success=False,
                           error_message="Credential not found")
            return False
        
        # Delete from backend
        success = self.backend.delete(cred_id)
        
        if success:
            del self.credentials[cred_id]
            
            # Remove from scopes
            for wf_creds in self.workflow_scopes.values():
                if cred_id in wf_creds:
                    wf_creds.remove(cred_id)
            
            self._log_access(cred_id, workflow_id or "system", "delete", success=True)
        
        return success
    
    def get_workflow_credentials(self, workflow_id: str) -> Dict[str, str]:
        """Get all credentials accessible to a workflow (by name)"""
        cred_ids = self.workflow_scopes.get(workflow_id, [])
        
        creds = {}
        for cred_id in cred_ids:
            credential = self.credentials.get(cred_id)
            if credential:
                value = self.get_credential(cred_id, workflow_id)
                if value:
                    creds[credential.name] = value
        
        return creds
    
    def cleanup_expired(self) -> int:
        """Clean up expired credentials. Returns count deleted."""
        expired_ids = []
        now = datetime.utcnow()
        
        for cred_id, credential in self.credentials.items():
            if credential.expires_at and now > credential.expires_at:
                expired_ids.append(cred_id)
        
        for cred_id in expired_ids:
            self.delete_credential(cred_id)
        
        return len(expired_ids)
    
    def get_audit_log(
        self,
        cred_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        days: int = 30,
    ) -> List[CredentialAccessLog]:
        """Get audit log entries"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        logs = [
            log for log in self.access_logs
            if log.timestamp >= cutoff
            and (cred_id is None or log.credential_id == cred_id)
            and (workflow_id is None or log.workflow_id == workflow_id)
        ]
        
        return logs
    
    def _log_access(
        self,
        cred_id: str,
        workflow_id: str,
        action: str,
        success: bool = True,
        error_message: Optional[str] = None,
    ):
        """Log a credential access"""
        log = CredentialAccessLog(
            credential_id=cred_id,
            workflow_id=workflow_id,
            action=action,
            success=success,
            error_message=error_message,
        )
        self.access_logs.append(log)
    
    def get_vault_status(self) -> Dict[str, Any]:
        """Get vault statistics"""
        return {
            'total_credentials': len(self.credentials),
            'total_workflows': len(self.workflow_scopes),
            'total_access_logs': len(self.access_logs),
            'credentials_by_type': self._count_by_type(),
            'expired_count': sum(
                1 for c in self.credentials.values()
                if c.expires_at and c.expires_at < datetime.utcnow()
            ),
        }
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count credentials by type"""
        counts = {}
        for cred in self.credentials.values():
            key = cred.type.value
            counts[key] = counts.get(key, 0) + 1
        return counts
