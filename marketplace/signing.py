import base64
from pathlib import Path
from typing import Optional, Tuple
import logging

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger("bazaar")

# Key storage directory
KEYS_DIR = Path("marketplace/keys")

def generate_keypair(author_name: str, keys_dir: Path = KEYS_DIR) -> Tuple[Path, Path]:
    """
    Generate an RSA-2048 key pair for a skill author.
    
    Creates two files:
      - {author_name}_private.pem  (KEEP SECRET — used to sign skills)
      - {author_name}_public.pem   (SHARE — used to verify signatures)
    
    Args:
        author_name: Identifier for the author (used in filenames)
        keys_dir: Directory to save keys in
        
    Returns:
        Tuple of (private_key_path, public_key_path)
    """
    keys_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate RSA-2048 private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # Serialize private key to PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Serialize public key to PEM
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # Write to files
    private_path = keys_dir / f"{author_name}_private.pem"
    public_path = keys_dir / f"{author_name}_public.pem"
    
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)
    
    # Set restrictive permissions on private key
    private_path.chmod(0o600)  # Owner read/write only
    
    logger.info(f"Generated RSA-2048 keypair for '{author_name}'")
    logger.info(f"  Private key: {private_path} (KEEP SECRET!)")
    logger.info(f"  Public key:  {public_path} (share this)")
    
    return private_path, public_path

def load_private_key(key_path: Path):
    """Load an RSA private key from a PEM file."""
    return serialization.load_pem_private_key(
        key_path.read_bytes(),
        password=None
    )


def load_public_key(key_path: Path):
    """Load an RSA public key from a PEM file."""
    return serialization.load_pem_public_key(
        key_path.read_bytes()
    )

def sign_checksum(checksum: str, private_key_path: Path) -> str:
    """
    Sign a checksum string with an RSA private key.
    
    We sign the CHECKSUM (not the raw files) because:
    1. The checksum is a fixed-size digest of all files (Day 6)
    2. Signing small data is fast, signing large files is slow
    3. Checksum already covers all file contents
    
    Args:
        checksum: The checksum string (e.g., "sha256:abc123...")
        private_key_path: Path to the author's private key PEM file
        
    Returns:
        Base64-encoded signature string
    """
    private_key = load_private_key(private_key_path)
    
    signature_bytes = private_key.sign(
        checksum.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    # Base64-encode for YAML storage (binary can't go in YAML)
    return base64.b64encode(signature_bytes).decode("utf-8")


def sign_skill(skill_dir: Path, private_key_path: Path) -> str:
    """
    Sign a skill package: compute checksum, sign it, write to manifest.
    
    This is the PUBLISH step — the author calls this before uploading:
      1. Compute checksum
      2. Sign the checksum with private key
      3. Write both checksum + signature into manifest.yaml
    
    Args:
        skill_dir: Path to the skill directory
        private_key_path: Path to the author's private key
        
    Returns:
        The signature string
    """
    import yaml
    from marketplace.integrity import stamp_manifest
    
    # Step 1: Stamp manifest with checksum
    checksum = stamp_manifest(skill_dir)
    
    # Step 2: Sign the checksum
    signature = sign_checksum(checksum, private_key_path)
    
    # Step 3: Write signature into manifest
    manifest_path = skill_dir / "manifest.yaml"
    with open(manifest_path, "r") as f:
        data = yaml.safe_load(f)
    
    data["signature"] = signature
    
    with open(manifest_path, "w") as f:
        yaml.dump(data, f, sort_keys=False, default_flow_style=False)
    
    logger.info(f"Signed skill with RSA signature ({len(signature)} chars)")
    return signature

def verify_signature(checksum: str, signature: str, public_key_path: Path) -> bool:
    """
    Verify that a signature was created by the holder of the private key
    matching the given public key.
    
    Args:
        checksum: The checksum string to verify against
        signature: Base64-encoded signature string
        public_key_path: Path to the author's public key PEM file
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        public_key = load_public_key(public_key_path)
        signature_bytes = base64.b64decode(signature)
        
        public_key.verify(
            signature_bytes,
            checksum.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
        
    except InvalidSignature:
        logger.error("Signature verification FAILED — skill may be forged")
        return False
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False


def verify_skill_signature(skill_dir: Path, public_key_path: Path) -> bool:
    """
    Full verification of a skill: checksum integrity + author signature.
    
    This combines Day 6 (checksum) and Day 7 (signature) into one call:
      1. Verify checksum (files haven't been tampered with)
      2. Verify signature (author is who they claim to be)
    
    Args:
        skill_dir: Path to the skill directory
        public_key_path: Path to the author's public key
        
    Returns:
        True only if BOTH checksum and signature are valid
    """
    import yaml
    from marketplace.integrity import verify_checksum, compute_checksum
    
    # Step 1: Verify checksum (Day 6)
    if not verify_checksum(skill_dir):
        logger.error("Checksum verification failed — files were tampered with")
        return False
    
    # Step 2: Read stored signature
    manifest_path = skill_dir / "manifest.yaml"
    with open(manifest_path, "r") as f:
        data = yaml.safe_load(f)
    
    signature = data.get("signature", "")
    checksum = data.get("checksum", "")
    
    if not signature:
        logger.warning(f"Skill in {skill_dir} has no signature (unsigned)")
        return True  # unsigned skills pass (for now — Day 8 trust policies)
    
    if not checksum:
        logger.error("Skill has signature but no checksum — invalid state")
        return False
    
    # Step 3: Verify signature
    return verify_signature(checksum, signature, public_key_path)