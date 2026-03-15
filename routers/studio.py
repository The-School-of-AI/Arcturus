import asyncio
import re
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, ValidationError
from typing import Dict, Literal, Optional

from core.schemas.studio_schema import ArtifactType, ExportFormat, ExportStatus
from core.studio.orchestrator import ForgeOrchestrator
from shared.state import get_studio_storage

router = APIRouter(prefix="/studio", tags=["Studio"])


# === Request Models ===

class CreateArtifactRequest(BaseModel):
    prompt: str
    title: Optional[str] = None
    parameters: Optional[Dict] = Field(default_factory=dict)
    model: Optional[str] = None


class ApproveOutlineRequest(BaseModel):
    approved: bool = True
    modifications: Optional[Dict] = None


class EditArtifactRequest(BaseModel):
    instruction: str
    base_revision_id: Optional[str] = None
    mode: Literal["apply", "dry_run"] = Field(default="apply", description="'apply' or 'dry_run'")


class ExportArtifactRequest(BaseModel):
    format: str = "pptx"
    theme_id: Optional[str] = None
    strict_layout: bool = False
    generate_images: bool = False


# === Validators ===

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _validate_artifact_id(artifact_id: str) -> str:
    if not _UUID_PATTERN.match(artifact_id):
        raise HTTPException(status_code=400, detail=f"Invalid artifact_id format: {artifact_id}")
    return artifact_id


def _validate_export_job_id(export_job_id: str) -> str:
    if not _UUID_PATTERN.match(export_job_id):
        raise HTTPException(status_code=400, detail=f"Invalid export_job_id format: {export_job_id}")
    return export_job_id


# === Helpers ===

def _get_orchestrator() -> ForgeOrchestrator:
    return ForgeOrchestrator(get_studio_storage())


# === Endpoints ===
# IMPORTANT: Static paths (/themes, /exports/{id}) BEFORE parameterized (/{artifact_id})

@router.post("/slides")
async def create_slides(request: CreateArtifactRequest):
    """Create a slides artifact; returns outline for approval."""
    return await _create_artifact(request, ArtifactType.slides)


@router.post("/documents")
async def create_document(request: CreateArtifactRequest):
    """Create a document artifact; returns outline for approval."""
    return await _create_artifact(request, ArtifactType.document)


@router.post("/sheets")
async def create_sheet(request: CreateArtifactRequest):
    """Create a sheet artifact; returns outline for approval."""
    return await _create_artifact(request, ArtifactType.sheet)


async def _create_artifact(request: CreateArtifactRequest, artifact_type: ArtifactType):
    """Shared handler for all three creation endpoints."""
    try:
        orchestrator = _get_orchestrator()
        result = await orchestrator.generate_outline(
            prompt=request.prompt,
            artifact_type=artifact_type,
            parameters=request.parameters,
            title=request.title,
            model=request.model,
        )
        return result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        detail = str(e)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{artifact_id}/outline/approve")
async def approve_outline(artifact_id: str, request: ApproveOutlineRequest):
    """Approve an outline and generate the draft content tree."""
    _validate_artifact_id(artifact_id)
    try:
        orchestrator = _get_orchestrator()
        if request.approved:
            result = await orchestrator.approve_and_generate_draft(
                artifact_id=artifact_id,
                modifications=request.modifications,
            )
        else:
            result = orchestrator.reject_outline(
                artifact_id=artifact_id,
                modifications=request.modifications,
            )
        return result
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        detail = str(e)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{artifact_id}/edit")
async def edit_artifact(artifact_id: str, request: EditArtifactRequest):
    """Apply a chat-driven edit to an existing artifact."""
    _validate_artifact_id(artifact_id)
    if not request.instruction or not request.instruction.strip():
        raise HTTPException(status_code=400, detail="Edit instruction must not be empty")
    try:
        from core.studio.orchestrator import ConflictError
        orchestrator = _get_orchestrator()
        result = await orchestrator.edit_artifact(
            artifact_id=artifact_id,
            instruction=request.instruction.strip(),
            base_revision_id=request.base_revision_id,
            mode=request.mode,
        )
        return result
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        detail = str(e)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Static GET routes MUST come before /{artifact_id} ---

