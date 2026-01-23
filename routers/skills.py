from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
from core.skills.manager import skill_manager

router = APIRouter(prefix="/skills", tags=["Skills"])

class SkillInfo(BaseModel):
    name: str
    version: str
    description: str
    intent_triggers: List[str]
    installed: bool = True # For now, since we only list installed ones

@router.get("", response_model=List[SkillInfo])
async def list_skills():
    """List all installed skills."""
    if not skill_manager.loaded_skills:
        skill_manager.initialize()
        
    registry = skill_manager.registry_file.read_text()
    import json
    data = json.loads(registry)
    
    skills = []
    for name, info in data.items():
        skills.append(SkillInfo(
            name=name,
            version=info.get("version", "0.0.0"),
            description=info.get("description", ""),
            intent_triggers=info.get("intent_triggers", []),
            installed=True
        ))
    return skills

@router.post("/{skill_id}/install")
async def install_skill(skill_id: str):
    """Placeholder for remote installation."""
    # In v2, this would clone from GitHub
    return {"status": "installed", "message": f"Skill {skill_id} is ready."}
