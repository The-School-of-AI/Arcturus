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

# --- Add these response models after the existing ones ---

class VersionInfoResponse(BaseModel):
    """Version and pin status for a skill."""
    skill_name: str
    current_version: Optional[str] = None
    pinned: bool = False
    history_count: int = 0

class ModerationStatusResponse(BaseModel):
    """Moderation record summary."""
    skill_name: str
    status: str
    flags_count: int = 0
    resolution: Optional[str] = None

class FlagRequest(BaseModel):
    """Request body for flagging a skill."""
    reason: str                 # e.g. "community_report", "suspicious_code"
    reporter: str = "api_user"
    detail: str = ""

class ReviewRequest(BaseModel):
    """Request body for starting/completing a review."""
    moderator: str

class ApproveRequest(BaseModel):
    """Request body for approving a skill."""
    moderator: str
    reason: str = "Approved after review"

class SuspendRequest(BaseModel):
    """Request body for suspending a skill."""
    moderator: str
    reason: str = "Suspended after review"

class AbuseEventResponse(BaseModel):
    """A single abuse event."""
    event_type: str
    skill_name: str
    tool_name: str
    detail: str
    timestamp: str

class PricingResponse(BaseModel):
    """Pricing info for a skill."""
    skill_name: str
    tier: str
    price_cents: int
    currency: str

class PurchaseRequest(BaseModel):
    """Request to purchase a premium skill."""
    buyer_id: str

class PurchaseResponse(BaseModel):
    """Purchase result."""
    success: bool
    message: str
    payment_intent_id: Optional[str] = None


# --- Add these endpoints after the existing ones ---


# ---- Version management ----

@router.get("/skills/{skill_name}/version", response_model=VersionInfoResponse)
async def get_skill_version(skill_name: str):
    """Get version info and pin status for a skill."""
    from marketplace.version_manager import VersionManager
    from shared.state import get_marketplace_bridge

    bridge = get_marketplace_bridge()
    vm = VersionManager(skills_dir=bridge.registry.skills_dir)
    info = vm.get_info(skill_name)

    if info is None:
        raise HTTPException(status_code=404,
                            detail=f"No version info for '{skill_name}'")
    return VersionInfoResponse(
        skill_name=skill_name,
        current_version=info.current_version,
        pinned=info.pinned,
        history_count=len(info.history),
    )


@router.post("/skills/{skill_name}/pin")
async def pin_skill(skill_name: str):
    """Pin a skill at its current version."""
    from marketplace.version_manager import VersionManager
    from shared.state import get_marketplace_bridge

    bridge = get_marketplace_bridge()
    vm = VersionManager(skills_dir=bridge.registry.skills_dir)
    result = vm.pin(skill_name)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"message": result.message}


@router.delete("/skills/{skill_name}/pin")
async def unpin_skill(skill_name: str):
    """Unpin a skill to allow upgrades."""
    from marketplace.version_manager import VersionManager
    from shared.state import get_marketplace_bridge

    bridge = get_marketplace_bridge()
    vm = VersionManager(skills_dir=bridge.registry.skills_dir)
    result = vm.unpin(skill_name)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"message": result.message}


@router.post("/skills/{skill_name}/rollback")
async def rollback_skill(skill_name: str):
    """Roll back a skill to its previous version."""
    from marketplace.version_manager import VersionManager
    from shared.state import get_marketplace_bridge

    bridge = get_marketplace_bridge()
    vm = VersionManager(skills_dir=bridge.registry.skills_dir)
    result = vm.rollback(skill_name)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    bridge.refresh()
    return {"message": result.message}


# ---- Moderation ----

@router.get("/moderation/queue", response_model=List[ModerationStatusResponse])
async def get_moderation_queue():
    """Get all flagged skills awaiting review."""
    from marketplace.moderation import ModerationQueue
    from shared.state import get_marketplace_bridge

    bridge = get_marketplace_bridge()
    mq = ModerationQueue(skills_dir=bridge.registry.skills_dir)
    flagged = mq.list_flagged()
    return [
        ModerationStatusResponse(
            skill_name=r.skill_name,
            status=r.status,
            flags_count=len(r.flags),
            resolution=r.resolution,
        )
        for r in flagged
    ]


