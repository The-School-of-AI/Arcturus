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

@router.get("/list", response_model=List[SkillInfo])
async def list_skills():
    """List all installed skills."""
    if not skill_manager.skill_classes:
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

@router.get("/store")
async def list_store():
    """List all available remote skills from GitHub."""
    import requests
    # Simple in-memory cache could act here, but for now direct call
    try:
        url = "https://api.github.com/repos/sickn33/antigravity-awesome-skills/contents/skills"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        skills = []
        for item in data:
            if item["type"] == "dir":
                skills.append({
                    "name": item["name"],
                    "description": "Community Skill (Install to view details)",
                    "installed": False # Frontend can cross-check
                })
        return skills
    except Exception as e:
        # Fallback to hardcoded list if API fails (rate limit)
        return [
            {"name": "research-scientist", "description": "Deep academic research."},
            {"name": "security-auditor", "description": "Vulnerability scanning."},
            {"name": "data-viz-wizard", "description": "Advanced plotting."},
        ]

@router.post("/{skill_name}/install")
async def install_skill(skill_name: str):
    """Download skill from GitHub."""
    import requests
    from pathlib import Path
    
    try:
        # Raw URL for SKILL.md
        url = f"https://raw.githubusercontent.com/sickn33/antigravity-awesome-skills/main/skills/{skill_name}/SKILL.md"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Skill definition not found")
            
        target_dir = Path(f"core/skills/library/{skill_name}")
        target_dir.mkdir(parents=True, exist_ok=True)
        
        (target_dir / "SKILL.md").write_text(resp.text)
        
        # Reload manager to recognize new skill
        skill_manager.initialize()
        
        return {"status": "installed", "message": f"{skill_name} installed successfully"}
    except Exception as e:
        print(f"INSTALL ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ToggleRequest(BaseModel):
    agent_name: str
    skill_name: str
    active: bool

@router.post("/toggle")
async def toggle_skill(req: ToggleRequest):
    """Enable or disable a skill for an agent."""
    import yaml
    from pathlib import Path
    
    config_path = Path("config/agent_config.yaml")
    try:
        data = yaml.safe_load(config_path.read_text())
        agent_config = data["agents"].get(req.agent_name)
        if not agent_config:
            raise HTTPException(status_code=404, detail="Agent not found")
            
        if "skills" not in agent_config:
            agent_config["skills"] = []
            
        current_skills = agent_config["skills"]
        
        if req.active:
            if req.skill_name not in current_skills:
                current_skills.append(req.skill_name)
        else:
            if req.skill_name in current_skills:
                current_skills.remove(req.skill_name)
                
        config_path.write_text(yaml.dump(data, sort_keys=False))
        return {"status": "success", "active": req.active}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/assignments")
async def get_assignments():
    """Return map of Agent -> List[Skills]."""
    import yaml
    from pathlib import Path
    try:
        data = yaml.safe_load(Path("config/agent_config.yaml").read_text())
        assignments = {}
        for agent, conf in data["agents"].items():
            assignments[agent] = conf.get("skills", [])
        return assignments
    except Exception:
        return {}

@router.get("/agents")
async def list_agents():
    """List available agents for assignment."""
    import yaml
    from pathlib import Path
    try:
        data = yaml.safe_load(Path("config/agent_config.yaml").read_text())
        return list(data.get("agents", {}).keys())
    except Exception:
        return []
