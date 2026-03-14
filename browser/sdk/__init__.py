"""
Phantom Browser Agent SDK

Three primitives for browser automation:
- act(): Single action execution
- extract(): Structured data extraction
- agent(): Multi-step workflow

Plus MCP server for Claude Desktop, Cursor, GitHub Copilot integration.
"""

from .primitives import (
    act,
    extract,
    agent,
    configure_browser,
    SimpleBrowserContext,
    ActionResult,
    ExtractionResult,
    AgentResult,
)

from .mcp_server import (
    MCPServer,
    MCPTool,
    get_mcp_server,
    create_mcp_handler,
)

__all__ = [
    # Primitives
    "act",
    "extract",
    "agent",
    "configure_browser",
    "SimpleBrowserContext",
    "ActionResult",
    "ExtractionResult",
    "AgentResult",
    
    # MCP
    "MCPServer",
    "MCPTool",
    "get_mcp_server",
    "create_mcp_handler",
]
