# Prompts Router - Manage system prompts
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path

router = APIRouter()

# Note: We need to locate the prompts folder relative to the project root
# routers/prompts.py -> parent -> prompts
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
PROMPTS_BACKUP_DIR = PROMPTS_DIR / ".backup"

class UpdatePromptRequest(BaseModel):
    content: str

@router.get("/prompts")
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

@router.put("/prompts/{prompt_name}")
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

@router.post("/prompts/{prompt_name}/reset")
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
