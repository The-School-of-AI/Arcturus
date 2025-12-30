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
from routers.remme import background_smart_scan  # Needed for lifespan startup

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
app.include_router(runs_router.router)
app.include_router(rag_router.router)
app.include_router(remme_router.router)
app.include_router(apps_router.router)
app.include_router(settings_router.router)
app.include_router(explorer_router.router)
app.include_router(mcp_router.router)
from routers import prompts as prompts_router
app.include_router(prompts_router.router)


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