@router.get("/themes")
async def list_themes_endpoint(
    include_variants: bool = False,
    base_id: Optional[str] = None,
    limit: Optional[int] = None,
):
    """List available themes. Defaults to base themes only for backward compatibility."""
    from core.studio.slides.themes import list_themes
    themes = list_themes(
        include_variants=include_variants,
        base_id=base_id,
        limit=limit,
    )
    return [t.model_dump() for t in themes]


@router.get("/{artifact_id}/images")
async def list_slide_images(artifact_id: str):
    """List slide IDs that have cached preview images."""
    _validate_artifact_id(artifact_id)
    storage = get_studio_storage()
    return {"slide_ids": storage.list_slide_images(artifact_id)}


@router.get("/{artifact_id}/images/{slide_id}")
async def get_slide_image(artifact_id: str, slide_id: str):
    """Serve a cached slide image as JPEG."""
    _validate_artifact_id(artifact_id)
    storage = get_studio_storage()
    image_path = storage.load_slide_image_path(artifact_id, slide_id)
    if image_path is None:
        raise HTTPException(status_code=404, detail="Image not yet generated")

    # Path traversal guard
    expected_base = storage.base_dir / artifact_id / "images"
    if not image_path.resolve().is_relative_to(expected_base.resolve()):
        raise HTTPException(status_code=400, detail="Invalid image path")

    return FileResponse(path=str(image_path), media_type="image/jpeg")


@router.post("/{artifact_id}/generate-images")
async def trigger_image_generation(artifact_id: str):
    """Manually trigger (or re-trigger) image generation for a slides artifact."""
    _validate_artifact_id(artifact_id)
    storage = get_studio_storage()
    artifact = storage.load_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_id}")
    if artifact.type != ArtifactType.slides:
        raise HTTPException(status_code=400, detail="Image generation only supported for slides")
    if artifact.content_tree is None:
        raise HTTPException(status_code=400, detail="No content tree (approve outline first)")

    orchestrator = _get_orchestrator()
    version = ForgeOrchestrator._image_gen_version[artifact_id] = ForgeOrchestrator._image_gen_version.get(artifact_id, 0) + 1
    asyncio.create_task(
        orchestrator._generate_and_cache_images(artifact_id, artifact.content_tree, version)
    )
    return {"status": "generating"}


