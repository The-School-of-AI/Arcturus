import shutil
import subprocess
import os
import json
from enum import Enum
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/python", tags=["python-tools"])

class ToolType(str, Enum):
    RUFF = "ruff"
    PYRIGHT = "pyright"

class FormatRequest(BaseModel):
    path: str
    file_path: str
    content: Optional[str] = None # If provided, format this content instead of reading file

class LintRequest(BaseModel):
    path: str 
    file_path: str

class TypeCheckRequest(BaseModel):
    path: str
    file_path: str

def get_tool_path(tool: str, project_path: str) -> Optional[str]:
    """
    Finds executable for tool.
    Prioritizes:
    1. Local .venv/bin/tool
    2. Global (PATH)
    3. uv run tool (if uv installed)
    """
    # 1. Local venv
    venv_bin = os.path.join(project_path, ".venv", "bin", tool)
    if os.path.exists(venv_bin):
        return venv_bin
    
    # 2. Global path
    global_tool = shutil.which(tool)
    if global_tool:
        return global_tool
        
    return None

def run_command(args: List[str], cwd: str, stdin: Optional[str] = None) -> tuple[int, str, str]:
    """Run command and return (returncode, stdout, stderr)"""
    try:
        process = subprocess.Popen(
            args,
            cwd=cwd,
            stdin=subprocess.PIPE if stdin else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=stdin)
        return process.returncode, stdout, stderr
    except Exception as e:
        return -1, "", str(e)

@router.post("/format")
async def format_python_code(request: FormatRequest):
    """
    Format Python code using Ruff.
    """
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="Project path not found")
        
    tool_path = get_tool_path("ruff", request.path)
    
    # If ruff not found, try to install it or default to no-op
    # For now, if not found, we can try `uv run ruff` or `pip install ruff` logic, 
    # but to be safe and fast, if not found we might return error or skip.
    # Let's try `python -m ruff` as fallback if python is available
    if not tool_path:
        # Fallback command structure
        cmd = ["python3", "-m", "ruff", "format", "-"]
    else:
        cmd = [tool_path, "format", "-"]

    # If content provided, format that. If not, read file (not safe if unsaved, but useful).
    # Typically IDE sends content of unsaved file.
    
    target_content = request.content
    if target_content is None:
        full_path = os.path.join(request.path, request.file_path)
        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                target_content = f.read()
        else:
             raise HTTPException(status_code=404, detail="File not found and no content provided")

    code, stdout, stderr = run_command(cmd, request.path, stdin=target_content)
    
    if code != 0:
        # Ruff failed? Maybe syntax error or ruff missing.
        # If ruff missing:
        if "No module named ruff" in stderr:
             return {"success": False, "error": "Ruff not installed. Run `pip install ruff`."}
        return {"success": False, "error": stderr}
        
    return {"success": True, "formatted_content": stdout}

@router.post("/lint")
async def lint_python_code(request: LintRequest):
    """
    Lint Python code using Ruff (check).
    Returns list of diagnostics.
    """
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="Project path not found")
        
    tool_path = get_tool_path("ruff", request.path)
    cmd = [tool_path] if tool_path else ["python3", "-m", "ruff"]
    
    # ruff check --output-format=json filename
    full_path = os.path.join(request.path, request.file_path)
    cmd.extend(["check", "--output-format=json", full_path])
    
    code, stdout, stderr = run_command(cmd, request.path)
    
    if "No module named ruff" in stderr:
         return {"success": False, "diagnostics": [], "error": "Ruff not installed"}
         
    try:
        diagnostics = json.loads(stdout)
        return {"success": True, "diagnostics": diagnostics}
    except Exception:
        return {"success": False, "error": stderr or "Failed to parse ruff output", "raw": stdout}

@router.post("/typecheck")
async def typecheck_python_code(request: TypeCheckRequest):
    """
    Run Pyright for type checking.
    """
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="Project path not found")

    tool_path = get_tool_path("pyright", request.path)
    # pyright --outputjson file
    cmd = [tool_path] if tool_path else ["npx", "pyright"] # Pyright is often npm installed
    
    full_path = os.path.join(request.path, request.file_path)
    cmd.extend(["--outputjson", full_path])
    
    code, stdout, stderr = run_command(cmd, request.path)
    
    try:
        result = json.loads(stdout)
        return {"success": True, "diagnostics": result.get("generalDiagnostics", [])}
    except Exception:
        return {"success": False, "error": stderr or "Failed to parse pyright output", "raw": stdout}
