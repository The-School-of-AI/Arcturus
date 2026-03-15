"""Tests for : Digital signatures — author verification using RSA."""
import pytest
from pathlib import Path
from marketplace.signing import (
    generate_keypair,
    sign_checksum,
    verify_signature,
    sign_skill,
    verify_skill_signature,
)
from marketplace.integrity import compute_checksum, stamp_manifest


# --- Helpers ---

def create_skill(base_path: Path, name: str = "test_skill") -> Path:
    """Create a minimal skill directory."""
    skill_dir = base_path / name
    tools_dir = skill_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    
    (skill_dir / "manifest.yaml").write_text(f"""
name: {name}
version: 1.0.0
description: A test skill
checksum: ""
signature: ""
""")
    (tools_dir / "hello.py").write_text('def greet():\n    return "Hello!"')
    return skill_dir


# --- Fixtures ---

@pytest.fixture
def keys(tmp_path):
    """Generate a test keypair and return (private_path, public_path)."""
    keys_dir = tmp_path / "keys"
    return generate_keypair("test_author", keys_dir=keys_dir)


@pytest.fixture
def skill_dir(tmp_path):
    """Create a test skill directory."""
    return create_skill(tmp_path)


# --- Key Generation Tests ---

def test_generate_keypair_creates_files(tmp_path):
    """generate_keypair should create both PEM files."""
    keys_dir = tmp_path / "keys"
    private_path, public_path = generate_keypair("alice", keys_dir=keys_dir)
    
    assert private_path.exists()
    assert public_path.exists()
    assert "alice_private.pem" in str(private_path)
    assert "alice_public.pem" in str(public_path)


def test_private_key_is_pem_format(keys):
    """Private key file should be in PEM format."""
    private_path, _ = keys
    content = private_path.read_text()
    assert "-----BEGIN PRIVATE KEY-----" in content


def test_public_key_is_pem_format(keys):
    """Public key file should be in PEM format."""
    _, public_path = keys
    content = public_path.read_text()
    assert "-----BEGIN PUBLIC KEY-----" in content


# --- Sign + Verify Tests ---

def test_sign_and_verify_checksum(keys):
    """A signature created with the private key should verify with the public key."""
    private_path, public_path = keys
    checksum = "sha256:abc123def456"
    
    signature = sign_checksum(checksum, private_path)
    assert verify_signature(checksum, signature, public_path) is True


def test_verify_fails_with_wrong_checksum(keys):
    """A signature should NOT verify against a different checksum."""
    private_path, public_path = keys
    
    signature = sign_checksum("sha256:original", private_path)
    assert verify_signature("sha256:tampered", signature, public_path) is False


def test_verify_fails_with_wrong_key(tmp_path):
    """A signature should NOT verify with a different author's public key."""
    keys_dir = tmp_path / "keys"
    priv_alice, pub_alice = generate_keypair("alice", keys_dir=keys_dir)
    _, pub_bob = generate_keypair("bob", keys_dir=keys_dir)
    
    # Alice signs
    signature = sign_checksum("sha256:abc123", priv_alice)
    
    # Bob's key can't verify Alice's signature
    assert verify_signature("sha256:abc123", signature, pub_bob) is False


# --- Full Skill Sign + Verify Tests ---

def test_sign_skill_writes_to_manifest(skill_dir, keys):
    """sign_skill should write both checksum and signature into manifest."""
    private_path, _ = keys
    import yaml
    
    sign_skill(skill_dir, private_path)
    
    with open(skill_dir / "manifest.yaml") as f:
        data = yaml.safe_load(f)
    
    assert data["checksum"].startswith("sha256:")
    assert len(data["signature"]) > 0


def test_sign_then_verify_passes(skill_dir, keys):
    """A freshly signed skill should pass full verification."""
    private_path, public_path = keys
    
    sign_skill(skill_dir, private_path)
    assert verify_skill_signature(skill_dir, public_path) is True


def test_verify_fails_after_tampering(skill_dir, keys):
    """Modifying files after signing should fail verification."""
    private_path, public_path = keys
    
    sign_skill(skill_dir, private_path)
    
    # Tamper with a tool file
    (skill_dir / "tools" / "hello.py").write_text("import os; os.system('evil')")
    
    assert verify_skill_signature(skill_dir, public_path) is False


def test_unsigned_skill_passes_verification(skill_dir, keys):
    """A skill with no signature should pass (backward compatibility)."""
    _, public_path = keys
    assert verify_skill_signature(skill_dir, public_path) is True


def test_different_skills_produce_different_signatures(tmp_path, keys):
    """Two different skills should have different signatures."""
    private_path, _ = keys
    
    skill_a = create_skill(tmp_path, "skill_a")
    skill_b = create_skill(tmp_path, "skill_b")
    (skill_b / "tools" / "hello.py").write_text('def greet():\n    return "Bye!"')
    
    sig_a = sign_skill(skill_a, private_path)
    sig_b = sign_skill(skill_b, private_path)
    
    assert sig_a != sig_b