import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from typing import Dict, Optional

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


class ExportArtifactRequest(BaseModel):
    format: str = "pptx"
    theme_id: Optional[str] = None


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


# --- Static GET routes MUST come before /{artifact_id} ---

@router.get("/themes")
async def list_themes_endpoint():
    """List all available themes."""
    from core.studio.slides.themes import list_themes
    return [t.model_dump() for t in list_themes()]


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

    return FileResponse(
        path=str(file_path),
        filename=f"{artifact_id}.{job.format.value}",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
