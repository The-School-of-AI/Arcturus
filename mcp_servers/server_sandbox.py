import asyncio
import sys
import os
from pathlib import Path

# Fix Path: Add 'Arcturus' to sys.path so we can import 'tools' and 'core'
# Current file: .../Arcturus/mcp_servers/server_sandbox.py
# We want: .../Arcturus/
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# Removed legacy sandbox tool dependency

from mcp.server.fastmcp import FastMCP

from core.sandbox.executor import UniversalSandbox

# Initialize FastMCP server
mcp = FastMCP("sandbox")

@mcp.tool()
async def run_python_script(code: str) -> str:
    """
    Execute Python code in a secure sandbox.
    Use this for math, data processing, and logic.
    Returns the stdout and result of the execution.
    """
    # Disabled recursive MultiMCP to prevent hang
    # from shared.state import get_multi_mcp
    # multi_mcp = get_multi_mcp()
    
    sandbox = UniversalSandbox(multi_mcp=None, session_id="mcp_worker")
    result = await sandbox.run(code)
    
    # Format the output for the agent
    if result.get("status") == "success":
        # Return the 'result' key and logs
        val = result.get("result", "")
        logs = result.get("logs", "")
        out = f"Execution Successful:\nResult: {val}"
        if logs.strip():
            out += f"\nLogs:\n{logs}"
        return out
    else:
        err = result.get("error", "Unknown error")
        trace = result.get("traceback", "")
        out = f"Execution Failed:\n{err}"
        if trace:
            out += f"\nTraceback:\n{trace}"
        return out

if __name__ == "__main__":
    mcp.run(transport="stdio")
