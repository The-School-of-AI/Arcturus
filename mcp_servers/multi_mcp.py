
import asyncio
import sys
import shutil
import json
import os
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
        self.server_pids = {} # server_name -> PID
        
        from collections import defaultdict
        self.active_calls = defaultdict(int) # server_name -> count
        
        # Robust path resolution
        self.base_dir = Path(__file__).parent
        self.config_path = self.base_dir / "mcp_config.json"
        
        # Metadata Cache (for tools)
        self.cache_path = self.base_dir.parent / "config" / "mcp_cache.json"
        self._cached_metadata = self._load_cache()
        
        self.server_configs = self._load_config()
        
        # Background task for lifecycle management (to avoid anyio task mismatch)
        self._command_queue = asyncio.Queue()
        self._manager_task = None
        
        # Disabled tools cache
        self.disabled_tools = set() # { "server:tool" }
        self.disabled_tools_path = self.base_dir.parent / "config" / "disabled_tools.json"
        self._load_disabled_tools()

    def _load_config(self) -> dict:
        """Load server configuration from JSON"""
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text())
            except Exception as e:
                print(f"⚠️ Failed to load MCP config: {e}")
        return {}

    def _save_config(self):
        """Save current server configuration"""
        try:
            self.config_path.write_text(json.dumps(self.server_configs, indent=2))
        except Exception as e:
            print(f"⚠️ Failed to save MCP config: {e}")

    def _load_disabled_tools(self):
        if self.disabled_tools_path.exists():
            try:
                data = json.loads(self.disabled_tools_path.read_text())
                self.disabled_tools = set(data)
            except: pass

    def _save_disabled_tools(self):
        self.disabled_tools_path.write_text(json.dumps(list(self.disabled_tools)))
        
    def set_tool_state(self, server_name: str, tool_name: str, enabled: bool):
        key = f"{server_name}:{tool_name}"
        if enabled:
            if key in self.disabled_tools:
                self.disabled_tools.remove(key)
                self._save_disabled_tools()
        else:
            self.disabled_tools.add(key)
            self._save_disabled_tools()

    async def add_server(self, name: str, config: dict):
        """Dynamically add a new server via the lifecycle manager"""
        if name in self.sessions:
            raise ValueError(f"Server '{name}' already exists")
        
        self.server_configs[name] = config
        self._save_config()
        
        # Send command to background task and wait for result
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        await self._command_queue.put(("ADD_SERVER", (name, config), future))
        
        result = await future
        if isinstance(result, Exception):
            raise result
        return result

    async def remove_server(self, name: str):
        """Remove a server"""
        try:
            if name in self.server_configs:
                del self.server_configs[name]
                self._save_config()
            
            # Remove from active sessions/tools regardless of config presence
            if name in self.sessions:
                print(f"  🗑️ Removed server '{name}' from sessions")
                del self.sessions[name]
                
            if name in self.server_pids:
                del self.server_pids[name]
                
            if name in self.tools:
                del self.tools[name]
                
            return True
        except Exception as e:
            print(f"  ⚠️ Error removing server {name}: {e}")
            return True

    async def _start_server(self, name: str, config: dict):
        """Start a single server with timeout protection"""
        if config.get("enabled", True) is False:
            print(f"  ⏭️ [dim]Server '{name}' is disabled in config. Skipping.[/dim]")
            return False

        try:
            cmd = config.get("command", "uv")
            args = list(config.get("args", [])) 
            server_type = config.get("type", "local-script")
            env = config.get("env", None) 

            if server_type == "local-script":
                script_name = args[-1]
                if not Path(script_name).is_absolute() and (self.base_dir / script_name).exists():
                     script_path = str(self.base_dir / script_name)
                     args = args[:-1] + [script_path]

            elif server_type == "stdio-git":
                repo_url = config.get("source")
                if not repo_url:
                    raise ValueError("Missing 'source' (git url) for stdio-git server")
                
                server_dir = self.base_dir.parent / "data" / "mcp_repos" / name
                server_dir.parent.mkdir(parents=True, exist_ok=True)
                
                if not server_dir.exists():
                     print(f"  ⬇️ Cloning {name} from {repo_url}...")
                     proc = await asyncio.create_subprocess_exec(
                         "git", "clone", repo_url, str(server_dir),
                         stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                     )
                     await proc.communicate()
                     if proc.returncode != 0:
                         raise RuntimeError(f"Git clone failed for {name}")

                cmd = "uv"
                if "run" in args:
                     try:
                         run_idx = args.index("run")
                         args.insert(run_idx + 1, "--directory")
                         args.insert(run_idx + 2, str(server_dir))
                         
                         req_file = server_dir / "requirements.txt"
                         if req_file.exists():
                             args.insert(run_idx + 3, "--with-requirements")
                             args.insert(run_idx + 4, str(req_file))
                             print(f"  📦 Detected requirements.txt for {name}, auto-installing dependencies...")
                         
                         script_arg_idx = -1
                         current_script = args[script_arg_idx]
                         script_path = server_dir / current_script
                         if not script_path.exists():
                             print(f"  ⚠️ Configured script '{current_script}' not found in {name}. Attempting auto-detection...")
                             candidates = list(server_dir.glob("*_mcp_server.py")) + \
                                          list(server_dir.glob("server.py")) + \
                                          list(server_dir.glob("src/server.py")) + \
                                          list(server_dir.glob("*.py"))
                             best_candidate = None
                             for c in candidates:
                                 if "mcp_server" in c.name or c.name == "server.py":
                                     best_candidate = c
                                     break
                             if not best_candidate and candidates:
                                 best_candidate = candidates[0]
                             if best_candidate:
                                 new_script = str(best_candidate.relative_to(server_dir))
                                 args[script_arg_idx] = new_script
                                 print(f"  ✅ Auto-detected entry point: {new_script}")
                             else:
                                 print(f"  [ERROR] Could not auto-detect entry point for {name}")
                     except ValueError:
                         pass
            
            final_env = os.environ.copy()
            if env:
                final_env.update(env)

            server_params = StdioServerParameters(
                command=cmd,
                args=args,
                env=final_env
            )
            
            import psutil
            parent_proc = psutil.Process()
            children_before = set(p.pid for p in parent_proc.children(recursive=False))

            async with asyncio.timeout(20):
                read, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
                
                children_after = set(p.pid for p in parent_proc.children(recursive=False))
                new_pids = children_after - children_before
                if new_pids:
                    pid = list(new_pids)[0]
                    self.server_pids[name] = pid
                    print(f"  🆔 Server '{name}' started with PID: {pid}")
                
                session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                
                if name in self._cached_metadata:
                    print(f"  📦 [cyan]{name}[/cyan] tools loaded from cache.")
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
                    print(f"  [DONE] [cyan]{name}[/cyan] connected. Tools: {len(result.tools)}")
                
                self.sessions[name] = session
                return True

        except asyncio.TimeoutError:
             print(f"  [TIMEOUT] [yellow]{name}[/yellow] timed out during startup.")
        except Exception as e:
            print(f"  [ERROR] [red]{name}[/red] failed to start: {e}")
        return False

    async def start(self):
        """Start the lifecycle manager task"""
        if self._manager_task and not self._manager_task.done():
            return
            
        print("[bold green][START] Starting MCP Lifecycle Manager...[/bold green]")
        self._manager_task = asyncio.create_task(self._lifecycle_manager())
        await asyncio.sleep(0.1)

    async def _lifecycle_manager(self):
        """Background task that owns the AsyncExitStack to ensure task consistency"""
        try:
            async with self.exit_stack:
                print("  ⚙️ MCP Manager task entered Stack context.")
                
                # Start initial servers
                for name, config in self.server_configs.items():
                    if config.get("enabled", True):
                        await self._start_server(name, config)
                    else:
                        print(f"  ⏭️ [dim]Skipping disabled server: {name}[/dim]")
                
                # Command loop
                while True:
                    cmd, data, future = await self._command_queue.get()
                    try:
                        if cmd == "STOP":
                            if not future.done(): future.set_result(True)
                            self._command_queue.task_done()
                            break
                        elif cmd == "ADD_SERVER":
                            name, config = data
                            success = await self._start_server(name, config)
                            if not future.done(): future.set_result(success)
                    except Exception as e:
                        print(f"  ⚠️ Error in MCP Manager loop: {e}")
                        if not future.done(): future.set_result(e)
                    finally:
                        self._command_queue.task_done()
                        
        except Exception as e:
            print(f"  ❌ CRITICAL: MCP Lifecycle Manager failed: {e}")
        finally:
            print("  ✅ MCP Manager task exited Stack context.")

    async def stop(self):
        """Stop the manager task (triggering aclose on all sessions)"""
        if self._manager_task and not self._manager_task.done():
            print("[bold yellow]🛑 Stopping MCP Lifecycle Manager...[/bold yellow]")
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            await self._command_queue.put(("STOP", None, future))
            await future
            await self._manager_task
            self._manager_task = None
        elif self._manager_task is None:
            await self.exit_stack.aclose()

    def get_all_tools(self) -> list:
        all_tools = []
        for tools in self.tools.values():
            all_tools.extend(tools)
        return all_tools
    
    def get_connected_servers(self) -> list:
        return list(self.sessions.keys())

    async def function_wrapper(self, tool_name: str, *args):
        target_tool = None
        for tools in self.tools.values():
            for tool in tools:
                if tool.name == tool_name:
                    target_tool = tool
                    break
            if target_tool: break
        
        if not target_tool:
            return f"Error: Tool {tool_name} not found"

        arguments = {}
        schema = target_tool.inputSchema
        if schema and 'properties' in schema:
            keys = list(schema['properties'].keys())
            for i, arg in enumerate(args):
                if i < len(keys):
                    arguments[keys[i]] = arg
        
        try:
            result = await self.route_tool_call(tool_name, arguments)
            if hasattr(result, 'content') and result.content:
                return result.content[0].text
            return str(result)
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    def get_tools_from_servers(self, server_names: list) -> list:
        all_tools = []
        for name in server_names:
            if name in self.tools:
                for tool in self.tools[name]:
                    key = f"{name}:{tool.name}"
                    if key not in self.disabled_tools:
                        all_tools.append(tool)
        return all_tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict):
        if server_name not in self.sessions:
            raise ValueError(f"Server '{server_name}' not connected")
        
        self.active_calls[server_name] += 1
        try:
            return await self.sessions[server_name].call_tool(tool_name, arguments)
        finally:
            self.active_calls[server_name] -= 1

    async def drain_server(self, name: str, timeout: float = 30.0) -> bool:
        if self.active_calls[name] == 0:
            return True
        start_time = asyncio.get_running_loop().time()
        while self.active_calls[name] > 0:
            if asyncio.get_running_loop().time() - start_time > timeout:
                return False
            await asyncio.sleep(0.5)
        return True

    async def route_tool_call(self, tool_name: str, arguments: dict):
        from core.circuit_breaker import get_breaker, CircuitOpenError
        breaker = get_breaker(tool_name, failure_threshold=5, recovery_timeout=60.0)
        if not breaker.can_execute():
            status = breaker.get_status()
            raise CircuitOpenError(f"Circuit open for '{tool_name}' - service failing. Retry in {status['time_until_retry']:.0f}s")
        
        try:
            for name, tools in self.tools.items():
                for tool in tools:
                    if tool.name == tool_name:
                        result = await self.call_tool(name, tool_name, arguments)
                        breaker.record_success()
                        return result
            raise ValueError(f"Tool '{tool_name}' not found in any server")
        except CircuitOpenError:
            raise
        except Exception as e:
            breaker.record_failure()
            raise

    def _load_cache(self) -> dict:
        if self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text())
            except Exception: pass
        return {}

    def _save_to_cache(self, server_name: str, tools: list):
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache = self._load_cache()
            tool_list = []
            for t in tools:
                tool_list.append({"name": t.name, "description": t.description, "inputSchema": t.inputSchema})
            cache[server_name] = tool_list
            self.cache_path.write_text(json.dumps(cache, indent=2))
        except Exception: pass

    async def refresh_server(self, server_name: str):
        if server_name in self.sessions:
            result = await self.sessions[server_name].list_tools()
            self.tools[server_name] = result.tools
            self._save_to_cache(server_name, result.tools)
            return True
        return False
        
    def get_server_readme(self, server_name: str) -> str:
        config = self.server_configs.get(server_name)
        if not config: return None
        repo_path = None
        if config.get("type") == "stdio-git":
             repo_path = self.base_dir.parent / "data" / "mcp_repos" / server_name
        elif config.get("type") == "local-script":
             repo_path = self.base_dir
        if repo_path:
            candidates = [f"README_{server_name}.md", f"docs/README_{server_name}.md", "README.md", "README.txt", "README"]
            for name in candidates:
                p = repo_path / name
                if p.exists(): return p.read_text(encoding="utf-8", errors="replace")
        return None

    def list_active_servers(self) -> list:
        active = []
        for name in self.sessions:
            pid = self.server_pids.get(name)
            active.append({"name": name, "status": "connected", "pid": pid, "type": self.server_configs.get(name, {}).get("type", "unknown")})
        return active

    async def kill_server(self, name: str) -> bool:
        import signal
        pid = self.server_pids.get(name)
        if not pid: return False
        try:
            os.kill(pid, signal.SIGKILL)
            if name in self.sessions: del self.sessions[name]
            if name in self.server_pids: del self.server_pids[name]
            return True
        except ProcessLookupError:
            if name in self.sessions: del self.sessions[name]
            if name in self.server_pids: del self.server_pids[name]
            return True
        except Exception: return False
