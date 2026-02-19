"""Tests for core/studio/revision.py — RevisionManager + compute_change_summary."""

import pytest
from datetime import datetime, timezone

from core.schemas.studio_schema import Artifact, ArtifactType
from core.studio.revision import RevisionManager, compute_change_summary
from core.studio.storage import StudioStorage


# === Fixtures ===

@pytest.fixture
def storage(tmp_path):
    return StudioStorage(base_dir=tmp_path / "studio")


@pytest.fixture
def revision_manager(storage):
    return RevisionManager(storage)


@pytest.fixture
def sample_artifact(storage):
    """Create and persist a sample artifact for revision tests."""
    now = datetime.now(timezone.utc)
    artifact = Artifact(
        id="art-rev-test",
        type=ArtifactType.slides,
        title="Test Deck",
        created_at=now,
        updated_at=now,
    )
    storage.save_artifact(artifact)
    return artifact


# === RevisionManager Tests ===

class TestRevisionManager:
    def test_create_revision(self, revision_manager, sample_artifact):
        content_tree = {"deck_title": "Test", "slides": []}
        revision = revision_manager.create_revision(
            artifact_id=sample_artifact.id,
            content_tree=content_tree,
            change_summary="Initial draft",
        )
        assert revision.artifact_id == sample_artifact.id
        assert revision.change_summary == "Initial draft"
        assert revision.content_tree_snapshot == content_tree
        assert revision.parent_revision_id is None

    def test_revision_has_generated_id(self, revision_manager, sample_artifact):
        revision = revision_manager.create_revision(
            artifact_id=sample_artifact.id,
            content_tree={"data": 1},
            change_summary="Test",
        )
        assert revision.id is not None
        assert len(revision.id) > 0
        # UUID format: 8-4-4-4-12
        assert len(revision.id.split("-")) == 5

    def test_revision_chain(self, revision_manager, sample_artifact):
        rev1 = revision_manager.create_revision(
            artifact_id=sample_artifact.id,
            content_tree={"v": 1},
            change_summary="First",
        )
        rev2 = revision_manager.create_revision(
            artifact_id=sample_artifact.id,
            content_tree={"v": 2},
            change_summary="Second",
            parent_revision_id=rev1.id,
        )
        assert rev2.parent_revision_id == rev1.id

    def test_get_revision(self, revision_manager, sample_artifact):
        revision = revision_manager.create_revision(
            artifact_id=sample_artifact.id,
            content_tree={"data": 1},
            change_summary="Test",
        )
        loaded = revision_manager.get_revision(sample_artifact.id, revision.id)
        assert loaded is not None
        assert loaded.id == revision.id
        assert loaded.change_summary == "Test"

    def test_get_nonexistent_revision(self, revision_manager, sample_artifact):
        result = revision_manager.get_revision(sample_artifact.id, "nonexistent")
        assert result is None

    def test_revision_history(self, revision_manager, sample_artifact):
        revision_manager.create_revision(
            artifact_id=sample_artifact.id,
            content_tree={"v": 1},
            change_summary="First",
        )
        revision_manager.create_revision(
            artifact_id=sample_artifact.id,
            content_tree={"v": 2},
            change_summary="Second",
        )
        history = revision_manager.get_revision_history(sample_artifact.id)
        assert len(history) == 2

    def test_revision_persisted(self, revision_manager, sample_artifact, storage):
        """Verify revision is actually on disk."""
        revision = revision_manager.create_revision(
            artifact_id=sample_artifact.id,
            content_tree={"test": True},
            change_summary="Persisted",
        )
        # Load directly from storage
        loaded = storage.load_revision(sample_artifact.id, revision.id)
        assert loaded is not None
        assert loaded.change_summary == "Persisted"


# === compute_change_summary Tests ===

class TestComputeChangeSummary:
    def test_initial_draft(self):
        result = compute_change_summary(None, {"deck_title": "Test", "slides": []})
        assert result == "Initial draft"

    def test_content_removed(self):
        result = compute_change_summary({"deck_title": "Test"}, None)
        assert result == "Content removed"

    def test_no_changes(self):
        tree = {"a": 1, "b": 2}
        result = compute_change_summary(tree, tree.copy())
        assert result == "No changes"

    def test_added_keys(self):
        old = {"a": 1}
        new = {"a": 1, "b": 2, "c": 3}
        result = compute_change_summary(old, new)
        assert "2 added" in result

    def test_removed_keys(self):
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 1}
        result = compute_change_summary(old, new)
        assert "2 removed" in result

    def test_changed_keys(self):
        old = {"a": 1, "b": "old"}
        new = {"a": 1, "b": "new"}
        result = compute_change_summary(old, new)
        assert "1 changed" in result

    def test_mixed_changes(self):
        old = {"a": 1, "b": 2, "c": 3}
        new = {"a": 99, "c": 3, "d": 4}
        result = compute_change_summary(old, new)
        assert "1 added" in result
        assert "1 removed" in result
        assert "1 changed" in result
