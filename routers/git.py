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
    
    try:
        # Get branch name
        branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], path).strip()
        
        # Get status porcelain
        status_raw = run_git_command(["status", "--porcelain"], path)
    except Exception:
        # Not a git repo or other error
        return {
            "branch": "not a git repo",
            "staged": [],
            "unstaged": [],
            "untracked": []
        }
    
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

@router.get("/diff_content")
async def get_git_diff_content(path: str, file_path: str, staged: bool = False, commit_hash: Optional[str] = None):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        if commit_hash:
            # Historical Commit Diff: Original is Parent, Modified is Commit
            modified = run_git_command(["show", f"{commit_hash}:{file_path}"], path)
            try:
                original = run_git_command(["show", f"{commit_hash}^:{file_path}"], path)
            except:
                # First commit or no parent for this file
                original = ""
        elif staged:
            # Staged: Original is HEAD, Modified is Index (staged)
            original = run_git_command(["show", f"HEAD:{file_path}"], path)
            modified = run_git_command(["show", f":{file_path}"], path)
        else:
            # Unstaged: Original is Index, Modified is Working Tree (disk)
            try:
                original = run_git_command(["show", f":{file_path}"], path)
            except:
                # If file is not in index (untracked), original is empty
                original = ""
            
            # Read from disk
            full_path = os.path.join(path, file_path)
            if os.path.exists(full_path):
                with open(full_path, "r") as f:
                    modified = f.read()
            else:
                modified = ""
                
        return {
            "original": original,
            "modified": modified,
            "filename": file_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
                
                commit_hash = parts[0]
                
                history.append({
                    "hash": commit_hash,
                    "message": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                    "branches": branches,
                    "files": [] # No longer fetched by default
                })
        return history
    except Exception as e:
        return []

@router.get("/commit_files")
async def get_with_commit_files(path: str, commit_hash: str):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        files_raw = run_git_command(["show", "--pretty=format:", "--name-only", commit_hash], path).strip()
        files_changed = [f for f in files_raw.split("\n") if f.strip()]
        return {"files": files_changed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
