
import asyncio
import sys
import shutil
from pathlib import Path
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool
from rich import print

class MultiMCP:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.sessions = {}  # server_name -> session
        self.tools = {}     # server_name -> [Tool]
        self.server_configs = {
            "browser": {
                "command": "uv",
                "args": ["run", "16_NetworkX/mcp_servers/server_browser.py"],
            },
            "rag": {
                "command": "uv",
                "args": ["run", "16_NetworkX/mcp_servers/server_rag.py"],
            }
        }

    async def start(self):
        """Start all configured servers"""
        print("[bold green]🚀 Starting MCP Servers...[/bold green]")
        
        for name, config in self.server_configs.items():
            try:
                # Check if uv exists, else fallback to python
                cmd = config["command"]
                if cmd == "uv" and not shutil.which("uv"):
                    cmd = sys.executable
                    args = [config["args"][1]] # just the script path
                else:
                    args = config["args"]

                server_params = StdioServerParameters(
                    command=cmd,
                    args=args,
                    env=None 
                )
                
                # Connect
                read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
                session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                
                # List tools
                result = await session.list_tools()
                self.sessions[name] = session
                self.tools[name] = result.tools
                
                print(f"  ✅ [cyan]{name}[/cyan] connected. Tools: {len(result.tools)}")
                
            except Exception as e:
                print(f"  ❌ [red]{name}[/red] failed to start: {e}")

    async def stop(self):
        """Stop all servers"""
        print("[bold yellow]🛑 Stopping MCP Servers...[/bold yellow]")
        await self.exit_stack.aclose()

    def get_tools_from_servers(self, server_names: list) -> list:
        """Get flattened list of tools from requested servers"""
        all_tools = []
        for name in server_names:
            if name in self.tools:
                all_tools.extend(self.tools[name])
        return all_tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        """Call a tool on a specific server"""
        if server_name not in self.sessions:
            raise ValueError(f"Server '{server_name}' not connected")
        
        return await self.sessions[server_name].call_tool(tool_name, arguments)

    # Helper to route tool call by finding which server has it
    async def route_tool_call(self, tool_name: str, arguments: dict):
        for name, tools in self.tools.items():
            for tool in tools:
                if tool.name == tool_name:
                    return await self.call_tool(name, tool_name, arguments)
        raise ValueError(f"Tool '{tool_name}' not found in any server")
