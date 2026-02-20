# Shared State Module
# This module holds global state that is shared across all routers

from pathlib import Path

# Project root for path resolution in routers
PROJECT_ROOT = Path(__file__).parent.parent

# === Lazy-loaded dependencies ===
# These will be initialized when first accessed or during api.py lifespan

# Global state - shared across routers
active_loops = {}

# MCP instance - will be started in api.py lifespan
_multi_mcp = None

def get_multi_mcp():
    """Get the MultiMCP instance, creating it if needed."""
    global _multi_mcp
    if _multi_mcp is None:
        from mcp_servers.multi_mcp import MultiMCP
        _multi_mcp = MultiMCP()
    return _multi_mcp

# RemMe store instance
_remme_store = None

def get_remme_store():
    """Get the RemmeStore instance, creating it if needed."""
    global _remme_store
    if _remme_store is None:
        from remme.store import RemmeStore
        _remme_store = RemmeStore()
    return _remme_store

# RemMe extractor instance
_remme_extractor = None

def get_remme_extractor():
    """Get the RemmeExtractor instance, creating it if needed."""
    global _remme_extractor
    if _remme_extractor is None:
        from remme.extractor import RemmeExtractor
        _remme_extractor = RemmeExtractor()
    return _remme_extractor

# Skill Manager instance
_skill_manager = None

def get_skill_manager():
    """Get the SkillManager instance, creating/initializing it if needed."""
    global _skill_manager
    if _skill_manager is None:
        from core.skills.manager import SkillManager
        _skill_manager = SkillManager()
        _skill_manager.initialize()
    return _skill_manager

# Agent Runner instance
_agent_runner = None

def get_agent_runner():
    """Get the AgentRunner instance, creating it if needed."""
    global _agent_runner
    if _agent_runner is None:
        from agents.base_agent import AgentRunner
        _agent_runner = AgentRunner(get_multi_mcp())
    return _agent_runner

# Studio Storage instance
_studio_storage = None

def get_studio_storage():
    """Get the StudioStorage instance, creating it if needed."""
    global _studio_storage
    if _studio_storage is None:
        from core.studio.storage import StudioStorage
        _studio_storage = StudioStorage()
    return _studio_storage

# Global settings state
settings = {}

# Canvas components
_canvas_ws = None
_canvas_runtime = None

def get_canvas_ws():
    """Get the CanvasWSHandler instance."""
    global _canvas_ws
    if _canvas_ws is None:
        from canvas.ws_handler import CanvasWSHandler
        _canvas_ws = CanvasWSHandler()
    return _canvas_ws

def get_canvas_runtime():
    """Get the CanvasRuntime instance."""
    global _canvas_runtime
    if _canvas_runtime is None:
        from canvas.runtime import CanvasRuntime
        _canvas_runtime = CanvasRuntime(get_canvas_ws())
    return _canvas_runtime
