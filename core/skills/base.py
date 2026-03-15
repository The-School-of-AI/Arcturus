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

class SkillContext(BaseModel):
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    config: Dict[str, Any] = {}


class Skill(ABC):
    name: str = "base_skill"
    description: str = "Base skill description"

    def __init__(self, config: Optional[SkillConfig] = None):
        self.config = config or SkillConfig()
        self.context = SkillContext()

    @property
    def prompt_text(self) -> str:
        """Return the raw prompt text associated with this skill (if any)."""
        return ""

    def get_system_prompt_additions(self) -> str:
        """Return text to begin appended to the system prompt."""
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

    def on_run_failure(self, error: Any = None):
        """Called when a run using this skill fails."""
        pass

    def on_run_success(self, result: Any = None):
        """Called when a run using this skill succeeds."""
        pass

# Alias for compatibility
BaseSkill = Skill
