import subprocess
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
import shutil
import logging

from marketplace.skill_base import load_manifest, SkillManifest
from marketplace.registry import SkillRegistry
from marketplace.integrity import verify_checksum

logger = logging.getLogger("bazaar")

@dataclass
class InstallResult:
    """Result of a skill install or uninstall operation."""
    success: bool
    skill_name: str
    message: str
    missing_deps: List[str] = field(default_factory=list)

class SkillInstaller:
    """
    Manages the full lifecycle of installing and uninstalling marketplace skills.
    """

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def validate_skill(self, source_dir: Path) -> InstallResult:
        """
        Validate a skill package before installation.
        
        Checks:
        1. Directory exists
        2. manifest.yaml exists and is valid
        3. All skill_dependencies are installed
        
        Args:
            source_dir: Path to the skill directory to validate
            
        Returns:
            InstallResult with success=True if valid, or failure details
        """
        # Check directory exists
        if not source_dir.exists() or not source_dir.is_dir():
            return InstallResult(
                success=False,
                skill_name="unknown",
                message=f"Source directory not found: {source_dir}"
            )
        
        # Check manifest exists and is valid
        manifest_path = source_dir / "manifest.yaml"
        try:
            manifest = load_manifest(manifest_path)
        except FileNotFoundError:
            return InstallResult(
                success=False,
                skill_name="unknown",
                message=f"No manifest.yaml found in {source_dir}"
            )
        except Exception as e:
            return InstallResult(
                success=False,
                skill_name="unknown",
                message=f"Invalid manifest: {e}"
            )
        
        # Check skill dependencies
        missing = self.registry.check_dependencies(manifest)
        if missing:
            return InstallResult(
                success=False,
                skill_name=manifest.name,
                message=f"Missing skill dependencies: {missing}",
                missing_deps=missing
            )
        
        # Check integrity (checksum verification)
        if manifest.checksum:
            if not verify_checksum(source_dir):
                return InstallResult(
                    success=False,
                    skill_name=manifest.name,
                    message="SECURITY: Checksum verification failed — skill may have been tampered with"
                )
        
        return InstallResult(
            success=True,
            skill_name=manifest.name,
            message="Validation passed"
        )

    def install_skill(self, source_dir: Path, force: bool = False) -> InstallResult:
        """
        Install a skill from a source directory.

        Steps:
        1. Validate the package
        2. Copy to markerplace/skill/
        3. Install pip dependencies
        4. Register in the registry

        Args:
            source_dir: Path to the skill directory to install
            force: If True, overwrite exising skill with same name

        Returns:
            InstallResult with success status and details
        """
        # Step 1: Validate
        validation = self.validate_skill(source_dir)
        if not validation.success:
            return validation
        
        manifest = load_manifest(source_dir / "manifest.yaml")

        # Check moderation status
        try:
            from marketplace.moderation import ModerationQueue
            mq = ModerationQueue(skills_dir=self.registry.skills_dir)
            if not mq.is_installable(manifest.name):
                status = mq.get_status(manifest.name)
                return InstallResult(
                    success=False,
                    skill_name=manifest.name,
                    message=f"Skill '{manifest.name}' is {status.value} — "
                            f"installation blocked by moderation",
                )
        except Exception as exc:
            logger.warning("Could not check moderation status: %s", exc)

        # Check if already installed
        if self.registry.get_skill(manifest.name) and not force:
            return InstallResult(
                success=False,
                skill_name=manifest.name,
                message=f"Skill '{manifest.name}' is already installed. Use force=True to overwrite."
            )
        
        # Step 2: Copy files to skills directory
        target_dir = self.registry.skills_dir / manifest.name
        try:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(source_dir, target_dir)
        except Exception as e:
            return InstallResult(
                success=False,
                skill_name=manifest.name,
                message=f"Failed to copy skill files: {e}"
            )
        
        # Step 3: Install pip dependencies
        if manifest.dependencies:
            dep_result = self.install_pip_dependencies(manifest.dependencies)
            if not dep_result.success:
                # Rollback: remove copied files
                shutil.rmtree(target_dir, ignore_errors=True)
                return dep_result
        
        # Step 4: Register skill
        try:
            self.registry.register_skill(target_dir)
        except Exception as e:
            # Rollback: remove copied files
            shutil.rmtree(target_dir, ignore_errors=True)
            return InstallResult(
                success=False,
                skill_name=manifest.name,
                message=f"Failed to register skill: {e}"
            )
        
        # Record in version ledger
        try:
            from marketplace.version_manager import VersionManager
            vm = VersionManager(skills_dir=self.registry.skills_dir)
            vm.record_install(manifest.name, manifest.version)
        except Exception as exc:
            logger.warning("Could not record version: %s", exc)

        # Run auto-flag checks
        try:
            from marketplace.moderation import ModerationQueue
            mq = ModerationQueue(skills_dir=self.registry.skills_dir)
            auto_flags = mq.check_and_auto_flag(manifest)
            if auto_flags:
                logger.warning(
                    "Skill '%s' was auto-flagged: %s",
                    manifest.name,
                    [f.reason for f in auto_flags],
                )
        except Exception as exc:
            logger.warning("Could not run auto-flag checks: %s", exc)

        logger.info(f"Successfully installed skill: {manifest.name} v{manifest.version}")
        return InstallResult(
            success=True,
            skill_name=manifest.name,
            message=f"Skill '{manifest.name}' v{manifest.version} installed successfully"
        )
    
    def install_pip_dependencies(self, dependencies: List[str]) -> InstallResult:
        """
        Install pip dependencies for a skill.

        Args:
            dependencies: List of pip package specifiers (e.g. ["requests>=2.0", "beautifulsoup4"])

        Returns:
            InstallResult with success status and details
        """

        if not dependencies:
            return InstallResult(
                success=True,
                skill_name="",
                message="No dependencies to install"
            )   

        try:
            result = subprocess.run(
                ["pip", "install", "-r", "requirements.txt"],
                check=True,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                return InstallResult(
                    success=False,
                    skill_name="",
                    message=f"Failed to install dependencies: {result.stderr}"
                )
            
            logger.info(f"Successfully installed pip dependencies: {dependencies}")
            return InstallResult(
                success=True,
                skill_name="",
                message=f"Successfully installed {len(dependencies)} pip dependencies"
            )
        except subprocess.TimeoutExpired:
            return InstallResult(
                success=False,
                skill_name="",
                message="pip install timed out after 120 seconds"
            )
        
        except FileNotFoundError:
            return InstallResult(
                success=False,
                skill_name="",
                message="pip not found. Please install pip and try again"
            )   

        except Exception as e:
            return InstallResult(
                success=False,
                skill_name="",
                message=f"Failed to install pip dependencies: {e}"
            )   

    def uninstall_skill(self, name: str, force: bool = False) -> InstallResult:
        """
        Uninstall a skill by name.
        
        Steps:
        1. Check if skill exists
        2. Check for dependent skills (warn/block)
        3. Unregister from registry
        4. Delete files from disk
        
        Args:
            name: Skill name to uninstall
            force: If True, uninstall even if other skills depend on it
            
        Returns:
            InstallResult with success status and details
        """
        # Check if skill exists
        manifest = self.registry.get_skill(name)
        if not manifest:
            return InstallResult(
                success=False,
                skill_name=name,
                message=f"Skill '{name}' not found"
            )

        # Check for dependent skills
        dependent_skills = self.registry.get_dependents(name)
        if dependent_skills and not force:
            return InstallResult(
                success=False,
                skill_name=name,
                message=f"Cannot uninstall: these skills depend on '{name}': {dependent_skills}",
                missing_deps=dependent_skills 
            )
        
        # Unregister skill
        self.registry.unregister_skill(name)
        
        # Delete files from disk
        skill_path = self.registry.skills_dir / name
        if skill_path.exists():
            try:
                shutil.rmtree(skill_path)
            except Exception as e:
                logger.error(f"Failed to delete skill files: {e}")
                return InstallResult(
                    success=False,
                    skill_name=name,
                    message=f"Unregistered but failed to delete files: {e}"
                )
        
        # Remove from version ledger
        try:
            from marketplace.version_manager import VersionManager
            vm = VersionManager(skills_dir=self.registry.skills_dir)
            vm.remove(name)
        except Exception as exc:
            logger.warning("Could not clean version ledger: %s", exc)

        logger.info(f"Uninstalled skill: {name}")
        return InstallResult(
            success=True,
            skill_name=name,
            message=f"Successfully uninstalled {name}"
        )
        