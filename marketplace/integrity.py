import hashlib
import yaml
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger("bazaar")

def compute_checksum(skill_dir: Path) -> str:
    """
    Compute a SHA-256 checksum of all files in a skill directory.
    
    The checksum covers ALL files (Python, YAML, markdown, etc.)
    but EXCLUDES the 'checksum' field in manifest.yaml itself
    to avoid the chicken-and-egg problem.
    
    Files are processed in sorted order to ensure deterministic output
    across different operating systems and filesystems.
    
    Args:
        skill_dir: Path to the skill directory
        
    Returns:
        Checksum string in format "sha256:<64 hex chars>"
        
    Raises:
        FileNotFoundError: If skill_dir doesn't exist
    """

    if not skill_dir.exists():
        raise FileNotFoundError(f"Skill directory not found: {skill_dir}")

    hasher = hashlib.sha256()

    # Get all files, sorted for determinism
    all_files = sorted(skill_dir.rglob("*"))

    for file_path in all_files:
        if not file_path.is_file():
            continue

        # Skip __pycache__ and .pyc files
        if "__pycache__" in str(file_path) or file_path.suffix == ".pyc":
            continue

        # Include the relative path in hash (detects file renames)
        relative = file_path.relative_to(skill_dir)
        hasher.update(str(relative).encode("utf-8"))

        # manifest.yaml - exclude the checksum field
        if file_path.name == "manifest.yaml":
            content = _get_manifest_content_without_checksum_and_signature(file_path)
        else:
            content = file_path.read_bytes()

        hasher.update(content)

    return f"sha256:{hasher.hexdigest()}"

def _get_manifest_content_without_checksum_and_signature(manifest_path: Path) -> bytes:
    """
    Read manifest.yaml and return its content with the checksum and signature fields removed.
    
    This solves the chicken-and-egg problem: we need to hash the manifest
    to compute the checksum, but the manifest contains the checksum and signature.
    """

    with open(manifest_path, "r") as f:
        data = yaml.safe_load(f)

    if data:
        data_copy = data.copy()
        data_copy.pop("checksum",None)
        data_copy.pop("signature",None)
        return yaml.dump(data_copy, sort_keys=True).encode("utf-8")

    return manifest_path.read_bytes() # only if manifest is empty

def verify_checksum(skill_dir: Path) -> bool:
    """
    Verify that a skill's files match the checksum stored in its manifest.
    
    Args:
        skill_dir: Path to the skill directory
        
    Returns:
        True if checksum matches (or no checksum is set), False if tampered
    """
    manifest_path = skill_dir / "manifest.yaml"
    if not manifest_path.exists():
        logger.warning(f"No manifest.yaml found in {skill_dir}")
        return False

    with open(manifest_path, "r") as f:
        data = yaml.safe_load(f)

    stored_checksum = data.get("checksum", "")

    # No checksum stored - skill is unsigned (allow but warn)
    if not stored_checksum:
        logger.warning(f"Skill in {skill_dir} has no checksum (unsigned)")
        return True 
    
    # Compute and compare 
    actual_checksum = compute_checksum(skill_dir)

    if actual_checksum != stored_checksum:
        logger.error(
            f"CHECKSUM MISMATCH in {skill_dir}!\n"
            f" Expected: {stored_checksum}"
            f" Actual:   {actual_checksum}"
        )
        return False
    
    logger.info(f"Checksum verified for {skill_dir}")
    return True

def stamp_manifest(skill_dir: Path) -> str:
    """
    Compute the checksum and write it into the manifest's checksum field.
    
    This is called during the PUBLISH flow — the author stamps their
    skill before uploading, so the installer can verify later.
    
    Args:
        skill_dir: Path to the skill directory
        
    Returns:
        The computed checksum string
        
    Raises:
        FileNotFoundError: If manifest.yaml doesn't exist
    """
    manifest_path = skill_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    
    # Compute checksum (excludes the checksum field itself)
    checksum = compute_checksum(skill_dir)
    
    # Read current manifest
    with open(manifest_path, "r") as f:
        data = yaml.safe_load(f)
    
    # Write checksum into manifest
    data["checksum"] = checksum
    
    with open(manifest_path, "w") as f:
        yaml.dump(data, f, sort_keys=False, default_flow_style=False)
    
    logger.info(f"Stamped manifest with checksum: {checksum}")
    return checksum
 
