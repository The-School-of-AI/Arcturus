
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
        
        # Robust path resolution
        base_dir = Path(__file__).parent
        self.cache_path = base_dir.parent / "config" / "mcp_cache.json"
        self._cached_metadata = self._load_cache()
        
        self.server_configs = {
            "browser": {
                "command": "uv",
                "args": ["run", str(base_dir / "server_browser.py")],
            },
            "rag": {
                "command": "uv",
                "args": ["run", str(base_dir / "server_rag.py")],
            },
            "sandbox": {
                "command": "uv",
                "args": ["run", str(base_dir / "server_sandbox.py")],
            },
            "alphavantage": {
                "command": "uvx",
                "args": ["av-mcp", "VXLTQQFJYNCMMPZE"],
            }
        }

    async def _start_server(self, name: str, config: dict):
        """Start a single server with timeout protection"""
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
            
            # Connect with timeout
            async with asyncio.timeout(10): # 10s timeout per server
                read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
                session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                
                # List tools
                if name in self._cached_metadata:
                    print(f"  📦 [cyan]{name}[/cyan] tools loaded from cache.")
                    # Reconstruct Tool objects from dicts
                    cached_tools = []
                    for t_dict in self._cached_metadata[name]:
                        cached_tools.append(Tool(
                            name=t_dict["name"],
                            description=t_dict["description"],
                            inputSchema=t_dict["inputSchema"]
                        ))
                    self.tools[name] = cached_tools
                else:
                    result = await session.list_tools()
                    self.tools[name] = result.tools
                    self._save_to_cache(name, result.tools)
                    print(f"  ✅ [cyan]{name}[/cyan] connected. Tools: {len(result.tools)}")
                
                self.sessions[name] = session

        except TimeoutError:
             print(f"  ⏳ [yellow]{name}[/yellow] timed out during startup.")
        except Exception as e:
            print(f"  ❌ [red]{name}[/red] failed to start: {e}")
        except BaseException as e:
            print(f"  ❌ [red]{name}[/red] CRITICAL FAILURE: {e}")

    async def start(self):
        """Start all configured servers concurrently"""
        print("[bold green]🚀 Starting MCP Servers...[/bold green]")
        
        tasks = []
        for name, config in self.server_configs.items():
            tasks.append(self._start_server(name, config))
        
        await asyncio.gather(*tasks)

    async def stop(self):
        """Stop all servers"""
        print("[bold yellow]🛑 Stopping MCP Servers...[/bold yellow]")
        await self.exit_stack.aclose()

    def get_all_tools(self) -> list:
        """Get all tools from all connected servers"""
        all_tools = []
        for tools in self.tools.values():
            all_tools.extend(tools)
        return all_tools

    async def function_wrapper(self, tool_name: str, *args):
        """Execute a tool using positional arguments by mapping them to schema keys"""
        # Find tool definition
        target_tool = None
        for tools in self.tools.values():
            for tool in tools:
                if tool.name == tool_name:
                    target_tool = tool
                    break
            if target_tool: break
        
        if not target_tool:
            return f"Error: Tool {tool_name} not found"

        # Map positional args to keyword args based on schema
        arguments = {}
        schema = target_tool.inputSchema
        if schema and 'properties' in schema:
            keys = list(schema['properties'].keys())
            for i, arg in enumerate(args):
                if i < len(keys):
                    arguments[keys[i]] = arg
        
        try:
            result = await self.route_tool_call(tool_name, arguments)
            # Unpack CallToolResult
            if hasattr(result, 'content') and result.content:
                return result.content[0].text
            return str(result)
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

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

    def _load_cache(self) -> dict:
        """Load metadata cache from file"""
        if self.cache_path.exists():
            try:
                import json
                return json.loads(self.cache_path.read_text())
            except Exception as e:
                print(f"  ⚠️ Failed to load MCP cache: {e}")
        return {}

    def _save_to_cache(self, server_name: str, tools: list):
        """Save tool metadata to persistent cache"""
        try:
            import json
            # Ensure directory exists
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing
            cache = self._load_cache()
            
            # Update
            tool_list = []
            for t in tools:
                tool_list.append({
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema
                })
            cache[server_name] = tool_list
            
            # Write back
            self.cache_path.write_text(json.dumps(cache, indent=2))
            print(f"  💾 Cached metadata for [cyan]{server_name}[/cyan]")
        except Exception as e:
            print(f"  ⚠️ Failed to save MCP cache for {server_name}: {e}")

    async def refresh_server(self, server_name: str):
        """Force refresh tool metadata for a server"""
        if server_name in self.sessions:
            print(f"  🔄 Refreshing tools for [cyan]{server_name}[/cyan]...")
            result = await self.sessions[server_name].list_tools()
            self.tools[server_name] = result.tools
            self._save_to_cache(server_name, result.tools)
            return True
        return False
