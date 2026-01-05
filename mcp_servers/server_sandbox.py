import asyncio
import sys
import os
from pathlib import Path

# Fix Path: Add 'Arcturus' to sys.path so we can import 'tools' and 'core'
# Current file: .../Arcturus/mcp_servers/server_sandbox.py
# We want: .../Arcturus/
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

# DEBUG
sys.stderr.write(f"DEBUG: Added to path: {root_dir}\n")
sys.stderr.write(f"DEBUG: Contents of root: {os.listdir(root_dir)}\n")
import importlib.util

# Use importlib to avoid conflict with 'mcp_servers.tools'
sandbox_path = root_dir / "tools/sandbox.py"
spec = importlib.util.spec_from_file_location("tools.sandbox", sandbox_path)
sandbox_mod = importlib.util.module_from_spec(spec)
# We need to register it so internal imports (if any) work?
# sandbox.py imports core.utils. 
# We already added root_dir to sys.path so core.utils should work.
spec.loader.exec_module(sandbox_mod)

run_user_code = sandbox_mod.run_user_code

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("sandbox")

@mcp.tool()
async def run_python_script(code: str) -> str:
    """
    Execute Python code in a secure sandbox.
    Use this for math, data processing, and logic.
    Returns the stdout and result of the execution.
    """
    # We pass multi_mcp=None for now, limiting the sandbox to pure Python logic
    # without ability to call other MCP tools recursively.
    result = await run_user_code(code, multi_mcp=None, session_id="mcp_worker")
    
    # Format the output for the agent
    if result.get("status") == "success":
        # Return the 'result' key or raw stdout captured
        val = result.get("result", "")
        return f"Execution Successful:\n{val}"
    else:
        err = result.get("error", "Unknown error")
        return f"Execution Failed:\n{err}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
