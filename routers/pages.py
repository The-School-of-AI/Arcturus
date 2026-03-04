from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import asyncio
import uuid

from content import page_generator

router = APIRouter(prefix="/pages", tags=["Pages"])


class GenerateRequest(BaseModel):
    query: str
    template: Optional[str] = "topic_overview"


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


# Minimal in-memory placeholders for stub behavior
PAGES_META: Dict[str, Dict[str, Any]] = {}
FOLDERS: Dict[str, Dict[str, Any]] = {}
SHARES: Dict[str, Any] = {}
VERSIONS: Dict[str, List[Dict[str, Any]]] = {}


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
async def list_versions(page_id: str):
    versions = VERSIONS.get(page_id, [])
    return {"versions": versions}


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
                "expires_at": req.expires_at
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
