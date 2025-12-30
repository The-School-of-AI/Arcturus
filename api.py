import sys
import os
import re
import asyncio
import json
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.loop import AgentLoop4
from core.graph_adapter import nx_to_reactflow
from memory.context import ExecutionContextManager
from remme.utils import get_embedding
import tempfile
import subprocess
import shutil
from core.explorer_utils import CodeSkeletonExtractor
from core.model_manager import ModelManager
from config.settings_loader import settings, save_settings, reset_settings, reload_settings

# Import shared state
from shared.state import (
    active_loops,
    get_multi_mcp,
    get_remme_store,
    get_remme_extractor,
    PROJECT_ROOT,
)

from contextlib import asynccontextmanager

# Get shared instances
multi_mcp = get_multi_mcp()
remme_store = get_remme_store()
remme_extractor = get_remme_extractor()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 API Starting up...")
    await multi_mcp.start()
    
    # Check git
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        print("✅ Git found.")
    except Exception:
        print("⚠️ Git NOT found. GitHub explorer features will fail.")
    
    # 🧠 Start Smart Sync in background
    asyncio.create_task(background_smart_scan())
    
    yield
    
    await multi_mcp.stop()

app = FastAPI(lifespan=lifespan)

# Enable CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:517\d", # Allows 5170-5179
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State is now managed in shared/state.py
# active_loops, multi_mcp, remme_store, remme_extractor are imported from there

# === Import and Include Routers ===
from routers import runs as runs_router
from routers import rag as rag_router
from routers import remme as remme_router
from routers import apps as apps_router
from routers.remme import background_smart_scan  # Needed for lifespan startup
app.include_router(runs_router.router)
app.include_router(rag_router.router)
app.include_router(remme_router.router)
app.include_router(apps_router.router)


# --- Explorer Classes ---
class AnalyzeRequest(BaseModel):
    path: str
    type: str = "local" # local or github
    files: Optional[List[str]] = None # New: curated list of files

class ExplorerNode(BaseModel):
    name: str
    path: str
    type: str # file or folder
    children: Optional[List['ExplorerNode']] = None

ExplorerNode.update_forward_refs()


# Runs-related code has been moved to routers/runs.py


# RAG-related code has been moved to routers/rag.py

















 










# RemMe endpoints have been moved to routers/remme.py


# === SETTINGS API ENDPOINTS ===

