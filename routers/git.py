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


# =============================================================================
# ARCTURUS GIT - Auto-commit system with dual-branch management
# =============================================================================

ARCTURUS_BRANCH = "arcturus"

def ensure_gitignore(path: str):
    """
    Ensure .gitignore exists and contains standard exclusions.
    """
    gitignore_path = os.path.join(path, ".gitignore")
    
    # Standard defaults for Python, Node, and Arcturus
    defaults = [
        ".arcturus/",
        ".arcturus",
        "__pycache__/",
        "*.pyc",
        "node_modules/",
        ".DS_Store",
        ".venv/",
        "venv/",
        "env/",
        ".env"
    ]
    
    existing_lines = set()
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, "r") as f:
                # Strip logical lines to check presence
                existing_lines = {line.strip() for line in f.readlines()}
        except Exception as e:
            print(f"Error reading .gitignore: {e}")
            
    # Determine what's missing
    missing = []
    for d in defaults:
        if d not in existing_lines:
            missing.append(d)
            
    if missing:
        try:
            # Append missing rules
            with open(gitignore_path, "a") as f:
                if os.path.exists(gitignore_path) and os.path.getsize(gitignore_path) > 0:
                    f.write("\n")
                
                f.write("# Added by Arcturus\n")
                for m in missing:
                    f.write(f"{m}\n")
        except Exception as e:
            print(f"Error writing .gitignore: {e}")


def run_git_command_safe(args, cwd):
    """Run git command and return (success, output/error)"""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr or e.stdout or str(e)


class ArcturusInitRequest(BaseModel):
    path: str


class ArcturusCommitRequest(BaseModel):
    path: str
    files_changed: Optional[List[str]] = None  # For auto-generated commit message


class ArcturusUserCommitRequest(BaseModel):
    path: str
    message: str


@router.post("/arcturus/init")
async def init_arcturus_branch(request: ArcturusInitRequest):
    """
    Initialize ArcturusGit for a project:
    1. If not a git repo, initialize one
    2. Create 'arcturus' branch if it doesn't exist
    3. Switch to arcturus branch for editing
    """
    path = request.path
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    # Ensure .gitignore exists and has defaults
    ensure_gitignore(path)
    
    # Check if it's a git repo
    git_dir = os.path.join(path, ".git")
    if not os.path.exists(git_dir):
        # Initialize git repo
        success, output = run_git_command_safe(["init"], path)
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to init git: {output}")
        
        # Create initial commit so we have a valid HEAD
        run_git_command_safe(["add", "-A"], path)
        run_git_command_safe(["commit", "-m", "Initial commit (Arcturus)", "--allow-empty"], path)
    
    # Get current branch (this is the "user" branch)
    success, current_branch = run_git_command_safe(["rev-parse", "--abbrev-ref", "HEAD"], path)
    if not success:
        current_branch = "main"
    
    # Check if arcturus branch exists
    success, branches = run_git_command_safe(["branch", "--list", ARCTURUS_BRANCH], path)
    arcturus_exists = ARCTURUS_BRANCH in branches if success else False
    
    if not arcturus_exists:
        # Create arcturus branch from current HEAD
        success, output = run_git_command_safe(["branch", ARCTURUS_BRANCH], path)
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to create arcturus branch: {output}")
    
    # Switch to arcturus branch
    success, output = run_git_command_safe(["checkout", ARCTURUS_BRANCH], path)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to switch to arcturus branch: {output}")
    
    return {
        "success": True,
        "arcturus_branch": ARCTURUS_BRANCH,
        "user_branch": current_branch if current_branch != ARCTURUS_BRANCH else "main",
        "message": f"Arcturus branch initialized. Now on '{ARCTURUS_BRANCH}' branch."
    }


@router.get("/arcturus/branches")
async def get_arcturus_branches(path: str):
    """
    Get information about both arcturus and user branches.
    """
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    # Get current branch
    success, current_branch = run_git_command_safe(["rev-parse", "--abbrev-ref", "HEAD"], path)
    if not success:
        return {
            "is_git_repo": False,
            "arcturus_exists": False,
            "current_branch": None,
            "user_branch": None
        }
    
    # Check if arcturus branch exists
    success, branches_raw = run_git_command_safe(["branch", "--list"], path)
    branches = [b.strip().lstrip("* ") for b in branches_raw.split("\n") if b.strip()] if success else []
    
    arcturus_exists = ARCTURUS_BRANCH in branches
    
    # Determine user branch (first non-arcturus branch, preferring main/master)
    user_branch = None
    for preferred in ["main", "master", "develop"]:
        if preferred in branches and preferred != ARCTURUS_BRANCH:
            user_branch = preferred
            break
    if not user_branch:
        for b in branches:
            if b != ARCTURUS_BRANCH:
                user_branch = b
                break
    
    # Get commit counts for each branch
    arcturus_commits = 0
    user_commits = 0
    
    if arcturus_exists:
        success, count = run_git_command_safe(["rev-list", "--count", ARCTURUS_BRANCH], path)
        arcturus_commits = int(count) if success and count.isdigit() else 0
    
    if user_branch:
        success, count = run_git_command_safe(["rev-list", "--count", user_branch], path)
        user_commits = int(count) if success and count.isdigit() else 0
    
    # Get ahead/behind between arcturus and user branch
    ahead = 0
    behind = 0
    if arcturus_exists and user_branch:
        success, ahead_behind = run_git_command_safe(
            ["rev-list", "--left-right", "--count", f"{user_branch}...{ARCTURUS_BRANCH}"], 
            path
        )
        if success:
            parts = ahead_behind.split()
            if len(parts) == 2:
                behind = int(parts[0])  # commits in user not in arcturus
                ahead = int(parts[1])   # commits in arcturus not in user
    
    return {
        "is_git_repo": True,
        "arcturus_exists": arcturus_exists,
        "current_branch": current_branch,
        "user_branch": user_branch,
        "arcturus_commits": arcturus_commits,
        "user_commits": user_commits,
        "arcturus_ahead": ahead,
        "arcturus_behind": behind
    }


