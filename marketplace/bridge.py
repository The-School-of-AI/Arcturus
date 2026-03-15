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
from marketplace.trust import TrustPolicy, TrustLevel
from marketplace.sandbox import SandboxedExecutor
from marketplace.abuse import AbuseController

logger = logging.getLogger("bazaar")

class MarketplaceBridge:
    """
    Single entry point for all marketplace operations.
    
    Combines Registry + Installer + Loader into one coordinated interface.
    The agent loop and API endpoints both talk to this instead of
    managing three separate objects.
    """
    def __init__(self, skills_dir: Optional[Path] = None, trust_policy: Optional[TrustPolicy] = None):
        # We need a resolved Path so we can pass it consistently
        actual_skills_dir = skills_dir or Path("marketplace/skills").resolve()
        
        self.registry = SkillRegistry(skills_dir=actual_skills_dir)
        self.installer = SkillInstaller(registry=self.registry)
        self.loader = SkillLoader(registry=self.registry)
        self.policy = trust_policy or TrustPolicy()
        self.executor = SandboxedExecutor()
        self.abuse = AbuseController(skills_dir=actual_skills_dir)
        self._initialized = False

    def initialize(self):
        """Discover installed skills and load their tools."""
        if self._initialized:
            return
        count = self.registry.discover_skills()
        if count > 0:
            self.loader.load_all_tools()
            # Register each skill's permissions with the executor
            for manifest in self.registry.list_skills():
                self.executor.register_skill_permissions(
                    manifest.name, manifest.permissions
                )
        self._initialized = True
        logger.info(f"Marketplace bridge initialized: {count} skills, {len(self.loader._loaded_tools)} tools")

    def check_policy(self, manifest, skill_dir=None, public_key_path=None):
        """Evaluate a skill against the trust policy before install."""
        return self.policy.evaluate(manifest, skill_dir, public_key_path)

    def _find_skill_for_tool(self, tool_name: str) -> Optional[str]:
        """Helper to find which skill owns a specific tool."""
        self.initialize()
        for manifest in self.registry.list_skills():
            for tool in manifest.tools:
                if tool.name == tool_name:
                    return manifest.name
        return None
        
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
            
        skill_name = self._find_skill_for_tool(tool_name)
        if skill_name:
            self.abuse.pre_call_check(skill_name, tool_name)
        
        try:
            result = self.loader.resolve_tool_call(tool_name, arguments or {})
            if skill_name:
                self.abuse.record_success(skill_name, tool_name)
            return result
        except Exception as e:
            if skill_name:
                self.abuse.record_error(skill_name, tool_name, str(e))
            raise

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
        self.executor.clear()
        self._initialized = False
        self.initialize()