@app.get("/settings")
async def get_settings():
    """Get all current settings from config/settings.json"""
    try:
        # Force reload to get latest from disk
        current_settings = reload_settings()
        return {"status": "success", "settings": current_settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load settings: {str(e)}")

class UpdateSettingsRequest(BaseModel):
    settings: dict

@app.put("/settings")
async def update_settings(request: UpdateSettingsRequest):
    """Update settings and save to config/settings.json
    
    Note: Some settings require re-indexing (chunk_size, chunk_overlap, etc.)
    or server restart to take effect.
    """
    try:
        global settings
        # Deep merge incoming settings with existing
        def deep_merge(base: dict, update: dict) -> dict:
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
            return base
        
        deep_merge(settings, request.settings)
        save_settings()
        
        # Identify settings that require action
        warnings = []
        rag_keys = ["chunk_size", "chunk_overlap", "max_chunk_length", "semantic_word_limit"]
        if "rag" in request.settings:
            for key in rag_keys:
                if key in request.settings["rag"]:
                    warnings.append(f"Changed '{key}' - requires re-indexing documents to take effect")
        
        if "models" in request.settings:
            warnings.append("Model changes take effect on next document processing or server restart")
        
        return {
            "status": "success",
            "message": "Settings saved successfully",
            "warnings": warnings if warnings else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")

@app.post("/settings/reset")
async def reset_to_defaults():
    """Reset all settings to default values from config/settings.defaults.json"""
    try:
        reset_settings()
        return {"status": "success", "message": "Settings reset to defaults"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {str(e)}")

@app.post("/settings/restart")
async def restart_server():
    """Return instructions for manual restart.
    
    Note: Automatic restart doesn't work reliably with npm run dev:all / concurrently.
    The proper way is to manually Ctrl+C and restart.
    """
    return {
        "status": "manual_required",
        "message": "Automatic restart is not supported. Please manually restart the server.",
        "instructions": [
            "1. Press Ctrl+C in the terminal running npm run dev:all",
            "2. Run: npm run dev:all",
            "3. Refresh the browser"
        ]
    }

# === OLLAMA API ENDPOINTS ===

@app.get("/ollama/models")
async def get_ollama_models():
    """Get list of available Ollama models from local instance"""
    try:
        import requests
        from config.settings_loader import get_ollama_url
        
        ollama_url = get_ollama_url("base")
        response = requests.get(f"{ollama_url}/api/tags", timeout=10)
        
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to connect to Ollama")
        
        data = response.json()
        models = []
        for model in data.get("models", []):
            name = model.get("name", "")
            size_bytes = model.get("size", 0)
            size_gb = round(size_bytes / (1024**3), 2) if size_bytes else 0
            
            # Get family info from Ollama response
            details = model.get("details", {})
            families = details.get("families", [])
            
            # Infer capabilities from model name AND family
            capabilities = set()
            name_lower = name.lower()
            
            # Embedding models
            if "embed" in name_lower or "nomic" in name_lower or "nomic-bert" in families:
                capabilities.add("embedding")
            
            # Vision/multimodal models - check for explicit vision families or name patterns
            vision_families = ["clip", "qwen3vl", "llava"]
            vision_names = ["vl", "vision", "llava", "moondream", "gemma3"]  # gemma3 supports vision
            
            if any(f in families for f in vision_families) or any(v in name_lower for v in vision_names):
                capabilities.add("text")
                capabilities.add("image")
            else:
                capabilities.add("text")
            
            models.append({
                "name": name,
                "size_gb": size_gb,
                "capabilities": list(capabilities),
                "modified_at": model.get("modified_at", "")
            })
        
        return {"status": "success", "models": models}
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Ollama server not running")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PullModelRequest(BaseModel):
    name: str

@app.post("/ollama/pull")
async def pull_ollama_model(request: PullModelRequest):
    """Pull a new model from Ollama registry (starts async download)"""
    try:
        import requests
        from config.settings_loader import get_ollama_url
        
        ollama_url = get_ollama_url("base")
        # Use streaming=False for now, just initiate the pull
        response = requests.post(
            f"{ollama_url}/api/pull",
            json={"name": request.name, "stream": False},
            timeout=600  # 10 min timeout for large models
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Failed to pull model: {response.text}")
        
        return {"status": "success", "message": f"Model '{request.name}' pulled successfully"}
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Model pull timed out - try from terminal")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/gemini/status")
async def get_gemini_status():
    """Check if Gemini API key is configured via environment variable"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        return {
            "status": "success",
            "configured": bool(api_key),
            "key_preview": f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === PROMPTS API ENDPOINTS ===

PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPTS_BACKUP_DIR = Path(__file__).parent / "prompts" / ".backup"

@app.get("/prompts")
async def list_prompts():
    """List all prompt files with their content"""
    try:
        prompts = []
        if PROMPTS_DIR.exists():
            for f in PROMPTS_DIR.glob("*.md"):
                content = f.read_text()
                # Check if backup exists (means original can be restored)
                backup_file = PROMPTS_BACKUP_DIR / f.name
                prompts.append({
                    "name": f.stem,
                    "filename": f.name,
                    "content": content,
                    "lines": len(content.splitlines()),
                    "has_backup": backup_file.exists()
                })
        return {"status": "success", "prompts": sorted(prompts, key=lambda x: x["name"])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UpdatePromptRequest(BaseModel):
    content: str

@app.put("/prompts/{prompt_name}")
async def update_prompt(prompt_name: str, request: UpdatePromptRequest):
    """Update a prompt file's content. Creates backup on first edit."""
    try:
        prompt_file = PROMPTS_DIR / f"{prompt_name}.md"
        if not prompt_file.exists():
            raise HTTPException(status_code=404, detail=f"Prompt '{prompt_name}' not found")
        
        # Create backup on first edit (if doesn't exist)
        PROMPTS_BACKUP_DIR.mkdir(exist_ok=True)
        backup_file = PROMPTS_BACKUP_DIR / f"{prompt_name}.md"
        if not backup_file.exists():
            backup_file.write_text(prompt_file.read_text())
        
        prompt_file.write_text(request.content)
        return {"status": "success", "message": f"Prompt '{prompt_name}' updated", "has_backup": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/prompts/{prompt_name}/reset")
async def reset_prompt(prompt_name: str):
    """Reset a prompt to its original content from backup"""
    try:
        prompt_file = PROMPTS_DIR / f"{prompt_name}.md"
        backup_file = PROMPTS_BACKUP_DIR / f"{prompt_name}.md"
        
        if not backup_file.exists():
            raise HTTPException(status_code=404, detail=f"No backup found for '{prompt_name}'")
        
        # Restore from backup
        original_content = backup_file.read_text()
        prompt_file.write_text(original_content)
        
        # Remove backup after restore
        backup_file.unlink()
        
        return {"status": "success", "message": f"Prompt '{prompt_name}' reset to original", "content": original_content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Apps endpoints have been moved to routers/apps.py










        apps_dir = Path(__file__).parent / "apps"
        apps_dir.mkdir(exist_ok=True)
        
        app_folder = apps_dir / request.id
        app_folder.mkdir(exist_ok=True)
        
        ui_file = app_folder / "ui.json"
        data = request.dict()
        
        # Check if exists to preserve creation time if we tracked it? 
        # Current schema only has lastModified.
        
        ui_file.write_text(json.dumps(data, indent=2))
        return {"status": "success", "id": request.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





# rag/images endpoint has been moved to routers/rag.py

@app.get("/mcp/tools")
async def get_mcp_tools():
    """List available MCP tools by scanning files using regex for robustness"""
    import re
    tools = []
    try:
        server_path = (Path(__file__).parent / "mcp_servers").resolve()
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

@app.get("/mcp/connected_tools")
async def get_connected_mcp_tools():
    """List tools from all connected MCP sessions"""
    try:
        tools_by_server = {}
        for server_name, tools in multi_mcp.tools.items():
            tools_by_server[server_name] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema
                } for t in tools
            ]
        return {"servers": tools_by_server}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/refresh/{server_name}")
async def refresh_mcp_server(server_name: str):
    """Force refresh tool metadata for a specific MCP server"""
    success = await multi_mcp.refresh_server(server_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Server {server_name} not found or not connected")
    return {"status": "success", "message": f"Metadata for {server_name} refreshed and cached"}

# RemMe background tasks and /remme/scan endpoint have been moved to routers/remme.py


# --- Explorer Endpoints ---
@app.get("/explorer/scan")
async def scan_project_files(path: str):
    """Scan project files for the context selector"""
    try:
        abs_path = path
        if not os.path.isabs(abs_path):
            abs_path = os.path.abspath(abs_path)
            
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="Path not found")
            
        extractor = CodeSkeletonExtractor(abs_path)
        scan_results = extractor.scan_project()
        
        return {
            "success": True,
            "scan": scan_results,
            "root_path": abs_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# /remme/profile endpoint has been moved to routers/remme.py


@app.get("/system/files")
async def list_files(path: str):
    """Recursively list files for the explorer panel"""
    try:
        abs_path = path
        if not os.path.isabs(abs_path):
            abs_path = os.path.abspath(abs_path)
            
        print(f"📁 Explorer: Listing files for {abs_path}")
            
        if not os.path.exists(abs_path):
            print(f"  ⚠️ Path not found: {abs_path}")
            return { "files": [], "root_path": abs_path, "error": "Path not found" }
        
        extractor = CodeSkeletonExtractor(abs_path)
        
        def build_tree(current_path):
            nodes = []
            try:
                items = os.listdir(current_path)
            except (PermissionError, FileNotFoundError):
                return []
                
            for item in items:
                full_path = os.path.join(current_path, item)
                try:
                    if extractor.is_ignored(full_path):
                        continue
                        
                    node = {
                        "name": item,
                        "path": full_path,
                        "type": "folder" if os.path.isdir(full_path) else "file"
                    }
                    if os.path.isdir(full_path):
                        children = build_tree(full_path)
                        if children:
                            node["children"] = children
                    nodes.append(node)
                except:
                    continue
            
            nodes.sort(key=lambda x: (x["type"] != "folder", x["name"].lower()))
            return nodes

        return {
            "files": build_tree(abs_path),
            "root_path": abs_path
        }
    except Exception as e:
        print(f"  ❌ List Files Failed: {e}")
        return { "files": [], "root_path": path, "error": str(e) }

@app.post("/explorer/analyze")
async def analyze_project(request: AnalyzeRequest):
    """Analyze a project and generate an architecture map"""
    target_path = request.path
    is_temp = False
    print(f"🧠 Explorer: Analyzing {target_path} (Type: {request.type})")
    
    try:
        # 1. HANDLE GITHUB
        if request.type == "github" or target_path.startswith("http"):
            is_temp = True
            temp_dir = tempfile.mkdtemp()
            print(f"  🔗 Cloning GitHub Repo {target_path} to {temp_dir}...")
            try:
                # Add --depth 1 for speed
                subprocess.run(["git", "clone", "--depth", "1", target_path, temp_dir], check=True, capture_output=True)
                target_path = temp_dir
                print("  ✅ Clone Successful.")
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.decode() if e.stderr else str(e)
                print(f"  ❌ Clone Failed: {err_msg}")
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                raise HTTPException(status_code=400, detail=f"Git clone failed: {err_msg}")
        else:
            # Resolve local path
            target_path = os.path.abspath(target_path)
            if not os.path.exists(target_path):
                print(f"  ⚠️ Local path not found: {target_path}")
                raise HTTPException(status_code=404, detail=f"Local path not found: {target_path}")

        if request.files:
            # Context Analysis Mode: We have a selected list of files
            # Read full content of selected files
            print(f"  📚 Analying {len(request.files)} selected files with Full Context...")
            context_str = ""
            for rel_path in request.files:
                full_path = os.path.join(target_path, rel_path)
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        context_str += f"--- FILE: {rel_path} ---\n{content}\n\n"
                except Exception as e:
                    print(f"  ⚠️ Could not read {rel_path}: {e}")
        else:
            # Fallback to Skeleton Mode (Legacy/Auto)
            # 2. EXTRACT SKELETON
            print("  💀 Extracting Skeletons (Blind Mode)...")
            extractor = CodeSkeletonExtractor(target_path)
            skeletons = extractor.extract_all()
            
            # Combine into a single prompt context
            context_str = ""
            for file_path, skel in skeletons.items():
                context_str += f"--- FILE: {file_path} ---\n{skel}\n\n"
        
        if not context_str:
            raise HTTPException(status_code=400, detail="No content found in the specified path/files for analysis.")

        # 3. LLM ANALYSIS
        model = ModelManager("gemini")
        prompt = f"""
        You are an elite software architect. Analyze the following code skeleton and generate a high-level architecture map in FlowStep format.
        
        CODE CONTEXT:
        {context_str}
        
        GOAL:
        1. Identify the core logical components (Manager classes, API layers, UI components, Utilities).
        2. Group related functionality into thematic blocks.
        3. Map how data flows between these components.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "nodes": [
                {{ 
                    "id": "1", 
                    "type": "agent", 
                    "position": {{ "x": 250, "y": 0 }}, 
                    "data": {{ 
                        "label": "ComponentName", 
                        "description": "Short explanation of what this component does.",
                        "details": ["Key Function A", "Key class B"], 
                        "attributes": ["Async", "Priority: High", "Stateful"]
                    }} 
                }}
            ],
            "edges": [
                {{ "id": "e1-2", "source": "1", "target": "2", "type": "smoothstep" }}
            ],
            "sequence": ["1", "2"]
        }}
        
        LAYOUT RULES:
        - Increment Y by ~250 for each layer to create a vertical flow.
        - X should be around 250 for center, or +/- 200 for side-branches.

        Be technical and precise. Focus on architectural intent.
        """
        
        response_text = await model.generate_text(prompt)
        print(f"  🤖 LLM Response (Raw): {response_text[:200]}...")
        
        # Clean response if it contains markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        try:
            flow_data = json.loads(response_text)
        except json.JSONDecodeError as je:
            print(f"  ❌ JSON Parse Error: {je}")
            raise HTTPException(status_code=500, detail=f"LLM returned invalid JSON: {str(je)}")
            
        return {
            "success": True, 
            "flow_data": flow_data,
            "root_path": request.path if (request.type == "github" or request.path.startswith("http")) else target_path
        }
        
    except Exception as e:
        print(f"Analysis Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if is_temp and os.path.exists(target_path):
            shutil.rmtree(target_path)


# --- MCP Server Management Endpoints ---

class AddServerRequest(BaseModel):
    name: str
    config: dict

@app.get("/mcp/servers")
async def list_mcp_servers():
    """List all configured MCP servers and their status"""
    try:
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

@app.post("/mcp/servers")
async def add_mcp_server(request: AddServerRequest):
    """Add a new MCP server dynamically"""
    try:
        await multi_mcp.add_server(request.name, request.config)
        
        # --- Auto-Assign to Agents ---
        try:
            import yaml
            
            AGENT_CONFIG_PATH = Path('config/agent_config.yaml')
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

@app.delete("/mcp/servers/{name}")
async def remove_mcp_server(name: str):
    """Remove an MCP server"""
    try:
        success = await multi_mcp.remove_server(name)
        if success:
            return {"status": "success", "message": f"Server {name} removed"}
        raise HTTPException(status_code=404, detail="Server not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mcp/connected_tools")
async def get_connected_tools():
    """Get tools grouped by server (Optimized)"""
    # Use cached tools from multi_mcp
    return {"servers": multi_mcp.tools}

class ToolStateRequest(BaseModel):
    server_name: str
    tool_name: str
    enabled: bool

@app.post("/mcp/tool_state")
async def set_tool_state(request: ToolStateRequest):
    """Enable or disable a specific tool"""
    multi_mcp.set_tool_state(request.server_name, request.tool_name, request.enabled)
    return {"status": "success"}

@app.get("/mcp/readme/{name}")
async def get_mcp_readme(name: str):
    """Get the README content for a server"""
    content = multi_mcp.get_server_readme(name)
    if content:
        return {"content": content}
    # Return empty or specific message if not found, don't 404 to avoid frontend console spam
    return {"content": f"# {name}\n\nNo documentation found."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
