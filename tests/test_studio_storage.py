"""Tests for core/studio/storage.py — file-based persistence."""

import pytest
import time
from datetime import datetime, timezone, timedelta

from core.schemas.studio_schema import (
    Artifact,
    ArtifactType,
    Outline,
    OutlineItem,
    OutlineStatus,
    Revision,
)
from core.studio.storage import StudioStorage


# === Fixtures ===

@pytest.fixture
def storage(tmp_path):
    return StudioStorage(base_dir=tmp_path / "studio")


@pytest.fixture
def sample_artifact():
    now = datetime.now(timezone.utc)
    return Artifact(
        id="art-test-001",
        type=ArtifactType.slides,
        title="Test Deck",
        created_at=now,
        updated_at=now,
        outline=Outline(
            artifact_type=ArtifactType.slides,
            title="Test Deck",
            items=[OutlineItem(id="1", title="Intro", description="Opening")],
            status=OutlineStatus.pending,
        ),
    )


@pytest.fixture
def sample_revision():
    return Revision(
        id="rev-test-001",
        artifact_id="art-test-001",
        parent_revision_id=None,
        change_summary="Initial draft",
        content_tree_snapshot={"deck_title": "Test", "slides": []},
        created_at=datetime.now(timezone.utc),
    )


# === Artifact Tests ===

class TestArtifactStorage:
    def test_save_load_artifact(self, storage, sample_artifact):
        storage.save_artifact(sample_artifact)
        loaded = storage.load_artifact(sample_artifact.id)
        assert loaded is not None
        assert loaded.id == sample_artifact.id
        assert loaded.title == sample_artifact.title
        assert loaded.type == sample_artifact.type

    def test_load_nonexistent_returns_none(self, storage):
        result = storage.load_artifact("nonexistent-id")
        assert result is None

    def test_list_artifacts_empty(self, storage):
        result = storage.list_artifacts()
        assert result == []

    def test_list_artifacts_sorted(self, storage):
        now = datetime.now(timezone.utc)
        older = Artifact(
            id="art-older",
            type=ArtifactType.document,
            title="Older Doc",
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        )
        newer = Artifact(
            id="art-newer",
            type=ArtifactType.slides,
            title="Newer Slides",
            created_at=now,
            updated_at=now,
        )
        storage.save_artifact(older)
        storage.save_artifact(newer)

        result = storage.list_artifacts()
        assert len(result) == 2
        assert result[0]["id"] == "art-newer"
        assert result[1]["id"] == "art-older"

    def test_delete_artifact(self, storage, sample_artifact):
        storage.save_artifact(sample_artifact)
        assert storage.load_artifact(sample_artifact.id) is not None

        storage.delete_artifact(sample_artifact.id)
        assert storage.load_artifact(sample_artifact.id) is None

    def test_delete_nonexistent_no_error(self, storage):
        storage.delete_artifact("does-not-exist")  # should not raise

    def test_artifact_dir_created(self, storage, sample_artifact):
        storage.save_artifact(sample_artifact)
        artifact_dir = storage.base_dir / sample_artifact.id
        assert artifact_dir.exists()
        assert (artifact_dir / "artifact.json").exists()

    def test_overwrite_artifact(self, storage, sample_artifact):
        storage.save_artifact(sample_artifact)
        sample_artifact.title = "Updated Title"
        storage.save_artifact(sample_artifact)
        loaded = storage.load_artifact(sample_artifact.id)
        assert loaded.title == "Updated Title"


# === Revision Tests ===

class TestRevisionStorage:
    def test_save_load_revision(self, storage, sample_revision):
        # Create artifact dir first
        (storage.base_dir / sample_revision.artifact_id).mkdir(parents=True, exist_ok=True)

        storage.save_revision(sample_revision)
        loaded = storage.load_revision(sample_revision.artifact_id, sample_revision.id)
        assert loaded is not None
        assert loaded.id == sample_revision.id
        assert loaded.change_summary == "Initial draft"

    def test_load_nonexistent_revision(self, storage):
        result = storage.load_revision("art-test-001", "nonexistent-rev")
        assert result is None

    def test_list_revisions(self, storage):
        artifact_id = "art-test-001"
        now = datetime.now(timezone.utc)

        rev1 = Revision(
            id="rev-1",
            artifact_id=artifact_id,
            change_summary="First",
            content_tree_snapshot={"v": 1},
            created_at=now - timedelta(hours=1),
        )
        rev2 = Revision(
            id="rev-2",
            artifact_id=artifact_id,
            parent_revision_id="rev-1",
            change_summary="Second",
            content_tree_snapshot={"v": 2},
            created_at=now,
        )
        storage.save_revision(rev1)
        storage.save_revision(rev2)

        revisions = storage.list_revisions(artifact_id)
        assert len(revisions) == 2
        assert revisions[0]["id"] == "rev-2"  # newer first
        assert revisions[1]["id"] == "rev-1"

    def test_list_revisions_empty(self, storage):
        result = storage.list_revisions("no-such-artifact")
        assert result == []
