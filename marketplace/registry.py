from typing import Dict, List, Optional
from pathlib import Path
import logging

from marketplace.skill_base import SkillManifest, load_manifest

logger = logging.getLogger("bazaar")

class SkillRegistry:
    """
    Registry for discovering and managing marketplace skills.
    
    Unlike core/skills/registry.json (static), this registry
    auto-discovers skills by scanning directories for manifest.yaml files.
    """
    def __init__(self, skills_dir: Optional[Path] = None):
        self._skills: Dict[str, SkillManifest] = {}    # name → manifest
        self._skill_paths: Dict[str, Path] = {}        # name → directory path
        self.skills_dir = skills_dir or Path("marketplace/skills")
        
    def discover_skills(self) -> int:
        """
        Scan the skills directory and register all valid skills

        Returns:
            Numer of skills discovered
        """
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return 0
        
        count = 0
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue 
            manifest_path = skill_dir / "manifest.yaml"
            if not manifest_path.exists():
                continue
            try:
                self.register_skill(skill_dir)
                count += 1
            except Exception as e:
                logger.error(f"Failed to load skill from {skill_dir}: {e}")
        
        logger.info(f"Discovered {count} marketplace skills")
        return count

    def register_skill(self, skill_dir: Path) -> SkillManifest:
        """
        Register a skill from its directory.
        
        Args:
            skill_dir: Path to the skill directory (must contain manifest.yaml)
            
        Returns:
            The loaded SkillManifest
            
        Raises:
            FileNotFoundError: If manifest.yaml doesn't exist
            ValidationError: If manifest is invalid
        """
        manifest_path = skill_dir / "manifest.yaml"
        manifest = load_manifest(manifest_path)

        if manifest.name in self._skills:
            logger.warning(f"Overwriting existing skill: {manifest.name}")

        self._skills[manifest.name] = manifest
        self._skill_paths[manifest.name] = skill_dir
        logger.info(f"Registered skills: {manifest.name} v{manifest.version}")

        return manifest

    def get_skill(self, name: str) -> Optional[SkillManifest]:
        """Get a skill manifest by name."""
        return self._skills.get(name)
    
    def get_skill_path(self, name: str) -> Optional[Path]:
        """Get the directory path for a skill."""
        return self._skill_paths.get(name)
    
    def list_skills(self) -> List[SkillManifest]:
        """Return all registered skill manifests."""
        return list(self._skills.values())
    
    def list_by_category(self, category: str) -> List[SkillManifest]:
        """Return all skills in a given category."""
        return [s for s in self._skills.values() if s.category == category]

    def search_skills(self, query: str) -> List[SkillManifest]:
        """
        Search skills by matching query against name, description, 
        category, and intent triggers.
        
        Args:
            query: Search term (case-insensitive)
            
        Returns:
            List of matching SkillManifests
        """
        query = query.lower()
        return [skill for skill in self._skills.values() 
                if query in skill.name.lower() or 
                query in skill.description.lower() or 
                query in skill.category.lower() or
                any(query in trigger.lower() for trigger in skill.intent_triggers)]

    
    def unregister_skill(self, name: str) -> bool:
        """
        Remove a skill from the registry.
        
        Args:
            name: Skill name to remove
            
        Returns:
            True if skill was removed, False if not found
        """
        if name not in self._skills:
            return False
        
        del self._skills[name]
        del self._skill_paths[name]
        logger.info(f"Unregistered skill: {name}")
        return True

    def get_dependents(self, name: str) -> List[str]:
        """
        Find all skills that depend on the given skill.
        
        This computes the reverse dependency graph dynamically
        by scanning all registered skills' skill_dependencies.
        
        Args:
            name: Skill name to check dependents for
            
        Returns:
            List of skill names that depend on this skill
        """
        dependents = []
        for skill in self._skills.values():
            if name in skill.skill_dependencies:
                dependents.append(skill.name)
        return dependents
    
    def check_dependencies(self, manifest: SkillManifest) -> List[str]:
        """
        Check which of a skill's dependencies are missing from the registry.
        
        Args:
            manifest: The skill manifest to check
            
        Returns:
            List of missing skill dependency names (empty = all satisfied)
        """
        missing = []
        for dep in manifest.skill_dependencies:
            if dep not in self._skills:
                missing.append(dep)
        return missing

    @property
    def count(self) -> int:
        """Number of registered skills."""
        return len(self._skills)
    
    def clear(self):
        """Clear the registry (for testing)."""
        self._skills.clear()
        self._skill_paths.clear()