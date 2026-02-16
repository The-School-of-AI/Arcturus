from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class SkillMetadata(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str
    author: str = "Community"
    intent_triggers: List[str] = []

class SkillConfig(BaseModel):
    enabled: bool = True
    params: Dict[str, Any] = {}

class Skill(ABC):
    name: str = "base_skill"
    description: str = "Base skill description"
    
    def __init__(self, config: Optional[SkillConfig] = None):
        self.config = config or SkillConfig()

    @property
    def prompt_text(self) -> str:
        """Return the raw prompt text associated with this skill (if any)."""
        return ""

    def get_system_prompt_additions(self) -> str:
        """Return text to begin appended to the system prompt."""
        # For compatibility with older skills that define on_run_start
        if hasattr(self, 'on_run_start'):
            # Note: old on_run_start took 'initial_prompt'. 
            # We might need to handle this carefully if it expects it.
            # But most just return a string to append.
            return ""
        return ""

    def get_tools(self) -> List[Any]:
        """Return list of tools (functions or schemas) this skill provides."""
        return []

    def get_metadata(self) -> SkillMetadata:
        """Helper to return metadata for registry."""
        return SkillMetadata(
            name=self.name,
            description=self.description
        )

    def on_activate(self):
        """Called when skill is activated."""
        pass

    def on_deactivate(self):
        """Called when skill is deactivated."""
        pass

# Alias for compatibility
BaseSkill = Skill