@router.post("/arcturus/commit")
async def arcturus_auto_commit(request: ArcturusCommitRequest):
    """
    Auto-commit changes to the arcturus branch.
    Called by the IDE timer after 15s of inactivity.
    """
    path = request.path
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    # Ensure we're on arcturus branch
    success, current = run_git_command_safe(["rev-parse", "--abbrev-ref", "HEAD"], path)
    if not success or current != ARCTURUS_BRANCH:
        raise HTTPException(status_code=400, detail=f"Not on arcturus branch. Current: {current}")
    
    # Check if there are changes to commit
    success, status = run_git_command_safe(["status", "--porcelain"], path)
    if not success or not status.strip():
        return {"success": True, "committed": False, "message": "No changes to commit"}
    
    # Stage all changes
    run_git_command_safe(["add", "-A"], path)
    
    # Generate commit message
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if request.files_changed:
        files_str = ", ".join(request.files_changed[:3])
        if len(request.files_changed) > 3:
            files_str += f" +{len(request.files_changed) - 3} more"
        message = f"Auto: {files_str} at {timestamp}"
    else:
        # Get list of changed files
        changed_files = [line[3:] for line in status.split("\n") if line.strip()]
        file_names = [os.path.basename(f) for f in changed_files[:3]]
        files_str = ", ".join(file_names)
        if len(changed_files) > 3:
            files_str += f" +{len(changed_files) - 3} more"
        message = f"Auto: {files_str} at {timestamp}"
    
    # Commit
    success, output = run_git_command_safe(["commit", "-m", message], path)
    if not success:
        raise HTTPException(status_code=500, detail=f"Commit failed: {output}")
    
    # Get the new commit hash
    success, commit_hash = run_git_command_safe(["rev-parse", "--short", "HEAD"], path)
    
    return {
        "success": True,
        "committed": True,
        "message": message,
        "commit_hash": commit_hash if success else None
    }


@router.post("/arcturus/user-commit")
async def arcturus_user_commit(request: ArcturusUserCommitRequest):
    """
    Squash all arcturus commits since last user commit and apply to user branch.
    This is called when user explicitly wants to "commit for real".
    """
    path = request.path
    message = request.message
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="Commit message required")
    
    # Get branch info
    success, branches_raw = run_git_command_safe(["branch", "--list"], path)
    branches = [b.strip().lstrip("* ") for b in branches_raw.split("\n") if b.strip()] if success else []
    
    # Find user branch
    user_branch = None
    for preferred in ["main", "master", "develop"]:
        if preferred in branches and preferred != ARCTURUS_BRANCH:
            user_branch = preferred
            break
    if not user_branch:
        for b in branches:
            if b != ARCTURUS_BRANCH:
                user_branch = b
                break
    
    if not user_branch:
        # Create main branch if none exists
        user_branch = "main"
        success, output = run_git_command_safe(["branch", user_branch], path)
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to create user branch: {output}")
    
    # Get current arcturus state (we'll apply this to user branch)
    success, current = run_git_command_safe(["rev-parse", "--abbrev-ref", "HEAD"], path)
    
    # Switch to user branch
    success, output = run_git_command_safe(["checkout", user_branch], path)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to switch to user branch: {output}")
    
    try:
        # Merge arcturus with squash
        success, output = run_git_command_safe(["merge", "--squash", ARCTURUS_BRANCH], path)
        if not success:
            # Revert to arcturus branch on failure
            run_git_command_safe(["checkout", ARCTURUS_BRANCH], path)
            raise HTTPException(status_code=500, detail=f"Merge failed: {output}")
        
        # Commit the squashed changes
        success, output = run_git_command_safe(["commit", "-m", message], path)
        if not success:
            # May fail if no changes (already up to date)
            if "nothing to commit" in output.lower():
                run_git_command_safe(["checkout", ARCTURUS_BRANCH], path)
                return {
                    "success": True,
                    "committed": False,
                    "message": "No new changes to commit to user branch"
                }
            run_git_command_safe(["checkout", ARCTURUS_BRANCH], path)
            raise HTTPException(status_code=500, detail=f"Commit failed: {output}")
        
        # Get commit hash
        success, commit_hash = run_git_command_safe(["rev-parse", "--short", "HEAD"], path)
        
        # Switch back to arcturus branch
        run_git_command_safe(["checkout", ARCTURUS_BRANCH], path)
        
        return {
            "success": True,
            "committed": True,
            "user_branch": user_branch,
            "commit_hash": commit_hash if success else None,
            "message": message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # Ensure we're back on arcturus branch
        run_git_command_safe(["checkout", ARCTURUS_BRANCH], path)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/arcturus/history")
async def get_arcturus_history(path: str, branch: str = "arcturus", limit: int = 50):
    """
    Get commit history for a specific branch (arcturus or user).
    """
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        log_raw = run_git_command([
            "log", branch,
            "--pretty=format:%h|%s|%an|%ar|%D", 
            f"-n{limit}"
        ], path).strip()
        
        history = []
        for line in log_raw.split("\n"):
            if not line: 
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                decorations = parts[4] if len(parts) > 4 else ""
                branches = []
                if decorations:
                    clean_dec = decorations.replace("HEAD -> ", "")
                    branches = [b.strip() for b in clean_dec.split(",") if b.strip()]
                
                history.append({
                    "hash": parts[0],
                    "message": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                    "branches": branches,
                    "files": []
                })
        return history
    except Exception:
        return []
