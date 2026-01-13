import subprocess
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/git", tags=["git"])

class GitStatusResponse(BaseModel):
    branch: str
    staged: List[str]
    unstaged: List[str]
    untracked: List[str]

class GitActionRequest(BaseModel):
    path: str
    file_path: Optional[str] = None
    message: Optional[str] = None
    stage_all: Optional[bool] = False

def run_git_command(args, cwd):
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=e.stderr or e.stdout or str(e))

@router.get("/status", response_model=GitStatusResponse)
async def get_git_status(path: str):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    # Get branch name
    branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], path).strip()
    
    # Get status porcelain
    status_raw = run_git_command(["status", "--porcelain"], path)
    
    staged = []
    unstaged = []
    untracked = []
    
    for line in status_raw.split("\n"):
        if not line:
            continue
        
        state = line[:2]
        file_path = line[3:]
        
        # Porcelain status 2-letter codes:
        # X Y  Meaning
        # -------------------------------------------------
        #   [MD]   not updated
        # M [ MD]  updated in index
        # A [ MD]  added to index
        # D        deleted from index
        # R [ MD]  renamed in index
        # C [ MD]  copied in index
        # -------------------------------------------------
        # [MARC]   index and work tree matches
        # [ MARC] M work tree changed since index
        # [ MARC] D work tree deleted since index
        # -------------------------------------------------
        # ??       untracked
        # !!       ignored
        
        # Simplified grouping:
        if state == "??":
            untracked.append(file_path)
        elif state[0] != " " and state[0] != "?":
            staged.append(file_path)
            # If XY and Y is M or D, it's also unstaged
            if state[1] in ["M", "D"]:
                unstaged.append(file_path)
        else:
            unstaged.append(file_path)
            
    return {
        "branch": branch,
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked
    }

@router.post("/stage")
async def stage_file(request: GitActionRequest):
    run_git_command(["add", request.file_path], request.path)
    return {"success": True}

@router.post("/unstage")
async def unstage_file(request: GitActionRequest):
    run_git_command(["reset", "HEAD", request.file_path], request.path)
    return {"success": True}

@router.post("/commit")
async def commit_changes(request: GitActionRequest):
    if not request.message:
        raise HTTPException(status_code=400, detail="Commit message required")
    
    if request.stage_all:
        # Stage everything including untracked files
        run_git_command(["add", "-A"], request.path)
    
    run_git_command(["commit", "-m", request.message], request.path)
    return {"success": True}

@router.get("/history")
async def get_git_history(path: str, limit: int = 50):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        # Get log with hash, message, author, relative date, and decorations (branches)
        log_raw = run_git_command(["log", "--pretty=format:%h|%s|%an|%ar|%D", f"-n{limit}"], path).strip()
        history = []
        for line in log_raw.split("\n"):
            if not line: continue
            parts = line.split("|")
            if len(parts) >= 4:
                decorations = parts[4] if len(parts) > 4 else ""
                # Parse decorations like "HEAD -> master, origin/master"
                branches = []
                if decorations:
                    # Clean up: remove "HEAD -> ", split by comma
                    clean_dec = decorations.replace("HEAD -> ", "")
                    branches = [b.strip() for b in clean_dec.split(",") if b.strip()]
                
                history.append({
                    "hash": parts[0],
                    "message": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                    "branches": branches
                })
        return history
    except Exception as e:
        return []
