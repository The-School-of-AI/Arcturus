import asyncio
import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from core.json_parser import parse_llm_json
from core.model_manager import ModelManager

logger = logging.getLogger(__name__)


class ConflictError(Exception):
    """Raised when optimistic concurrency check fails (409 Conflict)."""
    pass
from core.schemas.studio_schema import (
    Artifact,
    ArtifactType,
    Outline,
    OutlineItem,
    OutlineStatus,
    validate_content_tree,
)
from core.studio.prompts import (
    get_draft_prompt,
    get_draft_prompt_with_sequence,
    get_outline_prompt,
    get_sheet_visual_repair_prompt,
)
from core.studio.revision import RevisionManager, compute_change_summary
from core.studio.storage import StudioStorage


class ForgeOrchestrator:
    """Outline-first generation pipeline for Forge artifacts."""

    # Monotonic counter per artifact to detect stale background image tasks.
    # Class-level so the version survives across per-request instances.
    _image_gen_version: dict[str, int] = {}

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

        # Document-specific: normalize raw LLM field names before validation
        if artifact.type == ArtifactType.document:
            logger.debug(
                "Raw LLM document output (truncated): %.500s", str(parsed)
            )
            from core.studio.documents.generator import normalize_document_content_tree_raw
            parsed = normalize_document_content_tree_raw(parsed)

        try:
            content_tree_model = validate_content_tree(artifact.type, parsed)
        except Exception:
            logger.warning(
                "Content tree validation failed. Raw parsed data: %s", parsed
            )
            raise

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

        # Sheet-specific: normalize content tree
        elif artifact.type == ArtifactType.sheet:
            from core.studio.sheets.generator import (
                merge_sheet_visual_metadata,
                needs_sheet_visual_repair,
                normalize_sheet_content_tree,
            )
            content_tree_model = normalize_sheet_content_tree(content_tree_model)

            if needs_sheet_visual_repair(content_tree_model):
                try:
                    repair_prompt = get_sheet_visual_repair_prompt(
                        artifact.outline,
                        content_tree_model.model_dump(mode="json"),
                    )
                    repair_raw = await mm.generate_text(repair_prompt)
                    repair_parsed = parse_llm_json(repair_raw)
                    merge_sheet_visual_metadata(
                        content_tree_model,
                        repair_parsed.get("metadata"),
                    )
                except Exception as repair_err:
                    logger.warning(
                        "Sheet visual repair pass failed; continuing with defaults: %s",
                        repair_err,
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

        # Auto-generate images in the background for slides with image elements
        if artifact.type == ArtifactType.slides:
            version = self._image_gen_version[artifact_id] = self._image_gen_version.get(artifact_id, 0) + 1
            asyncio.create_task(self._generate_and_cache_images(artifact_id, content_tree, version))

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
            ArtifactType.document: {ExportFormat.docx, ExportFormat.pdf, ExportFormat.html},
            ArtifactType.sheet: {ExportFormat.xlsx, ExportFormat.csv},
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
            if generate_images and export_format != ExportFormat.html:
                raise ValueError("generate_images is only supported for HTML document exports")

        # Reject slides/document-only params for sheet exports
        if artifact.type == ArtifactType.sheet:
            if theme_id:
                raise ValueError("theme_id is not supported for sheet exports")
            if strict_layout:
                raise ValueError("strict_layout is not supported for sheet exports")
            if generate_images:
                raise ValueError("generate_images is not supported for sheet exports")

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

        # HTML document with images — run in background (Gemini API call)
        if artifact.type == ArtifactType.document and generate_images:
            asyncio.create_task(self._run_document_export(
                artifact_id, export_job, artifact.content_tree,
                generate_images=True,
            ))
            return export_job.model_dump(mode="json")

        # Synchronous path — fast, complete inline
        if artifact.type == ArtifactType.sheet:
            await self._run_sheet_export(
                artifact_id, export_job, artifact.content_tree,
            )
        elif artifact.type == ArtifactType.document:
            await self._run_document_export(
                artifact_id, export_job, artifact.content_tree,
            )
        else:
            await self._run_export(
                artifact_id, export_job, artifact.content_tree,
                theme, strict_layout, generate_images,
            )
        return export_job.model_dump(mode="json")

    async def _generate_and_cache_images(
        self,
        artifact_id: str,
        content_tree_dict: dict,
        version: int,
    ) -> None:
        """Background task: generate slide images via Gemini and cache to disk."""
        try:
            from core.schemas.studio_schema import SlidesContentTree
            from core.studio.slides.images import generate_slide_images

            content_tree = SlidesContentTree(**content_tree_dict)
            images = await generate_slide_images(content_tree)

            # Skip writes if a newer generation was started (edit during generation)
            if self._image_gen_version.get(artifact_id, 0) != version:
                logger.info("Skipping stale image generation (v%d) for %s", version, artifact_id)
                return

            for slide_id, buf in images.items():
                buf.seek(0)
                self.storage.save_slide_image(artifact_id, slide_id, buf.read())

            logger.info("Cached %d slide images for artifact %s", len(images), artifact_id)
        except Exception as e:
            logger.warning("Background image generation failed for %s: %s", artifact_id, e)

    def _load_cached_images(self, artifact_id: str) -> dict[str, io.BytesIO]:
        """Load cached slide images from disk into BytesIO buffers."""
        images: dict[str, io.BytesIO] = {}
        for slide_id in self.storage.list_slide_images(artifact_id):
            path = self.storage.load_slide_image_path(artifact_id, slide_id)
            if path:
                images[slide_id] = io.BytesIO(path.read_bytes())
        return images

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

            if strict_layout:
                from core.studio.slides.layout import repair_layout
                export_content_tree = repair_layout(export_content_tree)

            # Load images: use cache + generate any missing ones
            slide_images = None
            if generate_images:
                cached = self._load_cached_images(artifact_id)

                # Determine which image slides still need generation
                required_ids = {
                    s.id for s in export_content_tree.slides
                    if s.slide_type in ("image_text", "image_full")
                    and any(el.type == "image" and el.content for el in s.elements)
                }
                missing_ids = required_ids - set(cached.keys())

                if missing_ids:
                    try:
                        from core.studio.slides.images import generate_slide_images
                        # Only generate for missing slides to avoid redundant API calls
                        missing_tree = SlidesContentTree(
                            deck_title=export_content_tree.deck_title,
                            slides=[s for s in export_content_tree.slides if s.id in missing_ids],
                        )
                        new_images = await generate_slide_images(missing_tree)
                        for sid, buf in new_images.items():
                            buf.seek(0)
                            self.storage.save_slide_image(artifact_id, sid, buf.read())
                            buf.seek(0)
                            cached[sid] = buf
                    except Exception as img_err:
                        logger.warning(
                            "Image generation failed, exporting with %d cached images: %s",
                            len(cached), img_err,
                        )

                if cached:
                    slide_images = cached
                    logger.info("Using %d images for export (%d from cache)", len(cached), len(cached) - len(missing_ids))

            output_path = self.storage.get_export_file_path(
                artifact_id, export_job.id, export_job.format.value
            )
            export_to_pptx(export_content_tree, theme, output_path, images=slide_images)

            validation = validate_pptx(
                output_path,
                expected_slide_count=len(content_tree_model.slides),
                content_tree=export_content_tree,
            )

            validation["strict_layout"] = strict_layout

            if validation["valid"]:
                export_job.status = ExportStatus.completed
                export_job.output_uri = str(output_path)
                export_job.file_size_bytes = output_path.stat().st_size
                export_job.validator_results = validation
                export_job.completed_at = datetime.now(timezone.utc)
            else:
                export_job.status = ExportStatus.failed
                export_job.error = "; ".join(validation.get("errors", [])) or "Quality validation failed"
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
        generate_images: bool = False,
    ) -> None:
        """Execute document export (DOCX, PDF, or HTML)."""
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
            elif export_job.format == ExportFormat.html:
                from core.studio.documents.exporter_html import export_to_html
                from core.studio.documents.validator import validate_html

                # Optional hero image generation
                hero_image_bytes = None
                if generate_images:
                    try:
                        from core.studio.images import generate_single_image
                        description = f"Professional document header for: {content_tree_model.doc_title}"
                        if content_tree_model.abstract:
                            description += f". {content_tree_model.abstract[:200]}"
                        buf = await generate_single_image(description)
                        if buf:
                            hero_image_bytes = buf.read()
                    except Exception as img_err:
                        logger.warning("Hero image generation failed, exporting without: %s", img_err)

                export_to_html(content_tree_model, output_path, hero_image=hero_image_bytes)
                validation = validate_html(output_path, content_tree_model)
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

    async def _run_sheet_export(
        self,
        artifact_id: str,
        export_job: Any,
        content_tree_dict: dict,
    ) -> None:
        """Execute sheet export (XLSX or CSV)."""
        from core.schemas.studio_schema import ExportFormat, ExportStatus, SheetContentTree
        from core.studio.sheets.exporter_xlsx import export_to_xlsx, sanitize_sheet_name
        from core.studio.sheets.exporter_csv import export_to_csv_zip
        from core.studio.sheets.validator import validate_xlsx, validate_csv_zip

        try:
            content_tree_model = SheetContentTree(**content_tree_dict)
            output_path = self.storage.get_export_file_path(
                artifact_id, export_job.id, export_job.format.value
            )

            if export_job.format == ExportFormat.xlsx:
                export_to_xlsx(content_tree_model, output_path)
                validation = validate_xlsx(
                    output_path,
                    expected_sheet_names=[sanitize_sheet_name(t.name) for t in content_tree_model.tabs],
                    expected_formula_cells=sum(
                        len(t.formulas) for t in content_tree_model.tabs
                    ),
                )
            elif export_job.format == ExportFormat.csv:
                output_path = self.storage.get_export_file_path(
                    artifact_id, export_job.id, "zip"
                )
                exported_tabs = export_to_csv_zip(content_tree_model, output_path)
                validation = validate_csv_zip(
                    output_path, expected_tab_names=exported_tabs
                )
                validation["exported_tabs"] = exported_tabs
            else:
                raise ValueError(
                    f"Unsupported sheet format: {export_job.format.value}"
                )

            if validation["valid"]:
                export_job.status = ExportStatus.completed
                export_job.output_uri = str(output_path)
                export_job.file_size_bytes = output_path.stat().st_size
                export_job.validator_results = validation
                export_job.completed_at = datetime.now(timezone.utc)
            else:
                export_job.status = ExportStatus.failed
                export_job.error = (
                    "; ".join(validation.get("errors", [])) or "Validation failed"
                )
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

    async def analyze_sheet_upload(
        self,
        artifact_id: str,
        filename: str,
        content_bytes: bytes,
        content_type: str,
    ) -> dict:
        """Ingest an uploaded file, analyze it, and update the sheet artifact."""
        from core.schemas.studio_schema import SheetContentTree
        from core.studio.sheets.ingest import ingest_upload
        from core.studio.sheets.analysis import analyze_dataset, build_analysis_tabs

        artifact = self.storage.load_artifact(artifact_id)
        if artifact is None:
            raise ValueError(f"Artifact not found: {artifact_id}")
        if artifact.type != ArtifactType.sheet:
            raise ValueError(f"Artifact {artifact_id} is not a sheet artifact")
        if artifact.content_tree is None:
            raise ValueError(
                f"Artifact {artifact_id} has no content tree (approve outline first)"
            )

        # Ingest and analyze
        dataset = ingest_upload(filename, content_bytes, content_type)
        report = analyze_dataset(dataset)
        analysis_tabs = build_analysis_tabs(dataset, report)

        # Update content tree
        content_tree_model = SheetContentTree(**artifact.content_tree)

        # Remove existing analysis tabs (replace on re-upload)
        analysis_tab_ids = {"uploaded_data", "summary_stats", "correlations", "anomalies", "pivot"}
        content_tree_model.tabs = [
            t for t in content_tree_model.tabs if t.id not in analysis_tab_ids
        ]
        content_tree_model.tabs.extend(analysis_tabs)
        content_tree_model.analysis_report = report

        content_tree = content_tree_model.model_dump(mode="json")

        # Create revision
        change_summary = f"Added upload analysis from {filename}"
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

    async def edit_artifact(
        self,
        artifact_id: str,
        instruction: str,
        base_revision_id: Optional[str] = None,
        mode: str = "apply",
        _patch_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Apply a chat-driven edit to an existing artifact.

        Args:
            artifact_id: Target artifact UUID
            instruction: User's edit instruction (e.g. "Change slide 3 title to ...")
            base_revision_id: Expected current revision id for optimistic concurrency
            mode: "apply" (default) or "dry_run" (preview without persisting)
            _patch_override: Test hook — bypass LLM and use this patch directly

        Returns:
            Dict with artifact data, revision info, diff, and any warnings

        Raises:
            ValueError: On invalid artifact, missing content tree, or patch failure
            ConflictError: When base_revision_id doesn't match current revision_head_id
        """
        from core.studio.editing.diff import compute_revision_diff, summarize_diff_highlights
        from core.studio.editing.patch_apply import apply_patch_to_content_tree

        # 0. Validate mode
        if mode not in ("apply", "dry_run"):
            raise ValueError(f"Invalid edit mode: {mode!r}. Must be 'apply' or 'dry_run'")

        # 1. Load artifact
        artifact = self.storage.load_artifact(artifact_id)
        if artifact is None:
            raise ValueError(f"Artifact not found: {artifact_id}")
        if artifact.content_tree is None:
            raise ValueError(f"Artifact {artifact_id} has no content tree (approve outline first)")

        # 2. Optimistic concurrency check
        if base_revision_id is not None and artifact.revision_head_id != base_revision_id:
            raise ConflictError(
                f"Conflict: expected revision {base_revision_id}, "
                f"but current is {artifact.revision_head_id}"
            )

        # 3. Plan patch
        if _patch_override is not None:
            patch_dict = _patch_override
        else:
            from core.studio.editing.planner import plan_patch
            patch_dict = await plan_patch(
                artifact_type=artifact.type.value,
                instruction=instruction,
                content_tree=artifact.content_tree,
                outline=artifact.outline.model_dump(mode="json") if artifact.outline else None,
            )

        # 4. Apply patch
        new_tree, warnings = apply_patch_to_content_tree(
            artifact.type.value, artifact.content_tree, patch_dict
        )

        # 5. Compute diff
        diff = compute_revision_diff(
            artifact.type.value, artifact.content_tree, new_tree
        )

        # 6. Dry run — return preview without persisting
        if mode == "dry_run":
            return {
                "artifact_id": artifact_id,
                "mode": "dry_run",
                "patch": patch_dict,
                "diff": diff,
                "warnings": warnings,
                "change_summary": summarize_diff_highlights(diff.get("highlights", [])),
            }

        # 7. No changes — return with warning, no revision
        if diff["stats"]["paths_changed"] == 0:
            return {
                **artifact.model_dump(mode="json"),
                "edit_result": {
                    "status": "no_changes",
                    "warnings": warnings + ["No changes detected from this edit"],
                },
            }

        # 8. Persist — create revision with diff/patch/edit_instruction
        change_summary = summarize_diff_highlights(diff.get("highlights", []))
        revision = self.revision_manager.create_revision(
            artifact_id=artifact_id,
            content_tree=new_tree,
            change_summary=change_summary,
            parent_revision_id=artifact.revision_head_id,
        )

        # Store edit metadata on the revision
        rev_loaded = self.storage.load_revision(artifact_id, revision.id)
        if rev_loaded:
            rev_loaded.edit_instruction = instruction
            rev_loaded.patch = patch_dict
            rev_loaded.diff = diff
            self.storage.save_revision(rev_loaded)

        # Update artifact
        artifact.content_tree = new_tree
        artifact.revision_head_id = revision.id
        artifact.updated_at = datetime.now(timezone.utc)
        self.storage.save_artifact(artifact)

        # Invalidate cached images and re-generate for slides edits
        if artifact.type == ArtifactType.slides:
            images_dir = self.storage.base_dir / artifact_id / "images"
            if images_dir.exists():
                import shutil
                shutil.rmtree(images_dir)
            version = self._image_gen_version[artifact_id] = self._image_gen_version.get(artifact_id, 0) + 1
            asyncio.create_task(self._generate_and_cache_images(artifact_id, new_tree, version))

        return {
            **artifact.model_dump(mode="json"),
            "edit_result": {
                "status": "applied",
                "revision_id": revision.id,
                "patch": patch_dict,
                "diff": diff,
                "warnings": warnings,
                "change_summary": change_summary,
            },
        }


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
