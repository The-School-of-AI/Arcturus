import json
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from core.schemas.studio_schema import Artifact, ExportJob, Revision

_SAFE_ID = re.compile(r"^[\w-]+$")


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
                        outline_data = data.get("outline")
                        outline_status = None
                        if isinstance(outline_data, dict):
                            outline_status = outline_data.get("status")
                        artifacts.append({
                            "id": data.get("id", entry.name),
                            "type": data.get("type"),
                            "title": data.get("title", "Untitled"),
                            "updated_at": data.get("updated_at"),
                            "outline": {"status": outline_status} if outline_status else None,
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

    # === Export Job Methods ===

    def save_export_job(self, export_job: ExportJob) -> None:
        """Save an export job to {artifact_id}/exports/{job_id}.json."""
        exports_dir = self.base_dir / export_job.artifact_id / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        job_file = exports_dir / f"{export_job.id}.json"
        job_file.write_text(json.dumps(export_job.model_dump(mode="json"), indent=2))

    def load_export_job(self, artifact_id: str, export_job_id: str) -> Optional[ExportJob]:
        """Load a specific export job. Returns None if not found."""
        job_file = self.base_dir / artifact_id / "exports" / f"{export_job_id}.json"
        if not job_file.exists():
            return None
        data = json.loads(job_file.read_text())
        return ExportJob(**data)

    def list_export_jobs(self, artifact_id: str) -> List[Dict]:
        """List all export jobs for an artifact sorted by created_at desc."""
        exports_dir = self.base_dir / artifact_id / "exports"
        if not exports_dir.exists():
            return []
        jobs = []
        for job_file in exports_dir.glob("*.json"):
            try:
                data = json.loads(job_file.read_text())
                jobs.append({
                    "id": data.get("id", job_file.stem),
                    "format": data.get("format"),
                    "status": data.get("status"),
                    "created_at": data.get("created_at"),
                    "completed_at": data.get("completed_at"),
                    "file_size_bytes": data.get("file_size_bytes"),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sorted(jobs, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_export_file_path(self, artifact_id: str, export_job_id: str, fmt: str) -> Path:
        """Return the file path for an exported artifact."""
        return self.base_dir / artifact_id / "exports" / f"{export_job_id}.{fmt}"

    # === Slide Image Cache Methods ===

    def save_slide_image(self, artifact_id: str, slide_id: str, jpeg_bytes: bytes) -> Path:
        """Save a generated slide image to {artifact_id}/images/{slide_id}.jpg."""
        if not _SAFE_ID.match(slide_id):
            raise ValueError(f"Invalid slide_id: {slide_id!r}")
        images_dir = self.base_dir / artifact_id / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        image_path = images_dir / f"{slide_id}.jpg"
        image_path.write_bytes(jpeg_bytes)
        return image_path

    def load_slide_image_path(self, artifact_id: str, slide_id: str) -> Optional[Path]:
        """Return the path to a cached slide image, or None if not found."""
        if not _SAFE_ID.match(slide_id):
            return None
        image_path = self.base_dir / artifact_id / "images" / f"{slide_id}.jpg"
        return image_path if image_path.exists() else None

    def list_slide_images(self, artifact_id: str) -> List[str]:
        """Return slide IDs that have cached images."""
        images_dir = self.base_dir / artifact_id / "images"
        if not images_dir.exists():
            return []
        return [p.stem for p in images_dir.glob("*.jpg")]

    def find_export_job(self, export_job_id: str) -> Optional[tuple]:
        """Scan all artifact directories for an export job by ID.

        Returns (artifact_id, ExportJob) or None if not found.
        """
        if not self.base_dir.exists():
            return None
        for artifact_dir in self.base_dir.iterdir():
            if not artifact_dir.is_dir():
                continue
            job_file = artifact_dir / "exports" / f"{export_job_id}.json"
            if job_file.exists():
                try:
                    data = json.loads(job_file.read_text())
                    return (artifact_dir.name, ExportJob(**data))
                except (json.JSONDecodeError, Exception):
                    continue
        return None
