import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from core.schemas.studio_schema import Artifact, Revision


class StudioStorage:
    """File-based persistence for Forge artifacts and revisions.

    Directory layout:
        {base_dir}/{artifact_id}/artifact.json
        {base_dir}/{artifact_id}/revisions/{revision_id}.json
    """

    def __init__(self, base_dir: Path = None):
        """Initialize with configurable base_dir.

        Priority: explicit arg > FORGE_STUDIO_DIR env var > PROJECT_ROOT/studio default.
        """
        if base_dir is not None:
            self.base_dir = Path(base_dir)
        else:
            env_dir = os.environ.get("FORGE_STUDIO_DIR", "")
            if env_dir:
                self.base_dir = Path(env_dir)
            else:
                from shared.state import PROJECT_ROOT
                self.base_dir = PROJECT_ROOT / "studio"

    def save_artifact(self, artifact: Artifact) -> None:
        """Serialize artifact to {id}/artifact.json."""
        artifact_dir = self.base_dir / artifact.id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_file = artifact_dir / "artifact.json"
        artifact_file.write_text(json.dumps(artifact.model_dump(mode="json"), indent=2))

    def load_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """Load artifact from disk. Returns None if not found."""
        artifact_file = self.base_dir / artifact_id / "artifact.json"
        if not artifact_file.exists():
            return None
        data = json.loads(artifact_file.read_text())
        return Artifact(**data)

    def list_artifacts(self) -> List[Dict]:
        """List all artifacts sorted by updated_at descending."""
        if not self.base_dir.exists():
            return []

        artifacts = []
        for entry in self.base_dir.iterdir():
            if entry.is_dir():
                artifact_file = entry / "artifact.json"
                if artifact_file.exists():
                    try:
                        data = json.loads(artifact_file.read_text())
                        artifacts.append({
                            "id": data.get("id", entry.name),
                            "type": data.get("type"),
                            "title": data.get("title", "Untitled"),
                            "updated_at": data.get("updated_at"),
                        })
                    except (json.JSONDecodeError, KeyError):
                        continue

        return sorted(artifacts, key=lambda x: x.get("updated_at", ""), reverse=True)

    def delete_artifact(self, artifact_id: str) -> None:
        """Delete an artifact directory."""
        artifact_dir = self.base_dir / artifact_id
        if artifact_dir.exists():
            shutil.rmtree(artifact_dir)

    def save_revision(self, revision: Revision) -> None:
        """Save a revision to {artifact_id}/revisions/{revision_id}.json."""
        revisions_dir = self.base_dir / revision.artifact_id / "revisions"
        revisions_dir.mkdir(parents=True, exist_ok=True)
        revision_file = revisions_dir / f"{revision.id}.json"
        revision_file.write_text(json.dumps(revision.model_dump(mode="json"), indent=2))

    def load_revision(self, artifact_id: str, revision_id: str) -> Optional[Revision]:
        """Load a specific revision. Returns None if not found."""
        revision_file = self.base_dir / artifact_id / "revisions" / f"{revision_id}.json"
        if not revision_file.exists():
            return None
        data = json.loads(revision_file.read_text())
        return Revision(**data)

    def list_revisions(self, artifact_id: str) -> List[Dict]:
        """List all revisions for an artifact sorted by created_at descending."""
        revisions_dir = self.base_dir / artifact_id / "revisions"
        if not revisions_dir.exists():
            return []

        revisions = []
        for rev_file in revisions_dir.glob("*.json"):
            try:
                data = json.loads(rev_file.read_text())
                revisions.append({
                    "id": data.get("id", rev_file.stem),
                    "change_summary": data.get("change_summary", ""),
                    "created_at": data.get("created_at"),
                    "parent_revision_id": data.get("parent_revision_id"),
                })
            except (json.JSONDecodeError, KeyError):
                continue

        return sorted(revisions, key=lambda x: x.get("created_at", ""), reverse=True)
