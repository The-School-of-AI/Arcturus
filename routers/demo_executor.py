# Demo Executor Router - Execute various demos via API
import asyncio
import subprocess
import json
import os
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/demos", tags=["Demo Execution"])

PROJECT_ROOT = Path(os.getcwd())


# === Pydantic Models ===

class CronExecuteRequest(BaseModel):
    """Execute CRON worldometers demo"""
    pass


class RunsExecuteRequest(BaseModel):
    """Execute RUNS phantom integration demo"""
    pass


class RagExecuteRequest(BaseModel):
    """Execute ArXiv RAG demo"""
    arxiv_search: str  # e.g., "CNN architecture"
    rag_search: str    # e.g., "UNet architecture"


class DemoResponse(BaseModel):
    """Response from demo execution"""
    status: str
    message: str
    demo_type: str
    timestamp: str
    output_file: Optional[str] = None


# === Demo Output Tracking ===

demo_outputs = {}  # In-memory tracking of demo executions


# === Endpoints ===

@router.post("/cron/execute", response_model=DemoResponse)
async def execute_cron_demo(request: CronExecuteRequest, background_tasks: BackgroundTasks):
    """
    Execute CRON Worldometers demo asynchronously.
    
    This runs:
    - Fetches from Worldometers and Yahoo Finance every 2 minutes for 10 minutes
    - Downloads live market data
    - Stores results in data/statistics.txt
    
    Runtime: ~10 minutes
    """
    
    def run_cron():
        try:
            result = subprocess.run(
                ["uv", "run", "python", "scripts/cron_worldometers.py"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=700  # 11+ minutes for 10 min execution
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
    
    # Run in background
    background_tasks.add_task(run_cron)
    
    return DemoResponse(
        status="started",
        message="CRON Worldometers demo started (10 minute execution)",
        demo_type="cron",
        timestamp=datetime.now().isoformat(),
        output_file="data/statistics.txt"
    )


@router.post("/runs/execute", response_model=DemoResponse)
async def execute_runs_demo(request: RunsExecuteRequest, background_tasks: BackgroundTasks):
    """
    Execute RUNS Phantom Browser integration demo asynchronously.
    
    This runs:
    - Opens visible browser
    - Navigates to 3 websites (Wikipedia, Yahoo Finance, Worldometers)
    - Extracts live data
    - Stores results in data/runs_phantom_results.json
    
    Runtime: ~2-3 minutes
    """
    
    def run_runs():
        try:
            result = subprocess.run(
                ["uv", "run", "python", "scripts/demo_runs_phantom_integration.py"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
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


@router.post("/rag/execute", response_model=DemoResponse)
async def execute_rag_demo(request: RagExecuteRequest, background_tasks: BackgroundTasks):
    """
    Execute ArXiv RAG demo asynchronously.
    
    Parameters:
    - arxiv_search: Search query for ArXiv (e.g., "CNN architecture")
    - rag_search: Local RAG search query (e.g., "UNet architecture")
    
    This runs:
    - Opens visible browser
    - Searches ArXiv for papers
    - Downloads top 5 PDFs
    - Embeds documents with FAISS
    - Performs local RAG search
    - Stores results in data/arxiv_demo_results.json
    
    Runtime: ~5-8 minutes
    """
    
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
                timeout=600  # 10 minutes
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


@router.get("/status/{demo_type}")
async def get_demo_status(demo_type: str):
    """
    Get status of a running demo.
    
    demo_type: "cron", "runs", or "rag"
    """
    
    if demo_type not in demo_outputs:
        return {
            "status": "not_started",
            "message": f"Demo '{demo_type}' has not been executed yet"
        }
    
    output = demo_outputs[demo_type]
    
    # If execution is complete, include output
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


@router.get("/output/{demo_type}")
async def get_demo_output(demo_type: str):
    """Get full output from a completed demo execution."""
    
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


@router.get("/results/{demo_type}")
async def get_demo_results(demo_type: str):
    """Get results file from a completed demo."""
    
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
            # Return as text
            return {
                "content": results_path.read_text(),
                "format": "text"
            }
        else:
            # Return as JSON
            with open(results_path) as f:
                return {
                    "content": json.load(f),
                    "format": "json"
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading results: {str(e)}")


@router.delete("/cache")
async def clear_demo_cache():
    """Clear cached demo outputs."""
    demo_outputs.clear()
    return {
        "status": "success",
        "message": "Demo cache cleared"
    }
