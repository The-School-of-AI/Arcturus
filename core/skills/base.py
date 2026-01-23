from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from abc import ABC, abstractmethod

class SkillMetadata(BaseModel):
    name: str # e.g. "market_analyst"
    version: str # e.g. "1.0.0" 
    description: str
    author: str
    intent_triggers: List[str] # e.g. ["check stock", "market update"]

class SkillContext(BaseModel):
    """Context passed to the skill at runtime"""
    agent_id: str
    run_id: str
    memory: Dict[str, Any] = {}
    config: Dict[str, Any] = {}

class BaseSkill(ABC):
    def __init__(self, context: SkillContext = None):
        self.context = context or SkillContext(agent_id="system", run_id="init")

    @abstractmethod
    def get_metadata(self) -> SkillMetadata:
        """Return metadata about the skill"""
        pass

    @abstractmethod
    def get_tools(self) -> List[Any]:
        """Return list of tools (functions) this skill provides"""
        pass

    async def on_load(self):
        """Called when the skill is loaded into memory"""
        pass

    async def on_run_start(self, initial_prompt: str) -> str:
        """
        Called before the agent starts. 
        Can modify the effective prompt or set up resources.
        """
        return initial_prompt

    async def on_run_success(self, artifact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Called when the agent successfully finishes a run.
        This is where 'Meaningful Action' happens (e.g. saving a file, sending an email).
        Returns optional metadata to be included in notifications.
        """
        return None

    async def on_run_failure(self, error: str):
        """Called if the run fails"""
        pass
