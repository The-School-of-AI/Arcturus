import sys
import os
import asyncio
import json
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.loop import AgentLoop4
from mcp_servers.multi_mcp import MultiMCP
from core.graph_adapter import nx_to_reactflow
from memory.context import ExecutionContextManager

app = FastAPI()

# Enable CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:517\d", # Allows 5170-5179
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State (Simplified for now)
# In production, use database or persistent store
active_loops = {}
multi_mcp = MultiMCP()

@app.on_event("startup")
async def startup_event():
    await multi_mcp.start()

@app.on_event("shutdown")
async def shutdown_event():
    await multi_mcp.stop()

class RunRequest(BaseModel):
    query: str
    model: str = "gemini-2.0-pro"

class RunResponse(BaseModel):
    id: str
    status: str
    created_at: str
    query: str

async def process_run(run_id: str, query: str):
    """Background task to execute the agent loop"""
    try:
        loop = AgentLoop4(multi_mcp=multi_mcp)
        # Register the LOOP instance immediately so we can stop it
        active_loops[run_id] = loop
        
        # Execute the loop
        # The loop will maintain its own internal context
        context = await loop.run(query, [], {}, [], session_id=run_id)
        
    except Exception as e:
        print(f"Run {run_id} failed: {e}")
        # Clean up on failure
        if run_id in active_loops:
            del active_loops[run_id]

@app.post("/runs")
async def create_run(request: RunRequest, background_tasks: BackgroundTasks):
    run_id = str(int(datetime.now().timestamp()))
    
    # Start background execution
    background_tasks.add_task(process_run, run_id, request.query)
    
    return {
        "id": run_id,
        "status": "starting",
        "created_at": datetime.now().isoformat(),
        "query": request.query
    }

@app.get("/runs")
async def list_runs():
    """List runs from disk"""
    summaries_dir = Path(__file__).parent / "memory" / "session_summaries_index"
    runs = []
    
    if summaries_dir.exists():
        # Walk through date folders
        for date_folder in summaries_dir.glob("*/*/*"):
            for session_file in date_folder.glob("session_*.json"):
                try:
                    data = json.loads(session_file.read_text())
                    graph_data = data
                    # Extract meta
                    graph_details = graph_data.get("graph", {})
                    
                    # Robust Query Extraction
                    query = graph_details.get("original_query")
                    if not query:
                        query = graph_details.get("globals", {}).get("original_query", "Unknown Query")

                    # Timestamp Extraction
                    created_at = graph_details.get("created_at")
                    if not created_at:
                        # Fallback to file creation time
                        created_at = datetime.fromtimestamp(session_file.stat().st_ctime).isoformat()
                    
                    # Compute status from node statuses
                    # Check nodes for their statuses
                    nodes = data.get("nodes", [])
                    node_statuses = [n.get("status", "pending") for n in nodes if n.get("id") != "ROOT"]
                    
                    if any(s == "running" for s in node_statuses):
                        computed_status = "running"
                    elif any(s == "failed" for s in node_statuses):
                        computed_status = "failed" 
                    elif all(s == "completed" for s in node_statuses) and node_statuses:
                        computed_status = "completed"
                    else:
                        # Fallback to graph-level status or completed
                        computed_status = graph_details.get("status", "completed")
                    
                    runs.append({
                        "id": session_file.stem.replace("session_", ""),
                        "query": query, 
                        "created_at": created_at, 
                        "status": computed_status
                    })
                except:
                    continue
    
    # Sort by recent
    return sorted(runs, key=lambda x: x['id'], reverse=True)

@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get graph state for a run"""
    # Check memory first (if running)
    # Then check disk
    
    # Search disk
    summaries_dir = Path(__file__).parent / "memory" / "session_summaries_index"
    found_file = None
    
    # Brute force search (should optimize path structure later)
    for path in summaries_dir.rglob(f"session_{run_id}.json"):
        found_file = path
        break
        
    if found_file:
        data = json.loads(found_file.read_text())
        # Reconstruct Graph to use adapter
        import networkx as nx
        G = nx.node_link_graph(data)
        react_flow = nx_to_reactflow(G)
        return {
            "id": run_id,
            "status": "completed", # simplistic
            "graph": react_flow
        }
        
    raise HTTPException(status_code=404, detail="Run not found")

class UserInputRequest(BaseModel):
    input: str

@app.post("/runs/{run_id}/input")
async def provide_input(run_id: str, request: UserInputRequest):
    """Provide specific input to a running agent"""
    if run_id in active_loops:
        loop = active_loops[run_id]
        if loop.context:
            loop.context.provide_user_input(request.input)
            return {"id": run_id, "status": "input_received"}
        else:
            raise HTTPException(status_code=400, detail="Context not initialized")
    
    raise HTTPException(status_code=404, detail="Active run not found or not waiting for input")

@app.post("/runs/{run_id}/stop")
async def stop_run(run_id: str):
    """Stop a running agent execution"""
    if run_id in active_loops:
        loop = active_loops[run_id]
        loop.stop()
        return {"id": run_id, "status": "stopping"}
    
    raise HTTPException(status_code=404, detail="Active run not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
