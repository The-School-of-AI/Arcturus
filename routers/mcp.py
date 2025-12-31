# MCP Router - Manages Model Context Protocol servers and tools
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
import re
import os

# Import shared state
from shared.state import get_multi_mcp

router = APIRouter()

# --- Data Models ---

class AddServerRequest(BaseModel):
    name: str
    config: dict

class ToolStateRequest(BaseModel):
    server_name: str
    tool_name: str
    enabled: bool

class CallToolRequest(BaseModel):
    server_name: str
    tool_name: str
    arguments: Dict[str, Any]

# --- Endpoints ---

@router.post("/mcp/call")
async def call_mcp_tool(request: CallToolRequest):
    """Call a tool on a specific server"""
    try:
        multi_mcp = get_multi_mcp()
        result = await multi_mcp.call_tool(request.server_name, request.tool_name, request.arguments)
        
        # Serialize result (handle Pydantic models from MCP SDK)
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if hasattr(result, "dict"):
            return result.dict()
            
        return result
    except Exception as e:
        # Improve error logging
        print(f"Error calling tool {request.tool_name} on {request.server_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mcp/tools")
async def get_mcp_tools():
    """List available MCP tools by scanning files using regex for robustness"""
    tools = []
    try:
        # Note: We need to locate the mcp_servers folder relative to the project root
        # Ideally this should be centralized, but here we assume regular structure
        # routers/mcp.py -> parent -> mcp_servers
        server_path = (Path(__file__).parent.parent / "mcp_servers").resolve()
        print(f"🔍 Scanning for MCP tools in: {server_path}")
        
        if not server_path.exists():
            print(f"❌ server_path DOES NOT EXIST: {server_path}")
            return {"tools": []}

        # More robust regex:
        # 1. Matches @mcp.tool or @tool
        # 2. Handles optional parentheses/args
        # 3. Matches optional async
        # 4. Captures function name
        # 5. Correctly handles type hints and arrows
        tool_pattern = re.compile(
            r'@(?:mcp\.)?tool\s*(?:\(.*?\))?\s*'
            r'(?:async\s+)?def\s+(\w+)\s*\(.*?\)\s*(?:->\s*[\w\[\], \.]+)?\s*:'
            r'(?:\s*"""(.*?)""")?',
            re.DOTALL
        )
        
        for py_file in server_path.glob("*.py"):
            print(f"  📄 Scanning file: {py_file.name}")
            try:
                content = py_file.read_text()
                matches = list(tool_pattern.finditer(content))
                print(f"    - Found {len(matches)} tools")
                
                for match in matches:
                    name = match.group(1)
                    docstring = match.group(2)
                    
                    tools.append({
                        "name": name,
                        "description": (docstring or "No description").strip(),
                        "file": py_file.name
                    })

            except Exception as ex:
                print(f"Failed to scan {py_file}: {ex}")
                continue
                
        return {"tools": tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mcp/connected_tools")
async def get_connected_mcp_tools():
    """List tools from all connected MCP sessions"""
    try:
        multi_mcp = get_multi_mcp()
        
        # Check if we should use the optimized structure or manual loop
        # The original code had two endpoints with same path! 
        # Line 343: get_connected_mcp_tools -> loops manually
        # Line 657: get_connected_tools -> returns multi_mcp.tools directly
        # The latter is optimized. let's use the optimized one but return the structure expected by frontend.
        # Use cached tools from multi_mcp
        return {"servers": multi_mcp.tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mcp/refresh/{server_name}")
async def refresh_mcp_server(server_name: str):
    """Force refresh tool metadata for a specific MCP server"""
    multi_mcp = get_multi_mcp()
    success = await multi_mcp.refresh_server(server_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found or not connected")
    return {"status": "success", "message": f"Metadata for {server_name} refreshed and cached"}


@router.get("/mcp/servers")
async def list_mcp_servers():
    """List all configured MCP servers and their status"""
    try:
        multi_mcp = get_multi_mcp()
        # Get configured servers from config file
        config = multi_mcp.server_configs
        # Get connection status
        connected = multi_mcp.get_connected_servers()
        
        servers = []
        for name, cfg in config.items():
            servers.append({
                "name": name,
                "config": cfg,
                "status": "connected" if name in connected else "disconnected"
            })
        return {"servers": servers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mcp/servers")
async def add_mcp_server(request: AddServerRequest):
    """Add a new MCP server dynamically"""
    try:
        multi_mcp = get_multi_mcp()
        await multi_mcp.add_server(request.name, request.config)
        
        # --- Auto-Assign to Agents ---
        try:
            import yaml
            
            # Path resolution needs to be careful
            AGENT_CONFIG_PATH = Path(__file__).parent.parent / 'config/agent_config.yaml'
            if AGENT_CONFIG_PATH.exists():
                with open(AGENT_CONFIG_PATH, 'r') as f:
                    agent_config = yaml.safe_load(f)
                
                updated = False
                # Add to RetrieverAgent and CoderAgent by default
                targets = ['RetrieverAgent', 'CoderAgent']
                
                for agent_name in targets:
                    if agent_name in agent_config['agents']:
                        servers = agent_config['agents'][agent_name].get('mcp_servers', [])
                        if request.name not in servers:
                            servers.append(request.name)
                            agent_config['agents'][agent_name]['mcp_servers'] = servers
                            updated = True
                            print(f"  🤖 Auto-assigned {request.name} to {agent_name}")
                
                if updated:
                    with open(AGENT_CONFIG_PATH, 'w') as f:
                        yaml.dump(agent_config, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            print(f"  ⚠️ Failed to auto-assign server to agents: {e}")
            # Don't fail the whole request, just log warning

        return {"status": "success", "message": f"Server {request.name} added and assigned to agents"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/mcp/servers/{name}")
async def remove_mcp_server(name: str):
    """Remove an MCP server"""
    try:
        multi_mcp = get_multi_mcp()
        success = await multi_mcp.remove_server(name)
        if success:
            return {"status": "success", "message": f"Server {name} removed"}
        raise HTTPException(status_code=404, detail="Server not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mcp/tool_state")
async def set_tool_state(request: ToolStateRequest):
    """Enable or disable a specific tool"""
    multi_mcp = get_multi_mcp()
    multi_mcp.set_tool_state(request.server_name, request.tool_name, request.enabled)
    return {"status": "success"}

@router.get("/mcp/readme/{name}")
async def get_mcp_readme(name: str):
    """Get the README content for a server"""
    multi_mcp = get_multi_mcp()
    content = multi_mcp.get_server_readme(name)
    if content:
        return {"content": content}
    # Return empty or specific message if not found, don't 404 to avoid frontend console spam
    return {"content": f"# {name}\n\nNo documentation found."}
