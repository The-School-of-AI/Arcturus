"""
marketplace/sdk/publisher.py
----------------------------
End-to-end publish pipeline for Bazaar marketplace skills.

Usage (programmatic):
    from marketplace.sdk.publisher import publish_skill
    result = publish_skill(
        skill_dir=Path("marketplace/skills/weather_fetcher"),
        private_key_path=Path("keys/author.pem"),
    )
    print(result.success)

Usage (CLI):
    python -m marketplace.sdk.cli skill publish weather_fetcher
"""

from __future__ import annotations

import json
import logging
import shutil
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger("bazaar.sdk")

@dataclass
class PublishStep:
    """Result of a single publish pipeline step."""
    name: str
    success: bool
    message: str = ""
    hint: str = ""

@dataclass
class PublishResult:
    """Aggregated result of the publish pipeline."""
    skill_name: str
    steps: List[PublishStep] = field(default_factory=list)
    archive_path: Optional[Path] = None

    @property
    def success(self) -> bool:
        return all(s.success for s in self.steps)

    @property
    def failed_step(self) -> Optional[PublishStep]:
        return next((s for s in self.steps if not s.success), None)

    def _add(self, name: str, success: bool,
             message: str = "", hint: str = "") -> PublishStep:
        step = PublishStep(name=name, success=success,
                           message=message, hint=hint)
        self.steps.append(step)
        return step

def _step_harness(result: PublishResult, skill_dir: Path) -> bool:
    """Step 1: Run the local test harness. Abort if any check fails."""
    from marketplace.sdk.test_harness import run_harness

    report = run_harness(skill_dir)
    if report.passed:
        result._add("harness passes", success=True,
                    message=f"{len(report.results)} check(s) passed")
        return True
    else:
        failures = [r.check for r in report.failed]
        result._add(
            "harness passes",
            success=False,
            message=f"Failed checks: {', '.join(failures)}",
            hint="Run `arcturus skill test <name>` to see details and fix issues.",
        )
        return False

def _step_checksum(result: PublishResult, skill_dir: Path) -> bool:
    """Step 2: Compute SHA-256 checksum of all skill files and write it to manifest."""
    try:
        from marketplace.integrity import stamp_manifest
        checksum = stamp_manifest(skill_dir)
        result._add("checksum stamped", success=True,
                    message=f"sha256:{checksum[:16]}…")
        return True
    except Exception as exc:
        result._add(
            "checksum stamped",
            success=False,
            message=str(exc),
            hint="Ensure marketplace/integrity.py (Day 6) is present.",
        )
        return False

def _step_sign(result: PublishResult, skill_dir: Path,
               private_key_path: Optional[Path]) -> bool:
    """Step 3: Sign the manifest checksum with the author's RSA private key."""
    if private_key_path is None:
        result._add(
            "signature applied",
            success=False,
            message="No private key provided.",
            hint=(
                "Generate a keypair with `arcturus skill keypair` (Day 7), "
                "then pass --key <path> to publish."
            ),
        )
        return False

    try:
        from marketplace.signing import sign_skill
        sign_skill(skill_dir, private_key_path)
        result._add("signature applied", success=True,
                    message=f"signed with {private_key_path.name}")
        return True
    except Exception as exc:
        result._add(
            "signature applied",
            success=False,
            message=str(exc),
            hint="Check that the key file is a valid PEM-encoded RSA private key.",
        )
        return False

def _step_package(result: PublishResult, skill_dir: Path,
                  out_dir: Path) -> Optional[Path]:
    """Step 4: Bundle the skill directory into a .tar.gz archive."""
    skill_name = skill_dir.name
    manifest_path = skill_dir / "manifest.yaml"

    try:
        import yaml
        with open(manifest_path) as f:
            data = yaml.safe_load(f)
        version = data.get("version", "1.0.0")
    except Exception:
        version = "1.0.0"

    archive_name = f"{skill_name}-{version}.tar.gz"
    archive_path = out_dir / archive_name

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(skill_dir, arcname=skill_name)
        size_kb = archive_path.stat().st_size // 1024
        result._add("package created", success=True,
                    message=f"{archive_name} ({size_kb} KB)")
        return archive_path
    except Exception as exc:
        result._add(
            "package created",
            success=False,
            message=str(exc),
        )
        return None

def _step_upload(result: PublishResult, skill_dir: Path,
                 archive_path: Path) -> bool:
    """
    Step 5: Register the skill in the SkillRegistry.
    """
    try:
        from marketplace.registry import SkillRegistry
        registry = SkillRegistry()
        registry.register_skill(skill_dir)
        result._add("uploaded to registry", success=True,
                    message=f"archive: {archive_path.name}")
        return True
    except Exception as exc:
        result._add(
            "uploaded to registry",
            success=False,
            message=str(exc),
            hint="Check that the skill directory and manifest are intact.",
        )
        return False

def publish_skill(
    skill_dir: Path,
    private_key_path: Optional[Path] = None,
    out_dir: Optional[Path] = None,
) -> PublishResult:
    """
    Run the full publish pipeline for a skill.

    Steps (in order, abort on first failure):
      1. harness passes
      2. checksum stamped
      3. signature applied
      4. package created (.tar.gz)
      5. uploaded to registry

    Args:
        skill_dir: Root directory of the skill (must contain manifest.yaml)
        private_key_path: Path to the author's RSA private key (.pem)
        out_dir: Where to write the .tar.gz (default: marketplace/packages/)

    Returns:
        PublishResult with all pipeline steps.
    """
    skill_name = skill_dir.name
    result = PublishResult(skill_name=skill_name)
    out_dir = out_dir or Path("marketplace") / "packages"

    # 1. Harness
    if not _step_harness(result, skill_dir):
        return result

    # 2. Checksum
    if not _step_checksum(result, skill_dir):
        return result

    # 3. Sign
    if not _step_sign(result, skill_dir, private_key_path):
        return result

    # 4. Package
    archive_path = _step_package(result, skill_dir, out_dir)
    if archive_path is None:
        return result
    result.archive_path = archive_path

    # 5. Upload
    _step_upload(result, skill_dir, archive_path)

    return result
