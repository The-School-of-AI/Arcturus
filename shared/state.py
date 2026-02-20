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

# RemMe / Vector store instance (provider-agnostic via get_vector_store)
_remme_store = None

def get_remme_store():
    """Get the vector store instance via abstraction layer. Uses get_vector_store()."""
    global _remme_store
    if _remme_store is None:
        import os
        from memory.vector_store import get_vector_store
        # Default to faiss for backward compat; set VECTOR_STORE_PROVIDER=qdrant to use Qdrant
        provider = os.environ.get("VECTOR_STORE_PROVIDER", "faiss")
        _remme_store = get_vector_store(provider=provider)
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

# Global settings state
settings = {}
