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


@router.get("/{page_id}")
async def get_page(page_id: str):
    try:
        page = page_generator.load_page(page_id)
        return page
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="page not found")


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
EXPORT_JOBS: Dict[str, Dict[str, Any]] = {}


@router.get("", response_model=ListResponse)
async def list_pages(q: Optional[str] = None, folder_id: Optional[str] = None, tags: Optional[str] = None, page: int = 1, per_page: int = 25):
    """List pages (stub). Supports basic pagination and optional filters."""
    # Try to delegate to page_generator if available
    try:
        if hasattr(page_generator, "list_pages"):
            results = page_generator.list_pages(q=q, folder_id=folder_id, tags=tags, page=page, per_page=per_page)
            return results
    except Exception:
        pass

    # Fallback: return entries from in-memory PAGES_META
    items = []
    for pid, meta in list(PAGES_META.items()):
        items.append(PageListItem(id=pid, title=meta.get("title", "Untitled"), excerpt=meta.get("excerpt"), tags=meta.get("tags", []), folder_id=meta.get("folder_id"), owner_id=meta.get("owner_id"), updated_at=meta.get("updated_at")))

    start = (page - 1) * per_page
    sliced = items[start:start + per_page]
    return {"items": sliced, "total": len(items), "page": page, "per_page": per_page}


class CreateFolderRequest(BaseModel):
    name: str
    parent_id: Optional[str] = None
    description: Optional[str] = ""


@router.post("/folders", status_code=201)
async def create_folder(req: CreateFolderRequest):
    fid = uuid.uuid4().hex
    FOLDERS[fid] = {"id": fid, "name": req.name, "parent_id": req.parent_id, "description": req.description}
    return {"id": fid, "name": req.name}


class UpdatePageMetadata(BaseModel):
    title: Optional[str]
    tags: Optional[List[str]]
    folder_id: Optional[str]
    visibility: Optional[str]


@router.patch("/{page_id}")
async def update_page_metadata(page_id: str, req: UpdatePageMetadata):
    # Apply changes to in-memory meta; real implementation should persist and version
    meta = PAGES_META.setdefault(page_id, {})
    for k, v in req.dict(exclude_unset=True).items():
        meta[k] = v
    # create a new version marker
    ver_id = uuid.uuid4().hex
    VERSIONS.setdefault(page_id, []).append({"version_id": ver_id, "timestamp": "now", "author_id": "api", "summary": "metadata update"})
    return {"id": page_id, "version_id": ver_id}


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


class RevertRequest(BaseModel):
    version_id: str
    reason: Optional[str]


@router.post("/{page_id}/revert")
async def revert_page(page_id: str, req: RevertRequest):
    # Stub: create a new version representing the revert
    ver_id = uuid.uuid4().hex
    VERSIONS.setdefault(page_id, []).append({"version_id": ver_id, "timestamp": "now", "author_id": "api", "summary": f"reverted to {req.version_id}"})
    return {"id": page_id, "version_id": ver_id}


class ShareUser(BaseModel):
    user_id: str
    permissions: str


class ShareRequest(BaseModel):
    type: str  # 'link' or 'users'
    expires_at: Optional[str]
    password: Optional[str]
    permissions: Optional[str]
    users: Optional[List[ShareUser]]


@router.post("/{page_id}/share", status_code=201)
async def share_page(page_id: str, req: ShareRequest):
    if req.type == "link":
        token = uuid.uuid4().hex
        url = f"/share/{token}"
        SHARES.setdefault(page_id, []).append({"type": "link", "token": token, "expires_at": req.expires_at, "permissions": req.permissions})
        return {"share_url": url, "token": token, "expires_at": req.expires_at}

    added = []
    failed = []
    if req.users:
        for u in req.users:
            # naive add
            added.append({"user_id": u.user_id, "permissions": u.permissions})
        SHARES.setdefault(page_id, []).append({"type": "users", "entries": added})
    return {"added": added, "failed": failed}


@router.post("/{page_id}/export", status_code=202)
async def export_page(page_id: str, format: str = "pdf"):
    job_id = uuid.uuid4().hex
    EXPORT_JOBS[job_id] = {"status": "queued", "page_id": page_id, "format": format}
    return {"job_id": job_id, "status_url": f"/pages/export/jobs/{job_id}"}


@router.get("/export/jobs/{job_id}")
async def get_export_job(job_id: str):
    job = EXPORT_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="export job not found")
    return job
