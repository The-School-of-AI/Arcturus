import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from core.json_parser import parse_llm_json
from core.model_manager import ModelManager

logger = logging.getLogger(__name__)
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

        # Document-specific outline normalization
        if artifact_type == ArtifactType.document:
            from core.studio.documents.generator import normalize_document_outline
            outline = normalize_document_outline(outline, parameters, prompt)

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

            # Phase 3: notes quality repair pass
            from core.studio.slides.notes import repair_speaker_notes
            content_tree_model = repair_speaker_notes(content_tree_model)

        # Document-specific: normalize content tree
        elif artifact.type == ArtifactType.document:
            from core.studio.documents.generator import normalize_document_content_tree
            content_tree_model = normalize_document_content_tree(
                content_tree_model, outline=artifact.outline, artifact_id=artifact_id
            )

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
        strict_layout: bool = False,
        generate_images: bool = False,
    ) -> Dict[str, Any]:
        """Export an artifact to the specified format.

        Supported combinations:
        - slides → pptx
        - document → docx, pdf
        - sheet → (Phase 5)

        When generate_images=True, the heavy work runs in the background
        and the pending job is returned immediately for polling.
        Returns the export job dict.
        """
        from core.schemas.studio_schema import (
            ExportFormat,
            ExportJob,
            ExportJobSummary,
            ExportStatus,
        )

        # Load and verify artifact
        artifact = self.storage.load_artifact(artifact_id)
        if artifact is None:
            raise ValueError(f"Artifact not found: {artifact_id}")
        if artifact.content_tree is None:
            raise ValueError(f"Artifact {artifact_id} has no content tree (approve outline first)")

        # Validate artifact type / format combinations
        _VALID_COMBOS = {
            ArtifactType.slides: {ExportFormat.pptx},
            ArtifactType.document: {ExportFormat.docx, ExportFormat.pdf},
        }
        valid_formats = _VALID_COMBOS.get(artifact.type)
        if valid_formats is None:
            raise ValueError(f"Export not yet supported for {artifact.type.value} artifacts")
        if export_format not in valid_formats:
            raise ValueError(
                f"Format {export_format.value} not supported for {artifact.type.value} artifacts "
                f"(supported: {', '.join(f.value for f in valid_formats)})"
            )

        # Reject slides-only params for document exports
        if artifact.type == ArtifactType.document:
            if theme_id:
                raise ValueError("theme_id is not supported for document exports")
            if strict_layout:
                raise ValueError("strict_layout is not supported for document exports")
            if generate_images:
                raise ValueError("generate_images is not supported for document exports")

        # Resolve theme for slides
        theme = None
        if artifact.type == ArtifactType.slides:
            from core.studio.slides.themes import get_theme
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

        # Record the pending job on the artifact immediately
        artifact.exports.append(ExportJobSummary(
            id=export_job.id,
            format=export_job.format.value,
            status=export_job.status.value,
            created_at=export_job.created_at,
        ))
        artifact.updated_at = datetime.now(timezone.utc)
        self.storage.save_artifact(artifact)

        if artifact.type == ArtifactType.slides and generate_images:
            # Run heavy work in background — return pending job immediately
            asyncio.create_task(self._run_export(
                artifact_id, export_job, artifact.content_tree,
                theme, strict_layout, generate_images,
            ))
            return export_job.model_dump(mode="json")

        # Synchronous path — fast, complete inline
        if artifact.type == ArtifactType.document:
            await self._run_document_export(
                artifact_id, export_job, artifact.content_tree,
            )
        else:
            await self._run_export(
                artifact_id, export_job, artifact.content_tree,
                theme, strict_layout, generate_images,
            )
        return export_job.model_dump(mode="json")

    async def _run_export(
        self,
        artifact_id: str,
        export_job: Any,
        content_tree_dict: dict,
        theme: Any,
        strict_layout: bool,
        generate_images: bool,
    ) -> None:
        """Execute the actual export work (image generation + PPTX rendering)."""
        from core.schemas.studio_schema import (
            ExportStatus,
            SlidesContentTree,
        )
        from core.studio.slides.exporter import export_to_pptx
        from core.studio.slides.validator import validate_pptx

        try:
            content_tree_model = SlidesContentTree(**content_tree_dict)

            # Non-persisting notes repair for pre-Phase3 artifacts
            from core.studio.slides.notes import repair_speaker_notes
            export_content_tree = repair_speaker_notes(content_tree_model)

            # Generate images if requested
            slide_images = None
            if generate_images:
                try:
                    from core.studio.slides.images import generate_slide_images
                    slide_images = await generate_slide_images(export_content_tree)
                except Exception as img_err:
                    logger.warning(
                        "Image generation failed, exporting without images: %s", img_err
                    )

            output_path = self.storage.get_export_file_path(
                artifact_id, export_job.id, export_job.format.value
            )
            export_to_pptx(export_content_tree, theme, output_path, images=slide_images)

            validation = validate_pptx(
                output_path,
                expected_slide_count=len(content_tree_model.slides),
                content_tree=export_content_tree,
            )

            layout_ok = validation.get("layout_valid", True) or not strict_layout
            if validation["valid"] and layout_ok:
                export_job.status = ExportStatus.completed
                export_job.output_uri = str(output_path)
                export_job.file_size_bytes = output_path.stat().st_size
                validation["strict_layout"] = strict_layout
                export_job.validator_results = validation
                export_job.completed_at = datetime.now(timezone.utc)
            else:
                export_job.status = ExportStatus.failed
                all_errors = validation.get("errors", []) + validation.get("layout_errors", [])
                export_job.error = "; ".join(all_errors) if all_errors else "Quality validation failed"
                validation["strict_layout"] = strict_layout
                export_job.validator_results = validation
                export_job.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            export_job.status = ExportStatus.failed
            export_job.error = str(e)
            export_job.completed_at = datetime.now(timezone.utc)

        self.storage.save_export_job(export_job)

        # Update the artifact's exports summary with the final status
        artifact = self.storage.load_artifact(artifact_id)
        if artifact is not None:
            for summary in artifact.exports:
                if summary.id == export_job.id:
                    summary.status = export_job.status.value
                    break
            artifact.updated_at = datetime.now(timezone.utc)
            self.storage.save_artifact(artifact)


    async def _run_document_export(
        self,
        artifact_id: str,
        export_job: Any,
        content_tree_dict: dict,
    ) -> None:
        """Execute document export (DOCX or PDF)."""
        from core.schemas.studio_schema import (
            DocumentContentTree,
            ExportFormat,
            ExportStatus,
        )

        try:
            content_tree_model = DocumentContentTree(**content_tree_dict)

            output_path = self.storage.get_export_file_path(
                artifact_id, export_job.id, export_job.format.value
            )

            if export_job.format == ExportFormat.docx:
                from core.studio.documents.exporter_docx import export_to_docx
                from core.studio.documents.validator import validate_docx
                export_to_docx(content_tree_model, output_path)
                validation = validate_docx(output_path, content_tree_model)
            elif export_job.format == ExportFormat.pdf:
                from core.studio.documents.exporter_pdf import export_to_pdf
                from core.studio.documents.validator import validate_pdf
                export_to_pdf(content_tree_model, output_path)
                validation = validate_pdf(output_path, content_tree_model)
            else:
                raise ValueError(f"Unsupported document format: {export_job.format.value}")

            if validation["valid"]:
                export_job.status = ExportStatus.completed
                export_job.output_uri = str(output_path)
                export_job.file_size_bytes = output_path.stat().st_size
                export_job.validator_results = validation
                export_job.completed_at = datetime.now(timezone.utc)
            else:
                export_job.status = ExportStatus.failed
                export_job.error = "; ".join(validation.get("errors", [])) or "Validation failed"
                export_job.validator_results = validation
                export_job.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            export_job.status = ExportStatus.failed
            export_job.error = str(e)
            export_job.completed_at = datetime.now(timezone.utc)

        self.storage.save_export_job(export_job)

        # Update the artifact's exports summary with the final status
        artifact = self.storage.load_artifact(artifact_id)
        if artifact is not None:
            for summary in artifact.exports:
                if summary.id == export_job.id:
                    summary.status = export_job.status.value
                    break
            artifact.updated_at = datetime.now(timezone.utc)
            self.storage.save_artifact(artifact)


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
