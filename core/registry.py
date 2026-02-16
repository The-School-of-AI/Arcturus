
from typing import Dict, Type, Any, Optional
import logging

logger = logging.getLogger(__name__)

class AgentRegistry:
    """
    Singleton registry for managing available Agent classes dynamically.
    Allows for runtime injection of new agent types without code changes.
    """
    _instance = None
    _agents: Dict[str, Type] = {}
    _descriptions: Dict[str, str] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentRegistry, cls).__new__(cls)
            cls._instance._agents = {}
            cls._instance._descriptions = {}
        return cls._instance

    @classmethod
    def register(cls, name: str, agent_class: Type, description: str = ""):
        """
        Register a new agent class.
        
        Args:
            name: The unique identifier for the agent (e.g. 'PlannerAgent')
            agent_class: The Python class/type of the agent
            description: Optional description for the planner to understand capabilities
        """
        if name in cls._agents:
            logger.warning(f"Overwriting existing agent registration: {name}")
        
        cls._agents[name] = agent_class
        cls._descriptions[name] = description
        logger.info(f"Registered agent: {name}")

    @classmethod
    def get(cls, name: str) -> Optional[Any]:
        """Retrieve an agent class or config by name."""
        return cls._agents.get(name)

    @classmethod
    def get_config(cls, name: str) -> Optional[dict]:
        """Retrieve an agent config. If it's a class, returns its default config (if any)."""
        item = cls._agents.get(name)
        if isinstance(item, dict):
            return item
        # If it's a class, we might need a way to extract its default config
        # For now, let's assume dynamic agents are always dicts.
        return None

    @classmethod
    def list_agents(cls) -> Dict[str, str]:
        """Return a dict of {name: description} for all registered agents."""
        return cls._descriptions.copy()

    @classmethod
    def validate(cls):
        """Ensure critical agents are present."""
        required = ["PlannerAgent", "CoderAgent", "RetrieverAgent"]
        missing = [a for a in required if a not in cls._agents]
        if missing:
            raise KeyError(f"Registry is missing required agents: {missing}")
        logger.info("Agent Registry validated.")

    @classmethod
    def clear(cls):
        """Clear the registry (mostly for testing)."""
        cls._agents.clear()
        cls._descriptions.clear()

# Global accessor
registry = AgentRegistry()
