from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field
from pathlib import Path
import yaml
import logging
logger = logging.getLogger("bazaar")

class ToolDefinition(BaseModel):
    """Schema for a single tool that a marketplace skill provides."""
    name: str                       # eg. "read_inbox"
    description: str                # eg. "Reads the user's inbox"
    module: str                     # eg. "tools.email_reader"
    function: str                   # eg. "read_inbox"
    parameters: Dict[str, Any] = {} # eg. Optional JSON schema for parameters


class SkillManifest(BaseModel):
    """Complete manifest for a marketplace skill package."""    
    name: str                           # Unique skill identifier
    version: str = "1.0.0"              # Semantic version
    description: str = ""               # What does this skill do?
    author: str = "Community"           # Author name
    category: str = "general"           # For marketplace discovery
    permissions: List[str] = []         # Required permissions for this skill
    dependencies: List[str] = []        # pip packages required (e.g. ["google-api-python-client"])
    skill_dependencies: List[str] = []  # other marketplace skills this needs (e.g. ["gmail_reader", "rag"])
    intent_triggers: List[str] = []     # Keywords for auto-matching
    tools: List[ToolDefinition] = []    # Callable tools this skill provides
    checksum: str = ""                  # SHA-256 for tamper detection
    signature: str = ""                 # RSA signature for author verification


class MarketplaceSkill(ABC):
    """
    Base class for marketplace skills.
    """

    def __init__(self, skill_dir: Optional[Path] =None):
        self.skill_dir = skill_dir
        self._manifest: Optional[SkillManifest] = None
    
    @property
    @abstractmethod
    def prompt_text(self) -> str:
        """Return the raw prompt text associated with this skill (if any)."""
        ...
    
    def get_manifest(self) -> Optional[SkillManifest]:
        """Load manifest.yaml from the skill directory if it exists."""
        if self._manifest:
            return self._manifest
        if self.skill_dir:
            manifest_path = self.skill_dir / "manifest.yaml"
            if manifest_path.exists():
                self._manifest = load_manifest(manifest_path)
        return self._manifest
        

    def get_tools(self) -> List[ToolDefinition]:
        """Return list of definitions from the manifest."""
        manifest = self.get_manifest()
        return manifest.tools if manifest else []   

    def get_callable_tools(self) -> Dict[str, Callable]:
        """
        Return actual callable Python functions.
        
        Override this in your skill to return real functions:
        {
            "read_inbox": gmail_reader.read_inbox,
            "send_email": gmail_sender.send_email,
        }
        """
        return {}

    def on_activate(self):
        """Called when the skill is installed/activated."""
        pass
    
    def on_deactivate(self):
        """Called when the skill is uninstalled/deactivated."""
        pass


def load_manifest(manifest_path: Path) -> SkillManifest:
    """
    Load and validate a manifest.yaml file.
    
    Args:
        manifest_path: Path to the manifest.yaml file
        
    Returns:
        Validated SkillManifest object
        
    Raises:
        FileNotFoundError: If manifest.yaml doesn't exist
        ValidationError: If manifest has invalid/missing fields
    """
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    
    with open(manifest_path, 'r') as f:
        data = yaml.safe_load(f)
    
    if not data:
        raise ValueError(f"Empty manifest: {manifest_path}")
    
    return SkillManifest(**data)