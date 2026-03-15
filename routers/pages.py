from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
from typing import Optional, Dict, Any, List
import asyncio
import time
import uuid
import json
from functools import lru_cache
from datetime import datetime, timedelta

from content import page_generator

router = APIRouter(prefix="/pages", tags=["Pages"])

# Performance and monitoring
REQUEST_CACHE: Dict[str, Any] = {}  # Simple request cache
PERF_METRICS: Dict[str, List[float]] = {"generate_times": [], "fetch_times": [], "search_times": []}
RATE_LIMITS: Dict[str, List[datetime]] = {}  # Simple rate limiting

# Enhanced validation models
class GenerateRequest(BaseModel):
    query: str
    template: Optional[str] = "topic_overview"
    
    @validator('query')
    def validate_query(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError('Query must be at least 3 characters long')
        if len(v) > 1000:
            raise ValueError('Query too long (max 1000 characters)')
        return v.strip()
    
    @validator('template')
    def validate_template(cls, v):
        allowed = ["topic_overview", "product_comparison", "how_to_guide", "market_analysis", "research_brief", "profile"]
        if v not in allowed:
            raise ValueError(f'Template must be one of: {allowed}')
        return v

# Rate limiting helper
def check_rate_limit(endpoint: str, limit: int = 10, window_minutes: int = 1) -> bool:
    """Simple rate limiting - limit requests per window"""
    now = datetime.now()
    window_start = now - timedelta(minutes=window_minutes)
    
    # Clean old entries
    if endpoint in RATE_LIMITS:
        RATE_LIMITS[endpoint] = [ts for ts in RATE_LIMITS[endpoint] if ts > window_start]
    else:
        RATE_LIMITS[endpoint] = []
    
    # Check limit
    if len(RATE_LIMITS[endpoint]) >= limit:
        return False
    
    # Add current request
    RATE_LIMITS[endpoint].append(now)
    return True

# Performance monitoring decorator
def monitor_performance(operation: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                PERF_METRICS.setdefault(operation, []).append(elapsed)
                # Keep only last 100 measurements
                if len(PERF_METRICS[operation]) > 100:
                    PERF_METRICS[operation] = PERF_METRICS[operation][-100:]
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                PERF_METRICS.setdefault(f"{operation}_errors", []).append(elapsed)
                raise
        return wrapper
    return decorator

@lru_cache(maxsize=100)
def get_cached_folder_stats() -> str:
    """Cache folder statistics for performance"""
    stats = {}
    for folder_id, folder in FOLDERS.items():
        page_count = sum(1 for page_meta in PAGES_META.values() 
                        if page_meta.get("folder_id") == folder_id and not page_meta.get("deleted"))
        stats[folder_id] = page_count
    return json.dumps(stats)

@lru_cache(maxsize=50)
def get_cached_tag_stats() -> str:
    """Cache tag usage statistics"""
    tag_usage = {}
    for page_meta in PAGES_META.values():
        if not page_meta.get("deleted"):
            for tag in page_meta.get("tags", []):
                tag_usage[tag] = tag_usage.get(tag, 0) + 1
    return json.dumps(tag_usage)


class SectionRefreshRequest(BaseModel):
    action: str  # "expand", "simplify", "add_examples", "cite_more", "regenerate"
    instruction: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class WidgetRequest(BaseModel):
    widget_type: str  # "stock_ticker", "weather", "live_chart", "poll", "calculator"
    config: Dict[str, Any]


# Simple in-process job tracker (Phase-1). Replace with persistent job queue in Phase-2.
JOBS: Dict[str, Dict[str, Any]] = {}


async def _run_generate_job(job_id: str, req: GenerateRequest) -> None:
    JOBS[job_id]["status"] = "running"
    try:
        page = await page_generator.generate_page(req.query, template=req.template, created_by="api")
        JOBS[job_id]["status"] = "done"
        JOBS[job_id]["page_id"] = page.get("id")
        
        # Store page metadata for list endpoints
        page_id = page.get("id")
        PAGES_META[page_id] = {
            "title": page.get("title", "Untitled"),
            "created_at": page.get("metadata", {}).get("created_at", "now"),
            "updated_at": page.get("metadata", {}).get("created_at", "now"),
            "query": page.get("query"),
            "template": page.get("template"),
            "owner_id": page.get("metadata", {}).get("created_by"),
            "tags": [],
            "folder_id": None,
            "visibility": "private",
            "deleted": False
        }
        
    except Exception as exc:  # keep broad to capture failures for the job tracker
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(exc)


@router.post("/pages/generate", status_code=202)
async def generate_page(req: GenerateRequest):
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query is required")

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status": "pending", "page_id": None, "error": None}

    # schedule background generation on the event loop
    asyncio.create_task(_run_generate_job(job_id, req))

    return {"job_id": job_id, "status_url": f"/pages/jobs/{job_id}"}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


# --- Stubbed collection, folder, versioning, and collaboration endpoints ---


class PageListItem(BaseModel):
    id: str
    title: str
    excerpt: Optional[str] = None
    tags: List[str] = []
    folder_id: Optional[str] = None
    owner_id: Optional[str] = None
    updated_at: Optional[str] = None


class ListResponse(BaseModel):
    items: List[PageListItem]
    total: int
    page: int
    per_page: int


# Enhanced in-memory storage for production-ready collection management
PAGES_META: Dict[str, Dict[str, Any]] = {}
FOLDERS: Dict[str, Dict[str, Any]] = {}
SHARES: Dict[str, Any] = {}
VERSIONS: Dict[str, List[Dict[str, Any]]] = {}
PUBLIC_PAGES: Dict[str, Dict[str, Any]] = {}  # Store public page shares with passwords
TAGS_REGISTRY: Dict[str, Dict[str, Any]] = {}  # Global tag registry with metadata
TEAM_MEMBERS: Dict[str, Dict[str, Any]] = {}  # Team collaboration data


@router.get("", response_model=ListResponse)
async def list_pages(q: Optional[str] = None, folder_id: Optional[str] = None, tags: Optional[str] = None, page: int = 1, per_page: int = 25):
    """List pages with optional filters. Shows folder relationships clearly."""
    
    # Try to delegate to page_generator if available
    try:
        if hasattr(page_generator, "list_pages"):
            results = page_generator.list_pages(q=q, folder_id=folder_id, tags=tags, page=page, per_page=per_page)
            return results
    except Exception:
        pass

    # Fallback: return entries from in-memory PAGES_META with folder info
    items = []
    for pid, meta in list(PAGES_META.items()):
        if meta.get("deleted"):
            continue
            
        # Apply filters
        if folder_id and meta.get("folder_id") != folder_id:
            continue
        if q and q.lower() not in meta.get("title", "").lower():
            continue
        if tags:
            page_tags = meta.get("tags", [])
            tag_filter = tags.split(",")
            if not any(tag.strip() in page_tags for tag in tag_filter):
                continue
        
        # Get folder name for display
        folder_name = None
        folder_id_val = meta.get("folder_id")
        if folder_id_val and folder_id_val in FOLDERS:
            folder_name = FOLDERS[folder_id_val]["name"]
        
        items.append(PageListItem(
            id=pid,
            title=meta.get("title", "Untitled"),
            excerpt=meta.get("excerpt"),
            tags=meta.get("tags", []),
            folder_id=meta.get("folder_id"),
            owner_id=meta.get("owner_id"),
            updated_at=meta.get("updated_at")
        ))

    start = (page - 1) * per_page
    sliced = items[start:start + per_page]
    
    return {
        "items": sliced,
        "total": len(items),
        "page": page,
        "per_page": per_page,
        "filters": {
            "query": q,
            "folder_id": folder_id,
            "tags": tags
        }
    }


class CreateFolderRequest(BaseModel):
    name: str
    parent_id: Optional[str] = None
    description: Optional[str] = ""


@router.post("/folders", status_code=201)
async def create_folder(req: CreateFolderRequest):
    """Create a new folder for organizing pages"""
    fid = uuid.uuid4().hex
    FOLDERS[fid] = {
        "id": fid,
        "name": req.name,
        "parent_id": req.parent_id,
        "description": req.description,
        "created_at": "now",
        "page_count": 0
    }
    return {"id": fid, "name": req.name}


@router.get("/all-folders")
async def list_folders():
    """List all folders with page counts"""
    # Calculate page counts for each folder
    for folder_id in FOLDERS:
        count = sum(1 for page_meta in PAGES_META.values() 
                   if page_meta.get("folder_id") == folder_id and not page_meta.get("deleted"))
        FOLDERS[folder_id]["page_count"] = count
    
    return {"folders": list(FOLDERS.values())}


# Now parameterized routes after all specific routes
@router.get("/{page_id}")
async def get_page(page_id: str):
    try:
        page = page_generator.load_page(page_id)
        return page
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")


@router.get("/folders/{folder_id}")
async def get_folder(folder_id: str):
    """Get folder details with list of pages in it"""
    folder = FOLDERS.get(folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="folder not found")
    
    # Get pages in this folder
    pages_in_folder = []
    for page_id, page_meta in PAGES_META.items():
        if page_meta.get("folder_id") == folder_id and not page_meta.get("deleted"):
            pages_in_folder.append({
                "id": page_id,
                "title": page_meta.get("title", "Untitled"),
                "updated_at": page_meta.get("updated_at")
            })
    
    return {
        **folder,
        "pages": pages_in_folder,
        "page_count": len(pages_in_folder)
    }


@router.patch("/folders/{folder_id}")
async def update_folder(folder_id: str, req: CreateFolderRequest):
    """Update folder details"""
    folder = FOLDERS.get(folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="folder not found")
    
    folder.update({
        "name": req.name,
        "description": req.description,
        "parent_id": req.parent_id
    })
    return folder


# --- Team Collaboration Endpoints ---

class TeamMemberRequest(BaseModel):
    email: str
    role: str  # "viewer", "editor", "admin"
    name: Optional[str] = ""

class CommentRequest(BaseModel):
    content: str
    section_id: Optional[str] = None
    reply_to: Optional[str] = None

@router.get("/team/members")
async def list_team_members():
    """List all team members with their roles"""
    return {"members": list(TEAM_MEMBERS.values())}

@router.post("/team/members", status_code=201)
async def invite_team_member(req: TeamMemberRequest):
    """Invite a new team member"""
    member_id = uuid.uuid4().hex
    TEAM_MEMBERS[member_id] = {
        "id": member_id,
        "email": req.email,
        "name": req.name or req.email.split('@')[0],
        "role": req.role,
        "invited_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "invited"
    }
    return {"member_id": member_id, "status": "invited"}

@router.patch("/team/members/{member_id}")
async def update_team_member(member_id: str, req: TeamMemberRequest):
    """Update team member role or details"""
    if member_id not in TEAM_MEMBERS:
        raise HTTPException(status_code=404, detail="member not found")
    
    TEAM_MEMBERS[member_id].update({
        "role": req.role,
        "name": req.name or TEAM_MEMBERS[member_id]["name"],
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    })
    return TEAM_MEMBERS[member_id]

@router.delete("/team/members/{member_id}")
async def remove_team_member(member_id: str):
    """Remove team member and revoke all their page access"""
    if member_id not in TEAM_MEMBERS:
        return {"status": "deleted", "id": member_id}  # Idempotent
    
    # Remove from all page shares
    removed_from_pages = []
    for page_id, shares_list in SHARES.items():
        for share in shares_list:
            if share.get("type") == "users":
                original_count = len(share.get("entries", []))
                share["entries"] = [entry for entry in share.get("entries", []) if entry.get("user_id") != member_id]
                if len(share["entries"]) < original_count:
                    removed_from_pages.append(page_id)
    
    del TEAM_MEMBERS[member_id]
    return {
        "status": "deleted",
        "id": member_id,
        "removed_from_pages": len(set(removed_from_pages))
    }

@router.post("/{page_id}/comments", status_code=201)
async def add_comment(page_id: str, req: CommentRequest):
    """Add a comment to a page or section"""
    # Verify page exists
    try:
        page_generator.load_page(page_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")
    
    comment_id = uuid.uuid4().hex
    comment = {
        "id": comment_id,
        "content": req.content,
        "section_id": req.section_id,
        "reply_to": req.reply_to,
        "author_id": "api",  # In production, get from auth
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "resolved": False
    }
    
    # Store comment (in production, this would go to database)
    comments_key = f"comments_{page_id}"
    if comments_key not in globals():
        globals()[comments_key] = []
    globals()[comments_key].append(comment)
    
    return {"comment_id": comment_id, "comment": comment}

@router.get("/{page_id}/comments")
async def list_comments(page_id: str, section_id: Optional[str] = None):
    """List comments for a page or specific section"""
    comments_key = f"comments_{page_id}"
    all_comments = globals().get(comments_key, [])
    
    if section_id:
        filtered_comments = [c for c in all_comments if c.get("section_id") == section_id]
    else:
        filtered_comments = all_comments
    
    return {"comments": filtered_comments}

@router.patch("/{page_id}/comments/{comment_id}")
async def update_comment(page_id: str, comment_id: str, req: CommentRequest):
    """Update or resolve a comment"""
    comments_key = f"comments_{page_id}"
    all_comments = globals().get(comments_key, [])
    
    for comment in all_comments:
        if comment["id"] == comment_id:
            comment.update({
                "content": req.content,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
            return {"comment": comment}
    
    raise HTTPException(status_code=404, detail="comment not found")

@router.delete("/{page_id}/comments/{comment_id}")
async def delete_comment(page_id: str, comment_id: str):
    """Delete a comment"""
    comments_key = f"comments_{page_id}"
    all_comments = globals().get(comments_key, [])
    
    globals()[comments_key] = [c for c in all_comments if c["id"] != comment_id]
    return {"status": "deleted", "comment_id": comment_id}

# --- Delete Tag Endpoint ---

class TagRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    color: Optional[str] = "blue"
    category: Optional[str] = "general"

@router.get("/tags")
async def list_tags():
    """List all tags with usage statistics"""
    # Calculate usage for each tag
    tag_usage = {}
    for page_meta in PAGES_META.values():
        if not page_meta.get("deleted"):
            for tag in page_meta.get("tags", []):
                tag_usage[tag] = tag_usage.get(tag, 0) + 1
    
    # Combine registry data with usage
    all_tags = []
    for tag_name in set(list(TAGS_REGISTRY.keys()) + list(tag_usage.keys())):
        tag_info = TAGS_REGISTRY.get(tag_name, {"name": tag_name})
        tag_info["usage_count"] = tag_usage.get(tag_name, 0)
        all_tags.append(tag_info)
    
    return {"tags": sorted(all_tags, key=lambda x: x.get("usage_count", 0), reverse=True)}

@router.post("/tags", status_code=201)
async def create_tag(req: TagRequest):
    """Create or update a tag with metadata"""
    TAGS_REGISTRY[req.name] = {
        "name": req.name,
        "description": req.description,
        "color": req.color,
        "category": req.category,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    return {"tag": TAGS_REGISTRY[req.name]}

@router.delete("/tags/{tag_name}")
async def delete_tag(tag_name: str, reassign_to: Optional[str] = None):
    """Delete tag and optionally reassign pages to another tag"""
    # Count pages using this tag
    affected_pages = []
    for page_id, page_meta in PAGES_META.items():
        if not page_meta.get("deleted") and tag_name in page_meta.get("tags", []):
            affected_pages.append(page_id)
    
    # Remove tag from all pages
    for page_id in affected_pages:
        PAGES_META[page_id]["tags"] = [t for t in PAGES_META[page_id].get("tags", []) if t != tag_name]
        if reassign_to:
            PAGES_META[page_id]["tags"].append(reassign_to)
        PAGES_META[page_id]["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    # Remove from registry
    TAGS_REGISTRY.pop(tag_name, None)
    
    return {
        "status": "deleted",
        "tag": tag_name,
        "affected_pages": len(affected_pages),
        "reassigned_to": reassign_to
    }

@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: str, move_pages_to: Optional[str] = None, force: Optional[bool] = False):
    """Delete folder, handling pages appropriately"""
    folder = FOLDERS.get(folder_id)
    if not folder:
        return {"status": "deleted", "id": folder_id}  # Idempotent
    
    # Count pages in this folder
    pages_in_folder = [
        page_id for page_id, page_meta in PAGES_META.items() 
        if page_meta.get("folder_id") == folder_id and not page_meta.get("deleted")
    ]
    
    # If folder has pages and no move_pages_to specified and not force, require explicit action
    if pages_in_folder and not move_pages_to and not force:
        return {
            "error": "folder_not_empty",
            "message": f"Folder contains {len(pages_in_folder)} pages. Specify move_pages_to folder ID or use force=true to move to root",
            "page_count": len(pages_in_folder),
            "pages": pages_in_folder[:5],  # Show first 5 page IDs
            "suggestions": {
                "move_to_root": f"?force=true",
                "move_to_folder": f"?move_pages_to=folder_id"
            }
        }
    
    # Validate target folder if specified
    if move_pages_to and move_pages_to not in FOLDERS:
        raise HTTPException(status_code=400, detail=f"Target folder {move_pages_to} not found")
    
    # Move pages to target folder (or root if None)
    moved_count = 0
    for page_id in pages_in_folder:
        PAGES_META[page_id]["folder_id"] = move_pages_to
        PAGES_META[page_id]["updated_at"] = "now"
        moved_count += 1
    
    # Delete the folder
    del FOLDERS[folder_id]
    
    target_name = "root"
    if move_pages_to and move_pages_to in FOLDERS:
        target_name = FOLDERS[move_pages_to]["name"]
    
    return {
        "status": "deleted", 
        "id": folder_id,
        "pages_moved": moved_count,
        "pages_moved_to": move_pages_to or "root",
        "target_folder_name": target_name
    }


class UpdatePageMetadata(BaseModel):
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    folder_id: Optional[str] = None
    visibility: Optional[str] = None  # 'private', 'public', 'shared'


@router.patch("/{page_id}")
async def update_page_metadata(page_id: str, req: UpdatePageMetadata):
    """Update page metadata including folder assignment"""
    
    # Verify page exists
    try:
        page_generator.load_page(page_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")
    
    # Verify folder exists if folder_id is provided
    if req.folder_id and req.folder_id not in FOLDERS:
        raise HTTPException(status_code=400, detail=f"folder {req.folder_id} not found")
    
    # Apply changes to in-memory meta
    meta = PAGES_META.setdefault(page_id, {})
    updates = req.dict(exclude_unset=True)
    
    for k, v in updates.items():
        meta[k] = v
    
    meta["updated_at"] = "now"  # timestamp
    
    # Create a new version marker for the metadata change
    ver_id = uuid.uuid4().hex
    VERSIONS.setdefault(page_id, []).append({
        "version_id": ver_id,
        "timestamp": "now",
        "author_id": "api",
        "summary": f"metadata update: {', '.join(updates.keys())}",
        "changes": updates
    })
    
    return {"id": page_id, "version_id": ver_id, "updated_metadata": updates}


@router.delete("/{page_id}")
async def delete_page(page_id: str, hard: Optional[bool] = False):
    # Soft-delete behavior: mark tombstone in meta
    meta = PAGES_META.get(page_id)
    if not meta:
        # allow idempotent deletes
        return {"status": "deleted", "id": page_id}
    if hard:
        PAGES_META.pop(page_id, None)
        VERSIONS.pop(page_id, None)
        return {"status": "deleted_permanently", "id": page_id}
    meta["deleted"] = True
    return {"status": "soft_deleted", "id": page_id}


@router.get("/{page_id}/history")
async def list_versions(page_id: str, limit: Optional[int] = 50, include_content: Optional[bool] = False):
    """Get comprehensive version history with optional content snapshots"""
    versions = VERSIONS.get(page_id, [])
    
    if include_content:
        # In production, this would fetch actual page content snapshots
        for version in versions[-limit:]:
            version["has_content_snapshot"] = True
    
    return {
        "versions": versions[-limit:] if limit else versions,
        "total_versions": len(versions),
        "oldest_version": versions[0] if versions else None,
        "latest_version": versions[-1] if versions else None
    }

@router.get("/{page_id}/history/{version_id}")
async def get_version_details(page_id: str, version_id: str):
    """Get detailed information about a specific version"""
    versions = VERSIONS.get(page_id, [])
    version = None
    
    for v in versions:
        if v["version_id"] == version_id:
            version = v
            break
    
    if not version:
        raise HTTPException(status_code=404, detail="version not found")
    
    return {
        "version": version,
        "content_available": True,  # In production, check if content snapshot exists
        "diff_available": True     # In production, check if diff can be computed
    }

@router.get("/{page_id}/history/{version_id}/diff")
async def get_version_diff(page_id: str, version_id: str, compare_to: Optional[str] = None):
    """Get diff between two versions"""
    versions = VERSIONS.get(page_id, [])
    target_version = None
    compare_version = None
    
    for v in versions:
        if v["version_id"] == version_id:
            target_version = v
        if compare_to and v["version_id"] == compare_to:
            compare_version = v
    
    if not target_version:
        raise HTTPException(status_code=404, detail="target version not found")
    
    if compare_to and not compare_version:
        raise HTTPException(status_code=404, detail="comparison version not found")
    
    # In production, this would compute actual content diffs
    mock_diff = {
        "target_version": target_version,
        "compare_version": compare_version,
        "changes": {
            "sections_added": 1,
            "sections_modified": 2,
            "sections_removed": 0,
            "charts_added": 3,
            "citations_updated": 4
        },
        "diff_summary": "Added new data analysis section, updated market trends charts, refreshed citation sources"
    }
    
    return {"diff": mock_diff}

@router.post("/{page_id}/history/snapshot", status_code=201)
async def create_version_snapshot(page_id: str, description: Optional[str] = None):
    """Create a manual version snapshot"""
    # Verify page exists
    try:
        page = page_generator.load_page(page_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")
    
    version_id = uuid.uuid4().hex
    snapshot = {
        "version_id": version_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "author_id": "api",
        "summary": description or "Manual snapshot",
        "type": "snapshot",
        "content_hash": f"hash_{uuid.uuid4().hex[:8]}"  # In production, actual content hash
    }
    
    VERSIONS.setdefault(page_id, []).append(snapshot)
    
    return {"version_id": version_id, "snapshot": snapshot}


# Action-based unified endpoint for page operations
class PageActionRequest(BaseModel):
    action: str  # 'revert', 'share', 'export'
    # Revert fields
    version_id: Optional[str] = None
    reason: Optional[str] = None
    
    # Share fields  
    share_type: Optional[str] = None  # 'link' or 'users'
    expires_at: Optional[str] = None
    password: Optional[str] = None
    permissions: Optional[str] = None
    user_ids: Optional[List[str]] = None
    
    # Export fields
    format: Optional[str] = "pdf"  # 'pdf', 'html', 'markdown', 'docx'


# Unified action jobs tracker
ACTION_JOBS: Dict[str, Dict[str, Any]] = {}


@router.post("/{page_id}/actions", status_code=202)
async def execute_page_action(page_id: str, req: PageActionRequest):
    """Unified endpoint for page actions: revert, share, export"""
    
    # Verify page exists
    try:
        page_generator.load_page(page_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")
    
    job_id = uuid.uuid4().hex
    
    if req.action == "revert":
        if not req.version_id:
            raise HTTPException(status_code=400, detail="version_id required for revert")
        
        ACTION_JOBS[job_id] = {
            "status": "processing",
            "action": "revert",
            "page_id": page_id,
            "version_id": req.version_id,
            "reason": req.reason
        }
        
        # Create new version representing the revert
        ver_id = uuid.uuid4().hex
        VERSIONS.setdefault(page_id, []).append({
            "version_id": ver_id,
            "timestamp": "now", 
            "author_id": "api",
            "summary": f"reverted to {req.version_id}: {req.reason or 'no reason'}"
        })
        
        ACTION_JOBS[job_id].update({"status": "completed", "result_version_id": ver_id})
        
    elif req.action == "share":
        if not req.share_type:
            raise HTTPException(status_code=400, detail="share_type required for share")
            
        ACTION_JOBS[job_id] = {
            "status": "processing",
            "action": "share", 
            "page_id": page_id,
            "share_type": req.share_type
        }
        
        if req.share_type == "link":
            token = uuid.uuid4().hex
            url = f"/shared/{token}"
            
            # Store public share with metadata
            PUBLIC_PAGES[token] = {
                "page_id": page_id,
                "created_at": datetime.utcnow().isoformat(),
                "password": req.password,  # None if no password
                "access_count": 0,
                "expires_at": req.expires_at,
                "permissions": req.permissions or "read"
            }
            
            SHARES.setdefault(page_id, []).append({
                "type": "link",
                "token": token,
                "expires_at": req.expires_at,
                "permissions": req.permissions or "read"
            })
            ACTION_JOBS[job_id].update({
                "status": "completed",
                "share_url": url,
                "token": token,
                "expires_at": req.expires_at,
                "password_protected": bool(req.password)
            })
            
        elif req.share_type == "users":
            if not req.user_ids:
                raise HTTPException(status_code=400, detail="user_ids required for user sharing")
            
            shared_users = [{"user_id": uid, "permissions": req.permissions or "read"} for uid in req.user_ids]
            SHARES.setdefault(page_id, []).append({
                "type": "users",
                "entries": shared_users
            })
            ACTION_JOBS[job_id].update({
                "status": "completed",
                "shared_users": shared_users
            })
    
    elif req.action == "export":
        ACTION_JOBS[job_id] = {
            "status": "processing",
            "action": "export",
            "page_id": page_id,
            "format": req.format
        }
        
        # TODO: Implement actual export logic
        # For now, simulate completion
        ACTION_JOBS[job_id].update({
            "status": "completed", 
            "download_url": f"/api/pages/{page_id}/download/{job_id}.{req.format}"
        })
        
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")
    
    return {"job_id": job_id, "status_url": f"/api/pages/actions/{job_id}"}


@router.get("/actions/{job_id}")
async def get_action_status(job_id: str):
    """Get status of any page action (revert, share, export)"""
    job = ACTION_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="action job not found")
    return job


# Week 3: Interactive blocks and section-level refresh endpoints

@router.post("/{page_id}/sections/{section_id}/refresh", status_code=202)
async def refresh_section(page_id: str, section_id: str, req: SectionRefreshRequest):
    """Refresh a specific section with enhanced content using AI.
    
    Supports actions: expand, simplify, add_examples, cite_more, regenerate
    """
    # Verify page exists
    try:
        page = page_generator.load_page(page_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")
    
    # Find the section
    target_section = None
    for section in page.get("sections", []):
        if section.get("id") == section_id:
            target_section = section
            break
    
    if not target_section:
        raise HTTPException(status_code=404, detail="section not found")
    
    # Create refresh job
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "status": "pending",
        "page_id": page_id,
        "section_id": section_id,
        "action": req.action,
        "instruction": req.instruction
    }
    
    # Start async refresh task
    asyncio.create_task(_refresh_section_job(job_id, page_id, section_id, req, page, target_section))
    
    return {"job_id": job_id, "status_url": f"/api/pages/refresh/{job_id}"}


@router.get("/refresh/{job_id}")
async def get_refresh_status(job_id: str):
    """Get status of section refresh job"""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="refresh job not found")
    return job


@router.post("/{page_id}/widgets", status_code=201)
async def add_widget(page_id: str, req: WidgetRequest):
    """Add an interactive widget to a page"""
    try:
        page = page_generator.load_page(page_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")
    
    # Create widget
    widget_id = f"widget_{uuid.uuid4().hex[:8]}"
    widget = {
        "id": widget_id,
        "type": req.widget_type,
        "config": req.config,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "active": True
    }
    
    # Add to first section that supports widgets
    for section in page.get("sections", []):
        if "widgets" in section:
            section["widgets"].append(widget)
            break
    else:
        # If no section has widgets, add to overview section
        if page.get("sections"):
            page["sections"][0].setdefault("widgets", []).append(widget)
    
    # Save page
    import json
    from pathlib import Path
    DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "pages"
    path = DATA_DIR / f"{page_id}.json"
    path.write_text(json.dumps(page, indent=2), encoding="utf-8")
    
    return {"widget_id": widget_id, "message": "Widget added successfully"}


@router.delete("/{page_id}/widgets/{widget_id}")
async def remove_widget(page_id: str, widget_id: str):
    """Remove a widget from a page"""
    try:
        page = page_generator.load_page(page_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")
    
    # Find and remove widget
    removed = False
    for section in page.get("sections", []):
        if "widgets" in section:
            section["widgets"] = [w for w in section["widgets"] if w.get("id") != widget_id]
            if any(w.get("id") == widget_id for w in section.get("widgets", [])):
                removed = True
    
    if not removed:
        raise HTTPException(status_code=404, detail="widget not found")
    
    # Save page
    import json
    from pathlib import Path
    DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "pages"
    path = DATA_DIR / f"{page_id}.json"
    path.write_text(json.dumps(page, indent=2), encoding="utf-8")
    
    return {"message": "Widget removed successfully"}


@router.post("/{page_id}/copilot/chat", status_code=200)
async def copilot_chat(page_id: str, message: str = Query(..., description="Chat message for the copilot")):
    """Chat with the embedded copilot for a specific page"""
    try:
        page = page_generator.load_page(page_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")
    
    # Simple copilot response based on page content
    page_context = {
        "title": page.get("title", ""),
        "query": page.get("query", ""),
        "sections_count": len(page.get("sections", [])),
        "citations_count": len(page.get("citations", {}))
    }
    
    # Generate contextual response
    if "expand" in message.lower():
        response = f"I can help you expand any section of '{page_context['title']}'. Which specific topic would you like me to elaborate on?"
    elif "chart" in message.lower() or "data" in message.lower():
        response = f"This page contains data visualizations. I can help you understand the {page_context['citations_count']} sources or explain specific metrics in detail."
    elif "source" in message.lower() or "citation" in message.lower():
        response = f"This analysis is based on {page_context['citations_count']} credible sources. Would you like me to highlight specific research findings?"
    else:
        response = f"Hello! I'm here to help you with '{page_context['title']}'. I can expand sections, explain data, find additional sources, or answer specific questions about {page_context['query']}."
    
    return {
        "response": response,
        "context": page_context,
        "suggestions": [
            "Expand the overview section",
            "Show me more data visualizations", 
            "Find additional sources",
            "Explain the key findings"
        ]
    }


async def _refresh_section_job(job_id: str, page_id: str, section_id: str, req: SectionRefreshRequest, page: Dict[str, Any], section: Dict[str, Any]):
    """Background task to refresh a section with enhanced content"""
    try:
        JOBS[job_id]["status"] = "running"
        
        # Import section agents
        from content.section_agents import (
            overview_generate_section, detail_generate_section, 
            data_generate_section, source_generate_section, 
            comparison_generate_section
        )
        
        # Get original query and create enhanced query based on action
        original_query = page.get("query", "")
        enhanced_query = original_query
        
        if req.action == "expand":
            enhanced_query = f"{original_query} detailed analysis expanded"
        elif req.action == "simplify":
            enhanced_query = f"{original_query} simplified explanation"
        elif req.action == "add_examples":
            enhanced_query = f"{original_query} examples and case studies"
        elif req.action == "cite_more":
            enhanced_query = f"{original_query} additional sources research"
        
        # Add custom instruction if provided
        if req.instruction:
            enhanced_query += f" {req.instruction}"
        
        # Get fresh Oracle data
        from content import oracle_client
        oracle_resp = oracle_client.search_oracle(enhanced_query, k=5)
        resources = {"oracle_results": oracle_resp.get("results", [])}
        
        # Regenerate section based on type
        section_type = section.get("type")
        if section_type == "overview":
            new_section = await overview_generate_section(enhanced_query, page, resources)
        elif section_type == "detail":
            new_section = await detail_generate_section(enhanced_query, page, resources)
        elif section_type == "data":
            new_section = await data_generate_section(enhanced_query, page, resources)
        elif section_type == "source":
            new_section = await source_generate_section(enhanced_query, page, resources)
        elif section_type == "comparison":
            new_section = await comparison_generate_section(enhanced_query, page, resources)
        else:
            raise ValueError(f"Unknown section type: {section_type}")
        
        # Update section in page
        for i, sect in enumerate(page["sections"]):
            if sect.get("id") == section_id:
                # Preserve original ID and add refresh metadata
                new_section["id"] = section_id
                new_section.setdefault("metadata", {})["refreshed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                new_section.setdefault("metadata", {})["refresh_action"] = req.action
                page["sections"][i] = new_section
                break
        
        # Save updated page
        import json
        from pathlib import Path
        DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "pages"
        path = DATA_DIR / f"{page_id}.json"
        path.write_text(json.dumps(page, indent=2), encoding="utf-8")
        
        # Update job status
        JOBS[job_id]["status"] = "completed" 
        JOBS[job_id]["section"] = new_section
        
    except Exception as e:
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(e)


# Public Access Endpoints for Shared Pages

@router.get("/shared/{token}")
async def get_shared_page(token: str, password: Optional[str] = None):
    """Access a publicly shared page via token"""
    
    if token not in PUBLIC_PAGES:
        raise HTTPException(status_code=404, detail="Shared page not found")
    
    share_info = PUBLIC_PAGES[token]
    
    # Check if password is required
    if share_info.get("password") and password != share_info["password"]:
        raise HTTPException(status_code=401, detail="Password required or incorrect")
    
    # Check expiration
    if share_info.get("expires_at"):
        from datetime import datetime
        expires = datetime.fromisoformat(share_info["expires_at"])
        if datetime.utcnow() > expires:
            raise HTTPException(status_code=410, detail="Shared link has expired")
    
    # Increment access count
    PUBLIC_PAGES[token]["access_count"] += 1
    
    # Get the actual page
    page_id = share_info["page_id"]
    from pathlib import Path
    import json
    
    DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "pages"
    path = DATA_DIR / f"{page_id}.json"
    
    if not path.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    
    page = json.loads(path.read_text(encoding="utf-8"))
    
    # Add sharing metadata to response
    page["shared_via"] = {
        "token": token,
        "access_count": share_info["access_count"],
        "shared_at": share_info["created_at"],
        "permissions": share_info.get("permissions", "read")
    }
    
    return page


@router.get("/shared/{token}/info")
async def get_shared_page_info(token: str):
    """Get metadata about a shared page without accessing the content"""
    
    if token not in PUBLIC_PAGES:
        raise HTTPException(status_code=404, detail="Shared page not found")
    
    share_info = PUBLIC_PAGES[token]
    
    # Get basic page info
    page_id = share_info["page_id"]
    from pathlib import Path
    import json
    
    DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "pages"
    path = DATA_DIR / f"{page_id}.json"
    
    if not path.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    
    page = json.loads(path.read_text(encoding="utf-8"))
    
    return {
        "title": page.get("title", "Untitled"),
        "query": page.get("query", ""),
        "template": page.get("template", "unknown"),
        "sections_count": len(page.get("sections", [])),
        "shared_at": share_info["created_at"],
        "access_count": share_info["access_count"],
        "password_protected": bool(share_info.get("password")),
        "permissions": share_info.get("permissions", "read"),
        "expires_at": share_info.get("expires_at")
    }


@router.get("/{page_id}/versions")
async def get_page_versions(page_id: str):
    """Get version history for a page"""
    
    # Check if page exists
    from pathlib import Path
    import json
    
    DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "pages"
    path = DATA_DIR / f"{page_id}.json"
    
    if not path.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    
    versions = VERSIONS.get(page_id, [])
    
    # Add current version
    current_page = json.loads(path.read_text(encoding="utf-8"))
    current_version = {
        "version": len(versions) + 1,
        "created_at": current_page.get("created_at", "unknown"),
        "created_by": current_page.get("created_by", "system"),
        "query": current_page.get("query", ""),
        "sections_count": len(current_page.get("sections", [])),
        "is_current": True
    }
    
    return {
        "page_id": page_id,
        "current_version": current_version,
        "version_history": versions,
        "total_versions": len(versions) + 1
    }


@router.post("/{page_id}/versions")
async def create_page_version(page_id: str, description: Optional[str] = None):
    """Create a new version snapshot of a page"""
    
    from pathlib import Path
    import json
    from datetime import datetime
    
    DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "pages"
    path = DATA_DIR / f"{page_id}.json"
    
    if not path.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Load current page
    current_page = json.loads(path.read_text(encoding="utf-8"))
    
    # Create version snapshot
    version_entry = {
        "version": len(VERSIONS.get(page_id, [])) + 1,
        "created_at": datetime.utcnow().isoformat(),
        "description": description or f"Version snapshot {len(VERSIONS.get(page_id, [])) + 1}",
        "query": current_page.get("query", ""),
        "sections_count": len(current_page.get("sections", [])),
        "snapshot": current_page.copy()  # Full page snapshot
    }
    
    # Store version
    VERSIONS.setdefault(page_id, []).append(version_entry)
    
    return {
        "version_created": version_entry["version"],
        "description": version_entry["description"],
        "created_at": version_entry["created_at"]
    }
