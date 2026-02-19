from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError
from typing import Dict, Optional

from core.schemas.studio_schema import ArtifactType
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


# === Helpers ===

def _get_orchestrator() -> ForgeOrchestrator:
    return ForgeOrchestrator(get_studio_storage())


# === Endpoints ===

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


@router.get("/{artifact_id}")
async def get_artifact(artifact_id: str):
    """Retrieve a full artifact by ID."""
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
    try:
        storage = get_studio_storage()
        return storage.list_revisions(artifact_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{artifact_id}/revisions/{revision_id}")
async def get_revision(artifact_id: str, revision_id: str):
    """Get a specific revision."""
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
