"""
Marketplace API endpoints for browsing, installing, and managing marketplace skills.

Runs parallel to routers/skills.py (which handles core skills).
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from pathlib import Path


router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


# ===  Response Models ===

class MarketplaceSkillInfo(BaseModel):
    """Response model for a marketplace skill."""
    name: str
    version: str
    description: str
    author: str
    category: str
    permissions: List[str]
    dependencies: List[str]
    skill_dependencies: List[str]
    intent_triggers: List[str]
    tool_count: int


class MarketplaceToolInfo(BaseModel):
    """Response model for a marketplace tool."""
    name: str
    description: str
    module: str
    function: str


class InstallRequest(BaseModel):
    """Request body for installing a skill from a path."""
    source_path: str
    force: bool = False


class InstallResponse(BaseModel):
    """Response for install/uninstall operations."""
    success: bool
    skill_name: str
    message: str
    missing_deps: List[str] = []


# === Endpoints ===

@router.get("/skills", response_model=List[MarketplaceSkillInfo])
async def list_marketplace_skills():
    """List all installed marketplace skills."""
    from shared.state import get_marketplace_bridge
    bridge = get_marketplace_bridge()
    
    skills = bridge.registry.list_skills()
    return [
        MarketplaceSkillInfo(
            name=s.name,
            version=s.version,
            description=s.description,
            author=s.author,
            category=s.category,
            permissions=s.permissions,
            dependencies=s.dependencies,
            skill_dependencies=s.skill_dependencies,
            intent_triggers=s.intent_triggers,
            tool_count=len(s.tools)
        )
        for s in skills
    ]


@router.get("/skills/{skill_name}", response_model=MarketplaceSkillInfo)
async def get_marketplace_skill(skill_name: str):
    """Get details for a specific marketplace skill."""
    from shared.state import get_marketplace_bridge
    bridge = get_marketplace_bridge()
    
    manifest = bridge.registry.get_skill(skill_name)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    
    return MarketplaceSkillInfo(
        name=manifest.name,
        version=manifest.version,
        description=manifest.description,
        author=manifest.author,
        category=manifest.category,
        permissions=manifest.permissions,
        dependencies=manifest.dependencies,
        skill_dependencies=manifest.skill_dependencies,
        intent_triggers=manifest.intent_triggers,
        tool_count=len(manifest.tools)
    )


@router.get("/skills/{skill_name}/tools", response_model=List[MarketplaceToolInfo])
async def get_skill_tools(skill_name: str):
    """List all tools provided by a marketplace skill."""
    from shared.state import get_marketplace_bridge
    bridge = get_marketplace_bridge()
    
    manifest = bridge.registry.get_skill(skill_name)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    
    return [
        MarketplaceToolInfo(
            name=t.name,
            description=t.description,
            module=t.module,
            function=t.function
        )
        for t in manifest.tools
    ]


@router.get("/search", response_model=List[MarketplaceSkillInfo])
async def search_marketplace(q: str):
    """Search marketplace skills by keyword."""
    from shared.state import get_marketplace_bridge
    bridge = get_marketplace_bridge()
    
    results = bridge.registry.search_skills(q)
    return [
        MarketplaceSkillInfo(
            name=s.name,
            version=s.version,
            description=s.description,
            author=s.author,
            category=s.category,
            permissions=s.permissions,
            dependencies=s.dependencies,
            skill_dependencies=s.skill_dependencies,
            intent_triggers=s.intent_triggers,
            tool_count=len(s.tools)
        )
        for s in results
    ]


@router.get("/categories")
async def list_categories():
    """List all available skill categories with counts."""
    from shared.state import get_marketplace_bridge
    bridge = get_marketplace_bridge()
    
    categories = {}
    for skill in bridge.registry.list_skills():
        cat = skill.category
        categories[cat] = categories.get(cat, 0) + 1
    return categories


@router.post("/install", response_model=InstallResponse)
async def install_marketplace_skill(request: InstallRequest):
    """Install a marketplace skill from a source directory."""
    from shared.state import get_marketplace_bridge
    bridge = get_marketplace_bridge()
    
    source = Path(request.source_path)
    result = bridge.installer.install_skill(source, force=request.force)
    
    # Refresh marketplace to pick up the new skill
    if result.success:
        bridge.refresh()
    
    return InstallResponse(
        success=result.success,
        skill_name=result.skill_name,
        message=result.message,
        missing_deps=result.missing_deps
    )


@router.delete("/skills/{skill_name}", response_model=InstallResponse)
async def uninstall_marketplace_skill(skill_name: str, force: bool = False):
    """Uninstall a marketplace skill."""
    from shared.state import get_marketplace_bridge
    bridge = get_marketplace_bridge()
    
    result = bridge.installer.uninstall_skill(skill_name, force=force)
    
    # Refresh marketplace to remove the skill's tools
    if result.success:
        bridge.refresh()
    
    return InstallResponse(
        success=result.success,
        skill_name=result.skill_name,
        message=result.message,
        missing_deps=result.missing_deps
    )