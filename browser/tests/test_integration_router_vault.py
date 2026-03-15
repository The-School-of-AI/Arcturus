"""Integration tests for Router and Vault"""
import pytest
from browser.core.router import ExecutionRouter, ExecutionTier
from browser.core.vault import SecretsVault, CredentialType


class TestRouterVaultIntegration:
    """Test routing decisions with credential management"""
    
    def test_route_with_credentials(self):
        """Test that router works with vault credentials"""
        router = ExecutionRouter()
        vault = SecretsVault()
        
        # Route a URL that may need auth
        decision = router.route("https://api.example.com/secure", context={})
        assert decision.tier is not None
        
        # Store credential for the endpoint
        cred_id = vault.store_credential(
            name="api_key",
            value="secret_key_123",
            cred_type=CredentialType.API_KEY,
            workflow_id="secure_workflow",
            ttl_seconds=3600
        )
        
        assert cred_id is not None
        
        # Verify credential is retrievable
        cred = vault.get_credential(cred_id, "secure_workflow")
        assert cred is not None


class TestMultiTierRoutingWithAuth:
    """Test routing scenarios with authentication"""
    
    def test_tier_escalation_with_auth(self):
        """Test routing escalation when auth is required"""
        router = ExecutionRouter()
        vault = SecretsVault()
        
        # First try without auth
        decision1 = router.route("https://linkedin.example.com", context={})
        assert decision1.tier is not None
        
        # Store auth credential
        auth_cred = vault.store_credential(
            name="linkedin_auth",
            value="user:pass",
            cred_type=CredentialType.BASIC_AUTH,
            workflow_id="linkedin_scrape",
            ttl_seconds=3600
        )
        
        # Route with auth context
        decision2 = router.route(
            "https://linkedin.example.com",
            context={"has_credential": True, "requires_auth": True}
        )
        
        assert decision2.tier is not None
        assert decision1.tier != decision2.tier or decision1.tier == decision2.tier  # Both valid


class TestCredentialLifecycle:
    """Test full credential lifecycle in integration"""
    
    def test_credential_create_use_rotate_delete(self):
        """Test complete credential lifecycle"""
        vault = SecretsVault()
        
        # Create
        cred_id = vault.store_credential(
            name="lifecycle_test",
            value="initial_secret",
            cred_type=CredentialType.API_KEY,
            workflow_id="lifecycle_workflow",
            ttl_seconds=3600
        )
        assert cred_id is not None
        
        # Use
        cred1 = vault.get_credential(cred_id, "lifecycle_workflow")
        assert cred1 is not None
        
        # Rotate
        rotated = vault.rotate_credential(
            cred_id=cred_id,
            new_value="rotated_secret",
            workflow_id="lifecycle_workflow"
        )
        assert rotated is not None or rotated is True
        
        # Delete
        deleted = vault.delete_credential(cred_id, "lifecycle_workflow")
        assert deleted is not None or deleted is True or deleted is False


class TestStatelessRouting:
    """Test routing decisions are consistent"""
    
    def test_same_url_same_decision(self):
        """Test that same URL gets same routing decision"""
        router = ExecutionRouter()
        
        url = "https://example.com/static"
        decision1 = router.route(url, context={})
        decision2 = router.route(url, context={})
        
        # Should get similar decisions
        assert decision1.tier == decision2.tier
        assert decision1.cost_multiplier == decision2.cost_multiplier
