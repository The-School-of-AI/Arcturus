from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from core.json_parser import parse_llm_json
from core.model_manager import ModelManager
from core.schemas.studio_schema import (
    Artifact,
    ArtifactType,
    Outline,
    OutlineItem,
    OutlineStatus,
    validate_content_tree,
)
from core.studio.prompts import get_draft_prompt, get_draft_prompt_with_sequence, get_outline_prompt
from core.studio.revision import RevisionManager, compute_change_summary
from core.studio.storage import StudioStorage


class ForgeOrchestrator:
    """Outline-first generation pipeline for Forge artifacts."""

    def __init__(self, storage: StudioStorage):
        self.storage = storage
        self.revision_manager = RevisionManager(storage)

    async def generate_outline(
        self,
        prompt: str,
        artifact_type: ArtifactType,
        parameters: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate an outline for a new artifact.

        Returns dict with artifact_id, outline, and status.
        """
        parameters = parameters or {}

        # Build prompt and call LLM
        llm_prompt = get_outline_prompt(artifact_type, prompt, parameters)
        mm = ModelManager(model_name=model) if model else ModelManager()
        raw = await mm.generate_text(llm_prompt)

        # Parse LLM response
        parsed = parse_llm_json(raw, required_keys=["title", "items"])

        # Build outline items
        outline_items = [
            _parse_outline_item(item) for item in parsed["items"]
        ]

        outline_title = title.strip() if title and title.strip() else parsed["title"]

        outline = Outline(
            artifact_type=artifact_type,
            title=outline_title,
            items=outline_items,
            status=OutlineStatus.pending,
            parameters=parameters,
        )

        # Create artifact
        now = datetime.now(timezone.utc)
        artifact_id = str(uuid4())
        artifact = Artifact(
            id=artifact_id,
            type=artifact_type,
            title=outline.title,
            created_at=now,
            updated_at=now,
            model=model,
            outline=outline,
            content_tree=None,
        )

        self.storage.save_artifact(artifact)

        return {
            "artifact_id": artifact_id,
            "outline": outline.model_dump(mode="json"),
            "status": "pending",
        }

    async def approve_and_generate_draft(
        self,
        artifact_id: str,
        modifications: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Approve an outline and generate the full draft content tree.

        Returns the full artifact dict.
        """
        # Load artifact
        artifact = self.storage.load_artifact(artifact_id)
        if artifact is None:
            raise ValueError(f"Artifact not found: {artifact_id}")
        if artifact.outline is None:
            raise ValueError(f"Artifact {artifact_id} has no outline")

        # Apply optional modifications
        if modifications:
            _apply_outline_modifications(artifact, modifications)

        # Mark outline as approved
        artifact.outline.status = OutlineStatus.approved

        # Generate draft via LLM (slides-specific: inject sequence hints)
        if artifact.type == ArtifactType.slides:
            from core.studio.slides.generator import (
                clamp_slide_count,
                compute_seed,
                plan_slide_sequence,
            )
            seed = compute_seed(artifact.id)
            target_count = clamp_slide_count(
                artifact.outline.parameters.get("slide_count") if artifact.outline.parameters else None
            )
            sequence = plan_slide_sequence(target_count, seed)
            llm_prompt = get_draft_prompt_with_sequence(artifact.type, artifact.outline, sequence)
        else:
            llm_prompt = get_draft_prompt(artifact.type, artifact.outline)

        mm = ModelManager(model_name=artifact.model) if artifact.model else ModelManager()
        raw = await mm.generate_text(llm_prompt)

        # Parse and validate content tree
        parsed = parse_llm_json(raw)
        content_tree_model = validate_content_tree(artifact.type, parsed)

        # Slides-specific: enforce slide count range [8, 15]
        if artifact.type == ArtifactType.slides:
            from core.studio.slides.generator import enforce_slide_count
            content_tree_model = enforce_slide_count(content_tree_model)

        content_tree = content_tree_model.model_dump(mode="json")

        # Create revision
        change_summary = compute_change_summary(artifact.content_tree, content_tree)
        revision = self.revision_manager.create_revision(
            artifact_id=artifact_id,
            content_tree=content_tree,
            change_summary=change_summary,
            parent_revision_id=artifact.revision_head_id,
        )

        # Update artifact
        artifact.content_tree = content_tree
        artifact.revision_head_id = revision.id
        artifact.updated_at = datetime.now(timezone.utc)
        self.storage.save_artifact(artifact)

        return artifact.model_dump(mode="json")

    def reject_outline(
        self,
        artifact_id: str,
        modifications: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Reject an outline without generating draft content."""
        artifact = self.storage.load_artifact(artifact_id)
        if artifact is None:
            raise ValueError(f"Artifact not found: {artifact_id}")
        if artifact.outline is None:
            raise ValueError(f"Artifact {artifact_id} has no outline")

        if modifications:
            _apply_outline_modifications(artifact, modifications)

        artifact.outline.status = OutlineStatus.rejected
        artifact.updated_at = datetime.now(timezone.utc)
        self.storage.save_artifact(artifact)

        return artifact.model_dump(mode="json")

    async def export_artifact(
        self,
        artifact_id: str,
        export_format: "ExportFormat",
        theme_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Export an artifact to the specified format.

        Currently supports PPTX export for slides artifacts.
        Returns the export job dict.
        """
        from core.schemas.studio_schema import (
            ExportJob,
            ExportJobSummary,
            ExportStatus,
            SlidesContentTree,
        )
        from core.studio.slides.exporter import export_to_pptx
        from core.studio.slides.themes import get_theme
        from core.studio.slides.validator import validate_pptx

        # Load and verify artifact
        artifact = self.storage.load_artifact(artifact_id)
        if artifact is None:
            raise ValueError(f"Artifact not found: {artifact_id}")
        if artifact.content_tree is None:
            raise ValueError(f"Artifact {artifact_id} has no content tree (approve outline first)")
        if artifact.type != ArtifactType.slides:
            raise ValueError(f"Export format {export_format.value} only supports slides artifacts")

        # Resolve theme
        theme = get_theme(theme_id or artifact.theme_id)

        # Create export job
        now = datetime.now(timezone.utc)
        export_job_id = str(uuid4())
        export_job = ExportJob(
            id=export_job_id,
            artifact_id=artifact_id,
            format=export_format,
            status=ExportStatus.pending,
            created_at=now,
        )

        self.storage.save_export_job(export_job)

        try:
            content_tree_model = SlidesContentTree(**artifact.content_tree)

            output_path = self.storage.get_export_file_path(
                artifact_id, export_job_id, export_format.value
            )
            export_to_pptx(content_tree_model, theme, output_path)

            validation = validate_pptx(output_path, expected_slide_count=len(content_tree_model.slides))

            if validation["valid"]:
                export_job.status = ExportStatus.completed
                export_job.output_uri = str(output_path)
                export_job.file_size_bytes = output_path.stat().st_size
                export_job.validator_results = validation
                export_job.completed_at = datetime.now(timezone.utc)
            else:
                export_job.status = ExportStatus.failed
                export_job.error = "; ".join(validation["errors"])
                export_job.validator_results = validation
                export_job.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            export_job.status = ExportStatus.failed
            export_job.error = str(e)
            export_job.completed_at = datetime.now(timezone.utc)

        self.storage.save_export_job(export_job)

        artifact.exports.append(ExportJobSummary(
            id=export_job.id,
            format=export_job.format.value,
            status=export_job.status.value,
            created_at=export_job.created_at,
        ))
        artifact.updated_at = datetime.now(timezone.utc)
        self.storage.save_artifact(artifact)

        return export_job.model_dump(mode="json")


def _parse_outline_item(data: dict) -> OutlineItem:
    """Recursively parse an outline item dict into an OutlineItem model."""
    if not isinstance(data, dict):
        raise ValueError("Outline item must be an object")

    raw_children = data.get("children")
    if raw_children is None:
        child_items = []
    elif isinstance(raw_children, list):
        child_items = raw_children
    else:
        raise ValueError("Outline item 'children' must be a list")

    children = [_parse_outline_item(child) for child in child_items]
    return OutlineItem(
        id=str(data.get("id", "")),
        title=data.get("title", ""),
        description=data.get("description"),
        children=children,
    )


def _apply_outline_modifications(artifact: Artifact, modifications: Dict[str, Any]) -> None:
    """Apply user-provided outline modifications and keep artifact metadata aligned."""
    if "title" in modifications:
        title_value = modifications["title"]
        if title_value is not None:
            new_title = str(title_value).strip()
            if new_title:
                artifact.outline.title = new_title
                artifact.title = new_title
    if "items" in modifications:
        items_value = modifications["items"]
        if not isinstance(items_value, list):
            raise ValueError("Outline modification 'items' must be a list")
        artifact.outline.items = [
            _parse_outline_item(item) for item in items_value
        ]
