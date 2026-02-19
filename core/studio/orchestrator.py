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
from core.studio.prompts import get_draft_prompt, get_outline_prompt
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

        outline = Outline(
            artifact_type=artifact_type,
            title=parsed["title"],
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
            if "title" in modifications:
                artifact.outline.title = modifications["title"]
            if "items" in modifications:
                artifact.outline.items = [
                    _parse_outline_item(item) for item in modifications["items"]
                ]

        # Mark outline as approved
        artifact.outline.status = OutlineStatus.approved

        # Generate draft via LLM
        llm_prompt = get_draft_prompt(artifact.type, artifact.outline)
        mm = ModelManager()
        raw = await mm.generate_text(llm_prompt)

        # Parse and validate content tree
        parsed = parse_llm_json(raw)
        content_tree_model = validate_content_tree(artifact.type, parsed)
        content_tree = content_tree_model.model_dump(mode="json")

        # Create revision
        change_summary = compute_change_summary(None, content_tree)
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


def _parse_outline_item(data: dict) -> OutlineItem:
    """Recursively parse an outline item dict into an OutlineItem model."""
    children = [_parse_outline_item(child) for child in data.get("children", [])]
    return OutlineItem(
        id=str(data.get("id", "")),
        title=data.get("title", ""),
        description=data.get("description"),
        children=children,
    )
