import os
import json
import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type, Any
from .base import Skill, SkillMetadata

logger = logging.getLogger("skill_manager")

class SkillManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SkillManager, cls).__new__(cls)
            cls._instance.skills_dir = Path("core/skills/library")
            cls._instance.registry_file = Path("core/skills/registry.json")
            cls._instance.skill_classes: Dict[str, Type[Skill]] = {}
        return cls._instance

    def initialize(self):
        """Startup: Scan library and rebuild registry automatically"""
        self._ensure_paths()
        self.scan_and_register()

    def _ensure_paths(self):
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        if not self.registry_file.exists():
            self.registry_file.write_text("{}")

    def scan_and_register(self):
        """
        Auto-Discovery:
        1. Look at every folder in core/skills/library
        2. Try to load 'skill.py'
        3. Register metadata
        """
        registry = {}
        
        # Walk through skill directories
        if not self.skills_dir.exists():
            return

        for item in self.skills_dir.iterdir():
            if item.is_dir():
                skill_file = item / "skill.py"
                
                try:
                    if skill_file.exists():
                        skill_class = self._load_skill_class(skill_file)
                        if skill_class:
                            # Instantiate just to get metadata
                            temp_instance = skill_class()
                            meta = temp_instance.get_metadata()
                            
                            registry[meta.name] = {
                                "path": str(item),
                                "version": meta.version,
                                "description": meta.description,
                                "intent_triggers": meta.intent_triggers,
                                "class_name": skill_class.__name__,
                                "type": "python"
                            }
                            logger.info(f"✅ Discovered Python Skill: {meta.name} (v{meta.version})")
                    
                except Exception as e:
                    logger.error(f"Failed to load skill at {item}: {e}")

        # Save registry
        self.registry_file.write_text(json.dumps(registry, indent=2))
        logger.info(f"Skill Registry Updated. {len(registry)} skills available.")

    def _load_skill_class(self, file_path: Path) -> Optional[Type[Skill]]:
        """Dynamically import a Python file and find the Skill class"""
        spec = importlib.util.spec_from_file_location("dynamic_skill", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, Skill) and obj is not Skill:
                return obj
        return None

    def get_skill(self, skill_name: str) -> Optional[Skill]:
        """Get a fresh instance of a skill, loading its class if necessary"""
        if skill_name in self.skill_classes:
            return self.skill_classes[skill_name]()
        
        # Load from registry
        if not self.registry_file.exists():
            return None
            
        registry = json.loads(self.registry_file.read_text())
        if skill_name not in registry:
            return None
            
        info = registry[skill_name]
        path = Path(info["path"]) / "skill.py"
        
        klass = self._load_skill_class(path)
        if klass:
            self.skill_classes[skill_name] = klass
            return klass()
        return None



    def match_intent(self, user_query: str) -> Optional[str]:
        """Simple keyword matching with word boundaries"""
        import re
        if not self.registry_file.exists():
            return None
            
        registry = json.loads(self.registry_file.read_text())
        user_query = user_query.lower()
        
        for name, info in registry.items():
            for trigger in info.get("intent_triggers", []):
                # Escape trigger for regex safety, then wrap in \b
                pattern = r"\b" + re.escape(trigger.lower()) + r"\b"
                if re.search(pattern, user_query):
                    return name
        return None

skill_manager = SkillManager()

