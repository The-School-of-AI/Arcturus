import importlib.util
from typing import Dict, Optional, Callable, List, Any
from pathlib import Path
import logging

from marketplace.skill_base import ToolDefinition, MarketplaceSkill, SkillManifest
from marketplace.registry import SkillRegistry

logger = logging.getLogger("bazaar")


class SkillLoader:
    """
    Dynamically loads and manages callable tool functions from marketplace skills.
    
    This is the bridge between the marketplace's static manifests (YAML)
    and the agent's runtime tool execution. It takes ToolDefinitions
    and turns them into actual Python callables.
    """

    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self._loaded_tools: Dict[str, Callable] = {}        # tool_name -> callable function
        self._tool_metadata: Dict[str, ToolDefinition] = {} # tool_name -> tool_metadata
        self._loaded_modules: Dict[str, Any] = {}           # module_path -> imported module (cache)


    def _resolve_module_path(self, skill_dir: Path, module_str: str) -> Path:
        """
        Convert a module string to an absolute file path.
        
        Example:
            skill_dir = Path("marketplace/skills/gmail_reader")
            module_str = "tools.gmail_reader"
            → Path("marketplace/skills/gmail_reader/tools/gmail_reader.py")
        
        Args:
            skill_dir: Root directory of the skill
            module_str: Dot-separated module path from ToolDefinition
            
        Returns:
            Absolute path to the Python file
        """
        # Convert dots to path separators: "tools.gmail_reader" → "tools/gmail_reader"
        relative_path = module_str.replace(".", "/")
        return skill_dir / f"{relative_path}.py"

    def _load_function_from_module(self, module_path: Path, function_name: str) -> Optional[Callable]:
        """
        Dynamically import a Python file and extract a specific function.
        
        Args:
            module_path: Absolute path to the .py file
            function_name: Name of the function to extract
            
        Returns:
            The callable function, or None if not found
        """
        module_path_str = str(module_path)

        # Check cache first
        if module_path_str in self._loaded_modules:
            module = self._loaded_modules[module_path_str]
        else:
            # Dynamic Import
            try: 
                spec = importlib.util.spec_from_file_location(
                    f"marketplace_skill_{module_path.stem}",
                    module_path
                )
                if spec is None or spec.loader is None:
                    logger.error(f"Could not create import spec for: {module_path}")
                    return None

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self._loaded_modules[module_path_str] = module

            except Exception as e:
                logger.error(f"Failed to import module {module_path}: {e}")
                return None

        
        # Extract the function
        func = getattr(module, function_name, None)
        if func is None:
            logger.error(f"Function '{function_name}' not found in {module_path}")
            return None
        
        if not callable(func):
            logger.error(f"Function '{function_name}' in {module_path} is not callable")
            return None

        return func

    def load_skill_tools(self, skill_name: str) -> Dict[str, Callable]:
        """
        Load all callable tools from a registered marketplace skill.
        
        Reads the skill's manifest, resolves each ToolDefinition's module/function
        to an actual Python callable, and caches the result.
        
        Args:
            skill_name: Name of the registered skill
            
        Returns:
            Dict of {tool_name: callable_function}
        """
        manifest = self.registry.get_skill(skill_name)
        if not manifest:
            logger.error(f"Skill '{skill_name}' not found in registry")
            return {}

        skill_dir = self.registry.get_skill_path(skill_name)
        if not skill_dir:
            logger.error(f"No path found for skill '{skill_name}'")
            return {}

        loaded_tools = {}
        for tool_def in manifest.tools:
            # Skip already loaded tools
            if tool_def.name in self._loaded_tools:
                loaded_tools[tool_def.name] = self._loaded_tools[tool_def.name]
                continue

            # Resolve module path and load function
            module_path = self._resolve_module_path(skill_dir, tool_def.module)

            if not module_path.exists():
                logger.error(f"Module file '{module_path}' does not exist for tool '{tool_def.name}'")
                continue
            
            # Load the function
            func = self._load_function_from_module(module_path, tool_def.function)
            if func:
                self._loaded_tools[tool_def.name] = func
                self._tool_metadata[tool_def.name] = tool_def
                loaded_tools[tool_def.name] = func
                logger.info(f"Loaded tool: {tool_def.name} → {tool_def.module}.{tool_def.function}")
            else:
                logger.error(f"Failed to load function '{tool_def.function}' for tool '{tool_def.name}'")

        return loaded_tools

    def load_all_tools(self) -> Dict[str, Callable]:
        """
        Load tools from ALL registered marketplace skills.
        
        Returns:
            Dict of {tool_name: callable_function} across all skills
        """
        all_tools = {}
        for manifest in self.registry.list_skills():
            all_tools.update(self.load_skill_tools(manifest.name))
        return all_tools

    def resolve_tool_call(self, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """
        Find and execute a marketplace tool by name.
        
        This is the main entry point for the agent loop to call
        marketplace skill tools.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Keyword arguments to pass to the tool function
            
        Returns:
            The tool function's return value
            
        Raises:
            KeyError: If tool is not found
            Exception: Whatever the tool function raises
        """
        if arguments is None:
            arguments = {}

        if tool_name not in self._loaded_tools:
            # Try loading all tools first (lazy discovery)
            self.load_all_tools()

        if tool_name not in self._loaded_tools:
            raise KeyError(f"Tool '{tool_name}' not found in Marketplace")
        
        func = self._loaded_tools[tool_name]
        logger.info(f"Executing tool: {tool_name} with arguments: {arguments}")
        return func(**arguments)

    def get_tool_definitions(self) -> List[ToolDefinition]:
        """
        Return ToolDefinitions for all loaded tools.
        
        The agent needs these to know what tools are available
        and what parameters they accept (for the system prompt).
        """
        # Ensure all tools are loaded
        if not self._tool_metadata:
            self.load_all_tools()
        return list(self._tool_metadata.values())

    def get_tool(self, tool_name: str) -> Optional[Callable]:
        """Get a single tool callable by name, or None."""
        return self._loaded_tools.get(tool_name)

    def clear_cache(self):
        """Clear all cached tools and modules (for testing/reloading)."""
        self._loaded_tools.clear()
        self._tool_metadata.clear()
        self._loaded_modules.clear()