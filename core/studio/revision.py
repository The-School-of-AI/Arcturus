from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from core.schemas.studio_schema import Revision
from core.studio.storage import StudioStorage


class RevisionManager:
    """Manages creation and retrieval of artifact revisions."""

    def __init__(self, storage: StudioStorage):
        self.storage = storage

    def create_revision(
        self,
        artifact_id: str,
        content_tree: dict,
        change_summary: str,
        parent_revision_id: Optional[str] = None,
    ) -> Revision:
        """Create a new revision and persist it."""
        revision = Revision(
            id=str(uuid4()),
            artifact_id=artifact_id,
            parent_revision_id=parent_revision_id,
            change_summary=change_summary,
            content_tree_snapshot=content_tree,
            created_at=datetime.now(timezone.utc),
        )
        self.storage.save_revision(revision)
        return revision

    def get_revision(self, artifact_id: str, revision_id: str) -> Optional[Revision]:
        """Retrieve a specific revision."""
        return self.storage.load_revision(artifact_id, revision_id)

    def get_revision_history(self, artifact_id: str) -> List[Dict]:
        """Get all revisions for an artifact in reverse chronological order."""
        return self.storage.list_revisions(artifact_id)


def compute_change_summary(old_tree: dict | None, new_tree: dict | None) -> str:
    """Compute a human-readable summary of changes between two content trees.

    Compares top-level keys and reports added, removed, and changed counts.
    Returns a descriptive string suitable for Revision.change_summary.
    """
    if old_tree is None:
        return "Initial draft"
    if new_tree is None:
        return "Content removed"

    old_keys = set(old_tree.keys())
    new_keys = set(new_tree.keys())

    added = new_keys - old_keys
    removed = old_keys - new_keys
    changed = [k for k in old_keys & new_keys if old_tree[k] != new_tree[k]]

    parts = []
    if added:
        parts.append(f"{len(added)} added")
    if removed:
        parts.append(f"{len(removed)} removed")
    if changed:
        parts.append(f"{len(changed)} changed")

    return ", ".join(parts) if parts else "No changes"
