#!/usr/bin/env python3
"""
Standalone Demo Executor Server
Runs independently without the main API dependencies (no MongoDB required)
"""

import asyncio
import subprocess
import json
import os
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

PROJECT_ROOT = Path(os.getcwd())

app = FastAPI(title="Arcturus Demo Suite API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Pydantic Models ===

class CronExecuteRequest(BaseModel):
    pass


class RunsExecuteRequest(BaseModel):
    pass


class RagExecuteRequest(BaseModel):
    arxiv_search: str
    rag_search: str


class DemoResponse(BaseModel):
    status: str
    message: str
    demo_type: str
    timestamp: str
    output_file: Optional[str] = None


# === Demo Output Tracking ===

demo_outputs = {}


# === Endpoints ===

@app.post("/demos/cron/execute", response_model=DemoResponse)
async def execute_cron_demo(request: CronExecuteRequest, background_tasks: BackgroundTasks):
    """Execute CRON Worldometers demo"""
    
    def run_cron():
        try:
            result = subprocess.run(
                ["uv", "run", "python", "scripts/cron_worldometers.py"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=700
            )
            
            demo_outputs['cron'] = {
                "status": "completed" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "output": result.stdout,
                "errors": result.stderr,
                "timestamp": datetime.now().isoformat(),
                "output_file": "data/statistics.txt"
            }
        except subprocess.TimeoutExpired:
            demo_outputs['cron'] = {
                "status": "timeout",
                "error": "Execution timeout after 11 minutes",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            demo_outputs['cron'] = {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    background_tasks.add_task(run_cron)
    
    return DemoResponse(
        status="started",
        message="CRON Worldometers demo started (10 minute execution)",
        demo_type="cron",
        timestamp=datetime.now().isoformat(),
        output_file="data/statistics.txt"
    )


@app.post("/demos/runs/execute", response_model=DemoResponse)
async def execute_runs_demo(request: RunsExecuteRequest, background_tasks: BackgroundTasks):
    """Execute RUNS Phantom Browser integration demo"""
    
    def run_runs():
        try:
            result = subprocess.run(
                ["uv", "run", "python", "scripts/demo_runs_phantom_integration.py"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            demo_outputs['runs'] = {
                "status": "completed" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "output": result.stdout,
                "errors": result.stderr,
                "timestamp": datetime.now().isoformat(),
                "output_file": "data/runs_phantom_results.json"
            }
        except subprocess.TimeoutExpired:
            demo_outputs['runs'] = {
                "status": "timeout",
                "error": "Execution timeout after 5 minutes",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            demo_outputs['runs'] = {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    background_tasks.add_task(run_runs)
    
    return DemoResponse(
        status="started",
        message="RUNS Phantom Browser demo started",
        demo_type="runs",
        timestamp=datetime.now().isoformat(),
        output_file="data/runs_phantom_results.json"
    )


@app.post("/demos/rag/execute", response_model=DemoResponse)
async def execute_rag_demo(request: RagExecuteRequest, background_tasks: BackgroundTasks):
    """Execute ArXiv RAG demo"""
    
    def run_rag():
        try:
            result = subprocess.run(
                [
                    "uv", "run", "python",
                    "scripts/demo_arxiv_rag.py",
                    request.arxiv_search,
                    request.rag_search
                ],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=600
            )
            
            demo_outputs['rag'] = {
                "status": "completed" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "output": result.stdout,
                "errors": result.stderr,
                "timestamp": datetime.now().isoformat(),
                "output_file": "data/arxiv_demo_results.json",
                "arxiv_search": request.arxiv_search,
                "rag_search": request.rag_search
            }
        except subprocess.TimeoutExpired:
            demo_outputs['rag'] = {
                "status": "timeout",
                "error": "Execution timeout after 10 minutes",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            demo_outputs['rag'] = {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    background_tasks.add_task(run_rag)
    
    return DemoResponse(
        status="started",
        message=f"ArXiv RAG demo started (searching for '{request.arxiv_search}')",
        demo_type="rag",
        timestamp=datetime.now().isoformat(),
        output_file="data/arxiv_demo_results.json"
    )


@app.get("/demos/status/{demo_type}")
async def get_demo_status(demo_type: str):
    """Get status of a running demo"""
    
    if demo_type not in demo_outputs:
        return {
            "status": "not_started",
            "message": f"Demo '{demo_type}' has not been executed yet"
        }
    
    output = demo_outputs[demo_type]
    
    if output.get("status") in ["completed", "failed", "timeout", "error"]:
        return {
            "status": output["status"],
            "timestamp": output.get("timestamp"),
            "output_file": output.get("output_file"),
            "returncode": output.get("returncode"),
            "has_output": True,
            "message": f"Demo execution {output['status']}"
        }
    
    return {
        "status": "running",
        "timestamp": output.get("timestamp"),
        "message": "Demo is currently executing..."
    }


@app.get("/demos/output/{demo_type}")
async def get_demo_output(demo_type: str):
    """Get full output from a completed demo"""
    
    if demo_type not in demo_outputs:
        raise HTTPException(status_code=404, detail=f"No output for demo '{demo_type}'")
    
    output = demo_outputs[demo_type]
    
    if output.get("status") == "running":
        raise HTTPException(status_code=202, detail="Demo is still running")
    
    return {
        "demo_type": demo_type,
        "status": output.get("status"),
        "timestamp": output.get("timestamp"),
        "output": output.get("output", ""),
        "errors": output.get("errors", ""),
        "output_file": output.get("output_file"),
        "returncode": output.get("returncode")
    }


@app.get("/demos/results/{demo_type}")
async def get_demo_results(demo_type: str):
    """Get results file from a completed demo"""
    
    output_file_map = {
        "cron": "data/statistics.txt",
        "runs": "data/runs_phantom_results.json",
        "rag": "data/arxiv_demo_results.json"
    }
    
    if demo_type not in output_file_map:
        raise HTTPException(status_code=404, detail=f"Unknown demo type: {demo_type}")
    
    results_path = PROJECT_ROOT / output_file_map[demo_type]
    
    if not results_path.exists():
        raise HTTPException(status_code=404, detail=f"Results file not found for {demo_type}")
    
    try:
        if demo_type == "cron":
            return {
                "content": results_path.read_text(),
                "format": "text"
            }
        else:
            with open(results_path) as f:
                return {
                    "content": json.load(f),
                    "format": "json"
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading results: {str(e)}")


@app.delete("/demos/cache")
async def clear_demo_cache():
    """Clear cached demo outputs"""
    demo_outputs.clear()
    return {
        "status": "success",
        "message": "Demo cache cleared"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "service": "Demo Suite API"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("demo_suite_api:app", host="0.0.0.0", port=8001, reload=False)