@router.get("/exports/{export_job_id}")
async def get_export_job_global(export_job_id: str):
    """Get an export job by ID without requiring artifact_id."""
    _validate_export_job_id(export_job_id)
    storage = get_studio_storage()
    result = storage.find_export_job(export_job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Export job not found: {export_job_id}")
    _artifact_id, job = result
    return job.model_dump(mode="json")


# --- Parameterized GET routes ---

@router.get("/{artifact_id}")
async def get_artifact(artifact_id: str):
    """Retrieve a full artifact by ID."""
    _validate_artifact_id(artifact_id)
    try:
        storage = get_studio_storage()
        artifact = storage.load_artifact(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_id}")
        return artifact.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_artifacts():
    """List all artifacts."""
    try:
        storage = get_studio_storage()
        return storage.list_artifacts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
async def clear_all_artifacts():
    """Delete all artifacts and their exports."""
    try:
        storage = get_studio_storage()
        artifacts = storage.list_artifacts()
        for a in artifacts:
            storage.delete_artifact(a["id"])
        return {"deleted": len(artifacts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{artifact_id}")
async def delete_artifact(artifact_id: str):
    """Delete a single artifact by ID."""
    _validate_artifact_id(artifact_id)
    storage = get_studio_storage()
    if storage.load_artifact(artifact_id) is None:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_id}")
    storage.delete_artifact(artifact_id)
    return Response(status_code=204)


@router.get("/{artifact_id}/revisions")
async def list_revisions(artifact_id: str):
    """List all revisions for an artifact."""
    _validate_artifact_id(artifact_id)
    try:
        storage = get_studio_storage()
        return storage.list_revisions(artifact_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{artifact_id}/revisions/{revision_id}")
async def get_revision(artifact_id: str, revision_id: str):
    """Get a specific revision."""
    _validate_artifact_id(artifact_id)
    try:
        storage = get_studio_storage()
        revision = storage.load_revision(artifact_id, revision_id)
        if revision is None:
            raise HTTPException(status_code=404, detail=f"Revision not found: {revision_id}")
        return revision.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RestoreRevisionRequest(BaseModel):
    base_revision_id: Optional[str] = None


@router.post("/{artifact_id}/revisions/{revision_id}/restore")
async def restore_revision(artifact_id: str, revision_id: str, request: RestoreRevisionRequest = RestoreRevisionRequest()):
    """Restore an artifact to a previous revision's content tree."""
    _validate_artifact_id(artifact_id)
    try:
        from core.studio.orchestrator import ConflictError
        orchestrator = _get_orchestrator()
        result = await orchestrator.restore_revision(
            artifact_id=artifact_id,
            target_revision_id=revision_id,
            base_revision_id=request.base_revision_id,
        )
        return result
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        detail = str(e)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Export endpoints ---

@router.post("/{artifact_id}/export")
async def export_artifact(artifact_id: str, request: ExportArtifactRequest):
    """Export an artifact to the specified format."""
    _validate_artifact_id(artifact_id)
    try:
        try:
            export_format = ExportFormat(request.format)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported export format: {request.format}")

        orchestrator = _get_orchestrator()
        result = await orchestrator.export_artifact(
            artifact_id=artifact_id,
            export_format=export_format,
            theme_id=request.theme_id,
            strict_layout=request.strict_layout,
            generate_images=request.generate_images,
        )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        detail = str(e)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{artifact_id}/sheets/analyze-upload")
async def analyze_sheet_upload(artifact_id: str, file: UploadFile = File(...)):
    """Upload a file for analysis against an existing sheet artifact."""
    _validate_artifact_id(artifact_id)
    try:
        content_bytes = await file.read()
        orchestrator = _get_orchestrator()
        result = await orchestrator.analyze_sheet_upload(
            artifact_id=artifact_id,
            filename=file.filename or "upload",
            content_bytes=content_bytes,
            content_type=file.content_type or "",
        )
        return result
    except ValueError as e:
        detail = str(e)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{artifact_id}/exports")
async def list_exports(artifact_id: str):
    """List all export jobs for an artifact."""
    _validate_artifact_id(artifact_id)
    try:
        storage = get_studio_storage()
        return storage.list_export_jobs(artifact_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{artifact_id}/exports/{export_job_id}")
async def get_export_job(artifact_id: str, export_job_id: str):
    """Get a specific export job status."""
    _validate_artifact_id(artifact_id)
    _validate_export_job_id(export_job_id)
    try:
        storage = get_studio_storage()
        job = storage.load_export_job(artifact_id, export_job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Export job not found: {export_job_id}")
        return job.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{artifact_id}/exports/{export_job_id}/download")
async def download_export(artifact_id: str, export_job_id: str):
    """Download an exported file."""
    _validate_artifact_id(artifact_id)
    _validate_export_job_id(export_job_id)
    storage = get_studio_storage()
    job = storage.load_export_job(artifact_id, export_job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Export job not found: {export_job_id}")
    if job.status != ExportStatus.completed:
        raise HTTPException(status_code=400, detail=f"Export job not completed: {job.status}")

    file_path = Path(job.output_uri)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Export file not found on disk")

    # Path traversal guard
    expected_base = storage.base_dir / artifact_id / "exports"
    if not file_path.resolve().is_relative_to(expected_base.resolve()):
        raise HTTPException(status_code=400, detail="Export file path outside expected directory")

    _EXPORT_MEDIA_TYPES = {
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
        "html": "text/html",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv",
        "zip": "application/zip",
    }
    actual_ext = file_path.suffix.lstrip(".")
    media_type = _EXPORT_MEDIA_TYPES.get(
        actual_ext,
        "application/octet-stream",
    )

    return FileResponse(
        path=str(file_path),
        filename=f"{artifact_id}.{actual_ext}",
        media_type=media_type,
    )
