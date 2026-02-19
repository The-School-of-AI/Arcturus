"""Tests for core/studio/orchestrator.py — pipeline tests with mocked LLM."""

import asyncio
import json
import pytest
from datetime import datetime, timezone

from core.json_parser import JsonParsingError
from core.schemas.studio_schema import (
    Artifact,
    ArtifactType,
    Outline,
    OutlineItem,
    OutlineStatus,
)
from core.studio.orchestrator import ForgeOrchestrator
from core.studio.storage import StudioStorage


def _run(coro):
    """Helper to run async coroutines in sync tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# === Fixtures ===

@pytest.fixture
def storage(tmp_path):
    return StudioStorage(base_dir=tmp_path / "studio")


@pytest.fixture
def orchestrator(storage):
    return ForgeOrchestrator(storage)


# Canned LLM responses
OUTLINE_RESPONSE = json.dumps({
    "title": "AI Startup Pitch Deck",
    "items": [
        {"id": "1", "title": "Title Slide", "description": "Company intro", "children": []},
        {"id": "2", "title": "Problem", "description": "The pain point", "children": []},
        {"id": "3", "title": "Solution", "description": "Our product", "children": [
            {"id": "3.1", "title": "Demo", "description": "Product demo", "children": []}
        ]},
    ]
})

SLIDES_DRAFT_RESPONSE = json.dumps({
    "deck_title": "AI Startup Pitch Deck",
    "subtitle": "Transforming the Future",
    "slides": [
        {
            "id": "s1",
            "slide_type": "title",
            "title": "Title Slide",
            "elements": [
                {"id": "e1", "type": "title", "content": "AI Startup"},
                {"id": "e2", "type": "subtitle", "content": "Series A Pitch"},
            ],
            "speaker_notes": "Welcome everyone.",
        },
        {
            "id": "s2",
            "slide_type": "content",
            "title": "Problem",
            "elements": [
                {"id": "e3", "type": "body", "content": "Enterprises waste time."},
            ],
        },
    ],
    "metadata": {"audience": "investors"},
})

DOCUMENT_DRAFT_RESPONSE = json.dumps({
    "doc_title": "Test Report",
    "doc_type": "report",
    "abstract": "Summary here.",
    "sections": [
        {
            "id": "sec1",
            "heading": "Introduction",
            "level": 1,
            "content": "Intro content.",
            "subsections": [],
            "citations": [],
        }
    ],
    "bibliography": [],
})

SHEET_DRAFT_RESPONSE = json.dumps({
    "workbook_title": "Financial Model",
    "tabs": [
        {
            "id": "tab1",
            "name": "Revenue",
            "headers": ["Month", "MRR"],
            "rows": [["Jan", 5000]],
            "formulas": {},
            "column_widths": [120, 100],
        }
    ],
})


@pytest.fixture
def mock_llm_slides(monkeypatch):
    """Mock LLM that returns outline or slides draft based on prompt content."""
    async def fake_generate(self, prompt):
        # "content architect" only appears in outline prompt, not draft prompt
        if "content architect" in prompt.lower():
            return OUTLINE_RESPONSE
        return SLIDES_DRAFT_RESPONSE
    monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)


@pytest.fixture
def mock_llm_document(monkeypatch):
    """Mock LLM for document drafts."""
    async def fake_generate(self, prompt):
        if "content architect" in prompt.lower():
            return OUTLINE_RESPONSE
        return DOCUMENT_DRAFT_RESPONSE
    monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)


@pytest.fixture
def mock_llm_sheet(monkeypatch):
    """Mock LLM for sheet drafts."""
    async def fake_generate(self, prompt):
        if "content architect" in prompt.lower():
            return OUTLINE_RESPONSE
        return SHEET_DRAFT_RESPONSE
    monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)


@pytest.fixture
def mock_llm_malformed(monkeypatch):
    """Mock LLM that returns unparseable text."""
    async def fake_generate(self, prompt):
        return "This is not JSON at all, just some random text without any braces."
    monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)


@pytest.fixture
def mock_llm_invalid_content_tree(monkeypatch):
    """Mock LLM that returns valid JSON but invalid content tree."""
    async def fake_generate(self, prompt):
        if "content architect" in prompt.lower():
            return OUTLINE_RESPONSE
        # Valid JSON but doesn't match SlidesContentTree schema
        return json.dumps({"wrong_field": "bad data", "no_slides": True})
    monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)


# === Outline Generation Tests ===

class TestGenerateOutline:
    def test_creates_artifact(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline(
            prompt="Create a pitch deck for an AI startup",
            artifact_type=ArtifactType.slides,
        ))
        assert "artifact_id" in result
        assert result["status"] == "pending"
        assert result["outline"]["title"] == "AI Startup Pitch Deck"
        assert len(result["outline"]["items"]) == 3

    def test_persisted(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
        ))
        loaded = storage.load_artifact(result["artifact_id"])
        assert loaded is not None
        assert loaded.outline is not None
        assert loaded.outline.status == OutlineStatus.pending
        assert loaded.content_tree is None

    def test_with_parameters(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
            parameters={"slide_count": 5, "tone": "casual"},
        ))
        loaded = storage.load_artifact(result["artifact_id"])
        assert loaded.outline.parameters == {"slide_count": 5, "tone": "casual"}

    def test_with_title_override(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
            title="Founder Update Q1",
        ))
        loaded = storage.load_artifact(result["artifact_id"])
        assert result["outline"]["title"] == "Founder Update Q1"
        assert loaded.title == "Founder Update Q1"
        assert loaded.outline.title == "Founder Update Q1"

    def test_malformed_json_raises(self, orchestrator, mock_llm_malformed):
        with pytest.raises(JsonParsingError):
            _run(orchestrator.generate_outline(
                prompt="Create slides",
                artifact_type=ArtifactType.slides,
            ))


# === Approve and Draft Tests ===

class TestApproveAndGenerateDraft:
    def test_generates_draft(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
        ))
        artifact_id = result["artifact_id"]

        artifact_data = _run(orchestrator.approve_and_generate_draft(artifact_id))
        assert artifact_data["content_tree"] is not None
        assert artifact_data["content_tree"]["deck_title"] == "AI Startup Pitch Deck"
        assert artifact_data["revision_head_id"] is not None
        assert artifact_data["outline"]["status"] == "approved"

    def test_creates_revision(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        revisions = storage.list_revisions(result["artifact_id"])
        assert len(revisions) == 1
        assert revisions[0]["change_summary"] == "Initial draft"

    def test_nonexistent_raises(self, orchestrator, mock_llm_slides):
        with pytest.raises(ValueError, match="not found"):
            _run(orchestrator.approve_and_generate_draft("nonexistent-id"))

    def test_no_outline_raises(self, orchestrator, storage, mock_llm_slides):
        now = datetime.now(timezone.utc)
        artifact = Artifact(
            id="no-outline",
            type=ArtifactType.slides,
            title="Empty",
            created_at=now,
            updated_at=now,
        )
        storage.save_artifact(artifact)

        with pytest.raises(ValueError, match="no outline"):
            _run(orchestrator.approve_and_generate_draft("no-outline"))

    def test_invalid_content_tree_raises(self, orchestrator, storage, mock_llm_invalid_content_tree):
        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
        ))
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

    def test_approve_already_approved(self, orchestrator, storage, mock_llm_slides):
        """Approving again is idempotent — re-generates draft with new revision."""
        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
        ))
        artifact_id = result["artifact_id"]

        _run(orchestrator.approve_and_generate_draft(artifact_id))
        artifact_data = _run(orchestrator.approve_and_generate_draft(artifact_id))

        assert artifact_data["content_tree"] is not None
        revisions = storage.list_revisions(artifact_id)
        assert len(revisions) == 2
        assert revisions[0]["change_summary"] == "No changes"
        assert revisions[1]["change_summary"] == "Initial draft"

    def test_title_modification_updates_artifact_title(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
        ))
        artifact_data = _run(orchestrator.approve_and_generate_draft(
            result["artifact_id"],
            modifications={"title": "Board Review Deck"},
        ))

        assert artifact_data["title"] == "Board Review Deck"
        assert artifact_data["outline"]["title"] == "Board Review Deck"

    def test_document_draft(self, orchestrator, storage, mock_llm_document):
        result = _run(orchestrator.generate_outline(
            prompt="Write a technical report",
            artifact_type=ArtifactType.document,
        ))
        artifact_data = _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))
        assert artifact_data["content_tree"]["doc_title"] == "Test Report"

    def test_sheet_draft(self, orchestrator, storage, mock_llm_sheet):
        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        artifact_data = _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))
        assert artifact_data["content_tree"]["workbook_title"] == "Financial Model"


class TestRejectOutline:
    def test_reject_marks_outline_rejected(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
        ))

        artifact_data = orchestrator.reject_outline(result["artifact_id"])
        assert artifact_data["outline"]["status"] == "rejected"
        assert artifact_data["content_tree"] is None
        assert artifact_data["revision_head_id"] is None

    def test_reject_applies_title_modification(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
        ))

        artifact_data = orchestrator.reject_outline(
            result["artifact_id"],
            modifications={"title": "Needs Rework"},
        )
        assert artifact_data["title"] == "Needs Rework"
        assert artifact_data["outline"]["title"] == "Needs Rework"
