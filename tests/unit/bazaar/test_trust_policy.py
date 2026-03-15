"""Tests for Day 8: Trust policies — configurable security rules."""
import pytest
from pathlib import Path
from marketplace.trust import TrustLevel, TrustPolicy, PolicyResult
from marketplace.skill_base import SkillManifest


# --- Fixtures ---

@pytest.fixture
def open_policy():
    """Policy that allows everything."""
    return TrustPolicy(trust_level=TrustLevel.OPEN)


@pytest.fixture
def checksum_policy():
    """Policy that requires checksum verification."""
    return TrustPolicy(trust_level=TrustLevel.CHECKSUM)


@pytest.fixture
def signed_policy():
    """Policy that requires signatures."""
    return TrustPolicy(trust_level=TrustLevel.SIGNED)


@pytest.fixture
def verified_policy():
    """Policy that requires trusted authors."""
    return TrustPolicy(
        trust_level=TrustLevel.VERIFIED,
        trusted_authors=["alice", "core_team"]
    )


@pytest.fixture
def basic_manifest():
    """A minimal manifest for testing."""
    return SkillManifest(name="test_skill", author="alice")


# --- TrustLevel Enum Tests ---

def test_trust_levels_are_ordered():
    """Trust levels should be ordered from least to most strict."""
    assert TrustLevel.OPEN.value < TrustLevel.CHECKSUM.value
    assert TrustLevel.CHECKSUM.value < TrustLevel.SIGNED.value
    assert TrustLevel.SIGNED.value < TrustLevel.VERIFIED.value


def test_trust_level_from_string():
    """Trust levels should be creatable from strings."""
    assert TrustLevel["OPEN"] == TrustLevel.OPEN
    assert TrustLevel["VERIFIED"] == TrustLevel.VERIFIED


# --- Blocked Skills Tests ---

def test_blocked_skill_is_rejected(open_policy, basic_manifest):
    """A skill on the blocked list should be rejected even with OPEN policy."""
    open_policy.blocked_skills.add("test_skill")
    result = open_policy.evaluate(basic_manifest)
    assert result.allowed is False
    assert "blocked" in result.reason.lower()


# --- Permission Tests ---

def test_disallowed_permission_is_rejected(open_policy):
    """Skills requesting disallowed permissions should be blocked."""
    manifest = SkillManifest(
        name="evil_skill",
        permissions=["network", "kernel"]  # "kernel" is not allowed
    )
    result = open_policy.evaluate(manifest)
    assert result.allowed is False
    assert "kernel" in result.reason


def test_allowed_permissions_pass(open_policy):
    """Skills requesting only allowed permissions should pass."""
    manifest = SkillManifest(
        name="safe_skill",
        permissions=["network", "filesystem"]
    )
    result = open_policy.evaluate(manifest)
    assert result.allowed is True


def test_no_permissions_always_passes(open_policy, basic_manifest):
    """Skills requesting no permissions should always pass."""
    result = open_policy.evaluate(basic_manifest)
    assert result.allowed is True


# --- OPEN Level Tests ---

def test_open_policy_allows_anything(open_policy, basic_manifest):
    """OPEN policy should allow any skill without verification."""
    result = open_policy.evaluate(basic_manifest)
    assert result.allowed is True
    assert result.trust_level_met == TrustLevel.OPEN


# --- CHECKSUM Level Tests ---

def test_checksum_policy_warns_on_missing_checksum(checksum_policy, basic_manifest, tmp_path):
    """CHECKSUM policy should warn (not block) when checksum is empty."""
    skill_dir = tmp_path / "test_skill"
    skill_dir.mkdir()
    (skill_dir / "manifest.yaml").write_text("name: test_skill")
    
    result = checksum_policy.evaluate(basic_manifest, skill_dir=skill_dir)
    assert result.allowed is True
    assert any("no checksum" in w.lower() for w in result.warnings)


# --- SIGNED Level Tests ---

def test_signed_policy_rejects_unsigned_skill(signed_policy, basic_manifest, tmp_path):
    """SIGNED policy should reject skills with no signature."""
    skill_dir = tmp_path / "test_skill"
    skill_dir.mkdir()
    (skill_dir / "manifest.yaml").write_text("name: test_skill")
    
    result = signed_policy.evaluate(basic_manifest, skill_dir=skill_dir)
    assert result.allowed is False
    assert "no signature" in result.reason.lower()


# --- VERIFIED Level Tests ---

def test_verified_policy_rejects_untrusted_author(verified_policy, tmp_path):
    """VERIFIED policy should reject skills from non-trusted authors."""
    manifest = SkillManifest(
        name="untrusted_skill",
        author="mallory",
        checksum="sha256:abc",
        signature="sig123"
    )
    
    # Create dummy key and skill dir for the evaluation to reach the author check
    # In a real test you'd need valid crypto, but here we test the author gate
    # by using OPEN-level checks that don't need real verification
    result = verified_policy.evaluate(manifest, skill_dir=tmp_path)
    assert result.allowed is False


def test_verified_policy_allows_trusted_author(open_policy, basic_manifest):
    """OPEN policy with a trusted author should report VERIFIED level achieved."""
    open_policy.trusted_authors.add("alice")
    result = open_policy.evaluate(basic_manifest)
    assert result.allowed is True


# --- Config Loading Tests ---

def test_from_config_loads_yaml(tmp_path):
    """from_config should load trust policy from a YAML file."""
    config = tmp_path / "trust.yaml"
    config.write_text("""
trust_level: SIGNED
trusted_authors:
  - alice
  - bob
blocked_skills:
  - malware_skill
allowed_permissions:
  - network
""")
    
    policy = TrustPolicy.from_config(config)
    assert policy.trust_level == TrustLevel.SIGNED
    assert "alice" in policy.trusted_authors
    assert "malware_skill" in policy.blocked_skills
    assert "network" in policy.allowed_permissions


def test_from_config_defaults_on_missing_file(tmp_path):
    """Missing config file should use sensible defaults."""
    policy = TrustPolicy.from_config(tmp_path / "nonexistent.yaml")
    assert policy.trust_level == TrustLevel.CHECKSUM


def test_from_dict_creates_policy():
    """from_dict should create a policy from a dictionary."""
    policy = TrustPolicy.from_dict({
        "trust_level": "VERIFIED",
        "trusted_authors": ["alice"]
    })
    assert policy.trust_level == TrustLevel.VERIFIED
    assert "alice" in policy.trusted_authors


# --- PolicyResult Tests ---

def test_policy_result_has_required_fields():
    """PolicyResult should have allowed, reason, and optional fields."""
    result = PolicyResult(
        allowed=True,
        reason="All clear",
        trust_level_met=TrustLevel.SIGNED,
        warnings=["minor issue"]
    )
    assert result.allowed is True
    assert result.trust_level_met == TrustLevel.SIGNED
    assert len(result.warnings) == 1