@router.post("/moderation/{skill_name}/flag")
async def flag_skill(skill_name: str, body: FlagRequest):
    """Flag a skill for moderation review."""
    from marketplace.moderation import ModerationQueue, FlagReason
    from shared.state import get_marketplace_bridge

    bridge = get_marketplace_bridge()
    mq = ModerationQueue(skills_dir=bridge.registry.skills_dir)
    try:
        reason = FlagReason(body.reason)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reason '{body.reason}'. "
                   f"Valid: {[r.value for r in FlagReason]}",
        )
    result = mq.flag_skill(skill_name, reason, body.reporter, body.detail)
    return {"success": result.success, "message": result.message}


@router.post("/moderation/{skill_name}/review")
async def start_review(skill_name: str, body: ReviewRequest):
    """Start moderator review of a flagged skill."""
    from marketplace.moderation import ModerationQueue
    from shared.state import get_marketplace_bridge

    bridge = get_marketplace_bridge()
    mq = ModerationQueue(skills_dir=bridge.registry.skills_dir)
    result = mq.start_review(skill_name, body.moderator)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"success": True, "message": result.message}


@router.post("/moderation/{skill_name}/approve")
async def approve_skill(skill_name: str, body: ApproveRequest):
    """Approve a skill after review — restores to active."""
    from marketplace.moderation import ModerationQueue
    from shared.state import get_marketplace_bridge

    bridge = get_marketplace_bridge()
    mq = ModerationQueue(skills_dir=bridge.registry.skills_dir)
    result = mq.approve(skill_name, body.moderator, body.reason)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"success": True, "message": result.message}


@router.post("/moderation/{skill_name}/suspend")
async def suspend_skill(skill_name: str, body: SuspendRequest):
    """Suspend a skill — blocks installation."""
    from marketplace.moderation import ModerationQueue
    from shared.state import get_marketplace_bridge

    bridge = get_marketplace_bridge()
    mq = ModerationQueue(skills_dir=bridge.registry.skills_dir)
    result = mq.suspend(skill_name, body.moderator, body.reason)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"success": True, "message": result.message}


# ---- Abuse ----

@router.get("/abuse/events", response_model=List[AbuseEventResponse])
async def get_abuse_events(skill: Optional[str] = None):
    """Get abuse events, optionally filtered by skill name."""
    from marketplace.abuse import AbuseController
    from shared.state import get_marketplace_bridge

    bridge = get_marketplace_bridge()
    ac = AbuseController(skills_dir=bridge.registry.skills_dir)
    events = ac.get_events(skill_name=skill)
    return [
        AbuseEventResponse(
            event_type=e.event_type,
            skill_name=e.skill_name,
            tool_name=e.tool_name,
            detail=e.detail,
            timestamp=e.timestamp,
        )
        for e in events[-50:]   # cap at last 50
    ]


# ---- Billing ----

@router.get("/skills/{skill_name}/pricing", response_model=PricingResponse)
async def get_skill_pricing(skill_name: str):
    """Get pricing info for a skill."""
    from marketplace.billing import BillingManager
    from shared.state import get_marketplace_bridge

    bridge = get_marketplace_bridge()
    bm = BillingManager(skills_dir=bridge.registry.skills_dir)
    pricing = bm.get_pricing(skill_name)
    return PricingResponse(
        skill_name=pricing.skill_name,
        tier=pricing.tier,
        price_cents=pricing.price_cents,
        currency=pricing.currency,
    )


@router.post("/skills/{skill_name}/purchase", response_model=PurchaseResponse)
async def purchase_skill(skill_name: str, body: PurchaseRequest):
    """Purchase a premium skill."""
    from marketplace.billing import BillingManager
    from shared.state import get_marketplace_bridge

    bridge = get_marketplace_bridge()
    bm = BillingManager(skills_dir=bridge.registry.skills_dir)
    result = bm.create_checkout(skill_name, body.buyer_id)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    # Auto-confirm in stub mode (in production, frontend confirms after Stripe)
    confirm = bm.confirm_purchase(
        skill_name, body.buyer_id, result.payment_intent_id
    )
    return PurchaseResponse(
        success=confirm.success,
        message=confirm.message,
        payment_intent_id=confirm.payment_intent_id,
    )
