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
from core.scheduler import scheduler_service
from core.persistence import persistence_manager
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
    
    # Bootstrap & Validate Registry
    from core.bootstrap import bootstrap_agents
    from core.registry import registry
    try:
        bootstrap_agents()
        registry.validate()
    except Exception as e:
        print(f"❌ Registry Validation Failed: {e}")
        # We don't necessarily exit, but log big error
        
    scheduler_service.initialize()
    persistence_manager.load_snapshot()
    
    # 🎨 Restore Canvas snaps
    from shared.state import get_canvas_runtime
    get_canvas_runtime().load_snapshots()
    
    await multi_mcp.start()
    
    # Check git
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        print("✅ Git found.")
    except Exception:
        print("⚠️ Git NOT found. GitHub explorer features will fail.")

    # Check Ollama
    try:
        import requests
        from config.settings_loader import get_ollama_url
        requests.get(get_ollama_url("base"), timeout=1)  # Usually http://localhost:11434/
        print("✅ Ollama found.")
    except Exception:
        print("⚠️ Ollama NOT found. AI features may fail.")
    
    # 🧠 Start Smart Sync in background
    asyncio.create_task(background_smart_scan())
    
    yield
    
    print("🛑 API Shutting down...")
    from shared.state import get_canvas_runtime
    get_canvas_runtime().save_snapshots()
    persistence_manager.save_snapshot()
    await multi_mcp.stop()

app = FastAPI(lifespan=lifespan)

# Enable CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "app://."], # Explicitly allow frontend
    allow_origin_regex=r"http://localhost:(517\d|5555)", 
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
app.include_router(runs_router.router, prefix="/api")
app.include_router(rag_router.router, prefix="/api")
app.include_router(remme_router.router, prefix="/api")
app.include_router(apps_router.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(explorer_router.router, prefix="/api")
app.include_router(mcp_router.router, prefix="/api")
from routers import prompts as prompts_router
from routers import news as news_router
from routers import git as git_router
app.include_router(prompts_router.router, prefix="/api")
app.include_router(news_router.router, prefix="/api")
app.include_router(git_router.router, prefix="/api")

from routers import chat as chat_router
app.include_router(chat_router.router, prefix="/api")
from routers import agent as agent_router
app.include_router(agent_router.router, prefix="/api")
from routers import ide_agent as ide_agent_router
app.include_router(ide_agent_router.router, prefix="/api")
from routers import metrics as metrics_router
app.include_router(metrics_router.router, prefix="/api")
from routers import python_tools
app.include_router(python_tools.router, prefix="/api")
from routers import tests as tests_router
app.include_router(tests_router.router, prefix="/api")
# Chat router included
from routers import inbox
app.include_router(inbox.router, prefix="/api")
from routers import cron
app.include_router(cron.router, prefix="/api")
from routers import stream
app.include_router(stream.router, prefix="/api")
from routers import skills
app.include_router(skills.router, prefix="/api")
from routers import canvas as canvas_router
app.include_router(canvas_router.router, prefix="/api")
from routers import optimizer
app.include_router(optimizer.router, prefix="/api")





@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "1.0.0",
        "mcp_ready": True # Since lifespan finishes multi_mcp.start()
    }

if __name__ == "__main__":
    import uvicorn
    # Enable reload=True for development if needed, but here we'll just keep it simple
    # or actually enable it to avoid these restart issues.
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
