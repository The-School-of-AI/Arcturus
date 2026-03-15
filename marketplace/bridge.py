"""
Bridge between the marketplace subsystem and the core agent loop.

This module provides lazy-initialized access to marketplace components
and the main entry point for resolving marketplace tool calls.
"""
from typing import Dict, Optional, Callable, Any, List
from pathlib import Path
import logging

from marketplace.registry import SkillRegistry
from marketplace.installer import SkillInstaller
from marketplace.loader import SkillLoader
from marketplace.skill_base import ToolDefinition

logger = logging.getLogger("bazaar")

class MarketplaceBridge:
    """
    Single entry point for all marketplace operations.
    
    Combines Registry + Installer + Loader into one coordinated interface.
    The agent loop and API endpoints both talk to this instead of
    managing three separate objects.
    """
    def __init__(self, skills_dir: Optional[Path] = None):
        self.registry = SkillRegistry(skills_dir=skills_dir)
        self.installer = SkillInstaller(registry=self.registry)
        self.loader = SkillLoader(registry=self.registry)
        self._initialized = False

    def initialize(self):
        """Discover installed skills and load their tools."""
        if self._initialized:
            return
        count = self.registry.discover_skills()
        if count > 0:
            self.loader.load_all_tools()
        self._initialized = True
        logger.info(f"Marketplace bridge initialized: {count} skills, {len(self.loader._loaded_tools)} tools")
        
    def resolve_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Optional[Any]:
        """
        Try to resolve a tool call through marketplace skills.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool result if found, None if tool not in marketplace
        """
        self.initialize()  # lazy init
        
        if self.loader.get_tool(tool_name) is None:
            return None  # Not a marketplace tool
        
        return self.loader.resolve_tool_call(tool_name, arguments or {})

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """
        Get tool definitions for all loaded marketplace tools.
        
        Returns:
            List of ToolDefinition objects
        """
        self.initialize()
        return self.loader.get_tool_definitions()

    def refresh(self):
        """Refresh the marketplace."""
        self.loader.clear_cache()
        self._initialized = False
        self.initialize()