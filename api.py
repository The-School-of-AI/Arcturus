import sys
import os
import asyncio
import subprocess
from pathlib import Path
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
from routers import settings as settings_router
from routers import explorer as explorer_router
from routers import mcp as mcp_router
from routers.remme import background_smart_scan  # Needed for lifespan startup
app.include_router(runs_router.router)
app.include_router(rag_router.router)
app.include_router(remme_router.router)
app.include_router(apps_router.router)
app.include_router(settings_router.router)
app.include_router(explorer_router.router)
app.include_router(mcp_router.router)






# Runs-related code has been moved to routers/runs.py


# RAG-related code has been moved to routers/rag.py

















 










# RemMe endpoints have been moved to routers/remme.py


# === SETTINGS API ENDPOINTS ===

# Settings have been moved to routers/settings.py


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




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
