"""Tests for core/studio/orchestrator.py — pipeline tests with mocked LLM."""

import asyncio
import json
import pytest
from datetime import datetime, timezone

from core.json_parser import JsonParsingError
from core.schemas.studio_schema import (
    Artifact,
    ArtifactType,
    ExportFormat,
    Outline,
    OutlineItem,
    OutlineStatus,
)
from core.studio.orchestrator import ForgeOrchestrator
from core.studio.storage import StudioStorage


def _xhtml2pdf_available():
    try:
        from xhtml2pdf import pisa
        return True
    except (ImportError, OSError):
        return False


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
            "speaker_notes": "Explain the core problem.",
        },
        {
            "id": "s3",
            "slide_type": "content",
            "title": "Solution",
            "elements": [
                {"id": "e4", "type": "body", "content": "Our AI platform automates workflows."},
            ],
            "speaker_notes": "Present the solution.",
        },
        {
            "id": "s4",
            "slide_type": "two_column",
            "title": "Before vs After",
            "elements": [
                {"id": "e5", "type": "body", "content": "Manual processes."},
                {"id": "e6", "type": "body", "content": "Automated workflows."},
            ],
            "speaker_notes": "Compare old vs new.",
        },
        {
            "id": "s5",
            "slide_type": "timeline",
            "title": "Roadmap",
            "elements": [
                {"id": "e7", "type": "bullet_list", "content": ["Q1: Launch", "Q2: Scale", "Q3: Expand"]},
            ],
            "speaker_notes": "Walk through the timeline.",
        },
        {
            "id": "s6",
            "slide_type": "chart",
            "title": "Traction",
            "elements": [
                {"id": "e8", "type": "chart", "content": "Revenue growth chart"},
                {"id": "e9", "type": "body", "content": "3x growth in 12 months."},
            ],
            "speaker_notes": "Highlight growth metrics.",
        },
        {
            "id": "s7",
            "slide_type": "quote",
            "title": "Testimonial",
            "elements": [
                {"id": "e10", "type": "quote", "content": "This product changed everything."},
                {"id": "e11", "type": "body", "content": "Jane Doe, CTO"},
            ],
            "speaker_notes": "Share customer voice.",
        },
        {
            "id": "s8",
            "slide_type": "content",
            "title": "Business Model",
            "elements": [
                {"id": "e12", "type": "body", "content": "SaaS with enterprise pricing."},
            ],
            "speaker_notes": "Explain monetization.",
        },
        {
            "id": "s9",
            "slide_type": "team",
            "title": "Team",
            "elements": [
                {"id": "e13", "type": "bullet_list", "content": ["CEO: Alice", "CTO: Bob", "VP Eng: Carol"]},
            ],
            "speaker_notes": "Introduce the team.",
        },
        {
            "id": "s10",
            "slide_type": "title",
            "title": "Thank You",
            "elements": [
                {"id": "e14", "type": "title", "content": "Thank You"},
                {"id": "e15", "type": "subtitle", "content": "Questions?"},
            ],
            "speaker_notes": "Close and take questions.",
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


@pytest.fixture(autouse=True)
def _patch_model_manager_init(monkeypatch):
    """Prevent ModelManager.__init__ from calling real API clients."""
    def noop_init(self, model_name=None, provider=None, role=None):
        self.model_type = "gemini"
        self.client = None
    monkeypatch.setattr("core.model_manager.ModelManager.__init__", noop_init)


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


@pytest.fixture
def mock_llm_outline_null_children(monkeypatch):
    """Mock LLM that returns an outline with children set to null."""
    async def fake_generate(self, prompt):
        return json.dumps({
            "title": "Null Children Outline",
            "items": [
                {"id": "1", "title": "Intro", "description": "desc", "children": None}
            ],
        })
    monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)


@pytest.fixture
def mock_llm_outline_bad_children_type(monkeypatch):
    """Mock LLM that returns an outline with invalid children type."""
    async def fake_generate(self, prompt):
        return json.dumps({
            "title": "Bad Children Outline",
            "items": [
                {"id": "1", "title": "Intro", "description": "desc", "children": "invalid"}
            ],
        })
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
        assert loaded.creation_prompt == "Create slides"

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

    def test_null_children_is_supported(self, orchestrator, storage, mock_llm_outline_null_children):
        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
        ))
        loaded = storage.load_artifact(result["artifact_id"])
        assert loaded is not None
        assert loaded.outline is not None
        assert loaded.outline.items[0].children == []

    def test_bad_children_type_raises(self, orchestrator, mock_llm_outline_bad_children_type):
        with pytest.raises(ValueError, match="children"):
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

    def test_sheet_visual_repair_second_pass_triggered(self, orchestrator, monkeypatch):
        calls = {"total": 0, "repair": 0}
        chartable_draft = json.dumps(
            {
                "workbook_title": "Financial Model",
                "tabs": [
                    {
                        "id": "tab1",
                        "name": "Revenue",
                        "headers": ["Month", "MRR"],
                        "rows": [["Jan", 5000], ["Feb", 5500], ["Mar", 6200]],
                        "formulas": {},
                        "column_widths": [120, 100],
                    }
                ],
            }
        )

        async def fake_generate(self, prompt):
            calls["total"] += 1
            p = prompt.lower()
            if "content architect" in p:
                return OUTLINE_RESPONSE
            if "spreadsheet visual designer" in p:
                calls["repair"] += 1
                return json.dumps(
                    {
                        "metadata": {
                            "visual_profile": "balanced",
                            "palette_hint": "oceanic-blue",
                            "chart_plan": [
                                {
                                    "tab_name": "Revenue",
                                    "chart_type": "line",
                                    "category_column": "Month",
                                    "value_columns": ["MRR"],
                                }
                            ],
                        }
                    }
                )
            return chartable_draft

        monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)

        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        artifact_data = _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))
        md = artifact_data["content_tree"].get("metadata", {})

        assert calls["repair"] == 1
        assert calls["total"] == 3
        assert md.get("visual_profile") == "balanced"
        assert isinstance(md.get("chart_plan"), list)
        assert len(md["chart_plan"]) >= 1

    def test_sheet_visual_repair_skipped_when_metadata_already_valid(self, orchestrator, monkeypatch):
        calls = {"total": 0, "repair": 0}
        draft_with_visual_metadata = json.dumps(
            {
                "workbook_title": "Financial Model",
                "tabs": [
                    {
                        "id": "tab1",
                        "name": "Revenue",
                        "headers": ["Month", "MRR"],
                        "rows": [["Jan", 5000], ["Feb", 5500], ["Mar", 6200]],
                        "formulas": {},
                        "column_widths": [120, 100],
                    }
                ],
                "metadata": {
                    "visual_profile": "balanced",
                    "palette_hint": "oceanic-blue",
                    "chart_plan": [
                        {
                            "tab_name": "Revenue",
                            "chart_type": "line",
                            "category_column": "Month",
                            "value_columns": ["MRR"],
                        }
                    ],
                },
            }
        )

        async def fake_generate(self, prompt):
            calls["total"] += 1
            p = prompt.lower()
            if "content architect" in p:
                return OUTLINE_RESPONSE
            if "spreadsheet visual designer" in p:
                calls["repair"] += 1
                return json.dumps({"metadata": {"visual_profile": "balanced"}})
            return draft_with_visual_metadata

        monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)

        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        assert calls["repair"] == 0
        assert calls["total"] == 2

    def test_sheet_visual_repair_parse_failure_is_non_blocking(self, orchestrator, monkeypatch):
        calls = {"repair": 0}
        chartable_draft = json.dumps(
            {
                "workbook_title": "Financial Model",
                "tabs": [
                    {
                        "id": "tab1",
                        "name": "Revenue",
                        "headers": ["Month", "MRR"],
                        "rows": [["Jan", 5000], ["Feb", 5500], ["Mar", 6200]],
                        "formulas": {},
                        "column_widths": [120, 100],
                    }
                ],
            }
        )

        async def fake_generate(self, prompt):
            p = prompt.lower()
            if "content architect" in p:
                return OUTLINE_RESPONSE
            if "spreadsheet visual designer" in p:
                calls["repair"] += 1
                return "this is not valid json"
            return chartable_draft

        monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)

        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        artifact_data = _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))
        metadata = artifact_data["content_tree"].get("metadata", {})

        assert calls["repair"] == 1
        assert artifact_data["content_tree"]["workbook_title"] == "Financial Model"
        assert metadata.get("visual_profile") == "balanced"

    def test_reuses_selected_model_for_draft(self, orchestrator, monkeypatch):
        init_models = []

        def capture_init(self, model_name=None, provider=None, role=None):
            init_models.append(model_name)
            self.model_type = "gemini"
            self.client = None

        async def fake_generate(self, prompt):
            if "content architect" in prompt.lower():
                return OUTLINE_RESPONSE
            return SLIDES_DRAFT_RESPONSE

        monkeypatch.setattr("core.model_manager.ModelManager.__init__", capture_init)
        monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)

        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
            model="gpt-4o-mini",
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        assert init_models == ["gpt-4o-mini", "gpt-4o-mini"]

    def test_invalid_items_modification_raises(self, orchestrator, mock_llm_slides):
        result = _run(orchestrator.generate_outline(
            prompt="Create slides",
            artifact_type=ArtifactType.slides,
        ))

        with pytest.raises(ValueError, match="items.*list"):
            _run(orchestrator.approve_and_generate_draft(
                result["artifact_id"],
                modifications={"items": None},
            ))


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


# === Phase 4: Document Normalization and Export Tests ===

class TestDocumentOutlineNormalization:
    def test_document_outline_resolves_doc_type(self, orchestrator, storage, mock_llm_document):
        result = _run(orchestrator.generate_outline(
            prompt="Create a technical specification",
            artifact_type=ArtifactType.document,
        ))
        loaded = storage.load_artifact(result["artifact_id"])
        assert loaded.outline.parameters.get("doc_type") == "technical_spec"

    def test_document_outline_inserts_required_sections(self, orchestrator, storage, mock_llm_document):
        result = _run(orchestrator.generate_outline(
            prompt="Write a report",
            artifact_type=ArtifactType.document,
        ))
        loaded = storage.load_artifact(result["artifact_id"])
        titles = {item.title for item in loaded.outline.items}
        # Report requires: Executive Summary, Introduction, Findings, Conclusion
        assert "Executive Summary" in titles or "Findings" in titles or "Conclusion" in titles


class TestDocumentDraftNormalization:
    def test_document_draft_normalized(self, orchestrator, storage, mock_llm_document):
        result = _run(orchestrator.generate_outline(
            prompt="Write a report",
            artifact_type=ArtifactType.document,
        ))
        artifact_data = _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))
        ct = artifact_data["content_tree"]
        assert ct["doc_type"] in ("report", "technical_spec", "proposal")
        # Provenance slots should be present in metadata
        assert "provenance_slots" in ct.get("metadata", {})

    def test_document_draft_has_normalized_section_ids(self, orchestrator, storage, mock_llm_document):
        result = _run(orchestrator.generate_outline(
            prompt="Write a report",
            artifact_type=ArtifactType.document,
        ))
        artifact_data = _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))
        ct = artifact_data["content_tree"]
        assert ct["sections"][0]["id"] == "sec1"


class TestDocumentExportLifecycle:
    def test_export_docx_creates_job(self, orchestrator, storage, mock_llm_document):
        result = _run(orchestrator.generate_outline(
            prompt="Write a report",
            artifact_type=ArtifactType.document,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        job_data = _run(orchestrator.export_artifact(
            result["artifact_id"],
            export_format=ExportFormat.docx,
        ))
        assert job_data["format"] == "docx"
        assert job_data["status"] == "completed"
        assert job_data["output_uri"] is not None

    @pytest.mark.skipif(
        not _xhtml2pdf_available(),
        reason="xhtml2pdf not available",
    )
    def test_export_pdf_creates_job(self, orchestrator, storage, mock_llm_document):
        result = _run(orchestrator.generate_outline(
            prompt="Write a report",
            artifact_type=ArtifactType.document,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        job_data = _run(orchestrator.export_artifact(
            result["artifact_id"],
            export_format=ExportFormat.pdf,
        ))
        assert job_data["format"] == "pdf"
        assert job_data["status"] == "completed"

    def test_export_pptx_for_document_raises(self, orchestrator, storage, mock_llm_document):
        result = _run(orchestrator.generate_outline(
            prompt="Write a report",
            artifact_type=ArtifactType.document,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        with pytest.raises(ValueError, match="not supported"):
            _run(orchestrator.export_artifact(
                result["artifact_id"],
                export_format=ExportFormat.pptx,
            ))


class TestDocumentExportParamGating:
    def test_theme_id_rejected_for_document(self, orchestrator, storage, mock_llm_document):
        result = _run(orchestrator.generate_outline(
            prompt="Write a report",
            artifact_type=ArtifactType.document,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        with pytest.raises(ValueError, match="theme_id"):
            _run(orchestrator.export_artifact(
                result["artifact_id"],
                export_format=ExportFormat.docx,
                theme_id="some-theme",
            ))

    def test_strict_layout_rejected_for_document(self, orchestrator, storage, mock_llm_document):
        result = _run(orchestrator.generate_outline(
            prompt="Write a report",
            artifact_type=ArtifactType.document,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        with pytest.raises(ValueError, match="strict_layout"):
            _run(orchestrator.export_artifact(
                result["artifact_id"],
                export_format=ExportFormat.docx,
                strict_layout=True,
            ))

    def test_generate_images_rejected_for_document(self, orchestrator, storage, mock_llm_document):
        result = _run(orchestrator.generate_outline(
            prompt="Write a report",
            artifact_type=ArtifactType.document,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        with pytest.raises(ValueError, match="generate_images"):
            _run(orchestrator.export_artifact(
                result["artifact_id"],
                export_format=ExportFormat.docx,
                generate_images=True,
            ))

    def test_sheet_export_rejects_pptx_format(self, orchestrator, storage, mock_llm_sheet):
        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        with pytest.raises(ValueError, match="not supported"):
            _run(orchestrator.export_artifact(
                result["artifact_id"],
                export_format=ExportFormat.pptx,
            ))


# === Phase 5: Sheet Export Tests ===


class TestSheetExportLifecycle:
    def test_sheet_export_xlsx_lifecycle(self, orchestrator, storage, mock_llm_sheet):
        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        job = _run(orchestrator.export_artifact(
            result["artifact_id"],
            export_format=ExportFormat.xlsx,
        ))
        assert job["status"] == "completed"
        assert job["format"] == "xlsx"
        assert job["validator_results"]["valid"] is True

    def test_sheet_export_csv_lifecycle(self, orchestrator, storage, mock_llm_sheet):
        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        job = _run(orchestrator.export_artifact(
            result["artifact_id"],
            export_format=ExportFormat.csv,
        ))
        assert job["status"] == "completed"
        assert job["format"] == "csv"
        assert job["output_uri"].endswith(".zip")
        assert job["validator_results"]["valid"] is True
        assert job["validator_results"]["format"] == "csv_zip"
        assert "exported_tabs" in job["validator_results"]

    def test_sheet_export_rejects_theme_id(self, orchestrator, storage, mock_llm_sheet):
        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        with pytest.raises(ValueError, match="theme_id"):
            _run(orchestrator.export_artifact(
                result["artifact_id"],
                export_format=ExportFormat.xlsx,
                theme_id="some-theme",
            ))

    def test_sheet_export_rejects_strict_layout(self, orchestrator, storage, mock_llm_sheet):
        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        with pytest.raises(ValueError, match="strict_layout"):
            _run(orchestrator.export_artifact(
                result["artifact_id"],
                export_format=ExportFormat.xlsx,
                strict_layout=True,
            ))

    def test_sheet_export_rejects_generate_images(self, orchestrator, storage, mock_llm_sheet):
        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        with pytest.raises(ValueError, match="generate_images"):
            _run(orchestrator.export_artifact(
                result["artifact_id"],
                export_format=ExportFormat.xlsx,
                generate_images=True,
            ))

    def test_sheet_export_stores_validator_results(self, orchestrator, storage, mock_llm_sheet):
        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        job = _run(orchestrator.export_artifact(
            result["artifact_id"],
            export_format=ExportFormat.xlsx,
        ))
        assert job["validator_results"] is not None
        assert "sheet_count" in job["validator_results"]


class TestSheetUploadAnalysis:
    def test_analyze_sheet_upload_creates_revision(self, orchestrator, storage, mock_llm_sheet):
        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        csv_content = b"Name,Score\nAlice,95\nBob,88\n"
        updated = _run(orchestrator.analyze_sheet_upload(
            result["artifact_id"],
            "data.csv",
            csv_content,
            "text/csv",
        ))
        assert updated["content_tree"]["analysis_report"] is not None
        # Should have new revision
        revisions = storage.list_revisions(result["artifact_id"])
        assert len(revisions) >= 2  # initial draft + upload analysis

    def test_analyze_sheet_upload_updates_content_tree(self, orchestrator, storage, mock_llm_sheet):
        result = _run(orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        ))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        csv_content = b"Category,Revenue\nA,100\nB,200\nA,150\n"
        updated = _run(orchestrator.analyze_sheet_upload(
            result["artifact_id"],
            "data.csv",
            csv_content,
            "text/csv",
        ))
        tab_names = [t["name"] for t in updated["content_tree"]["tabs"]]
        assert "Uploaded_Data" in tab_names
        assert "Summary_Stats" in tab_names


# === Phase 6: Edit Loop Tests ===


class TestEditArtifact:
    """Tests for edit_artifact using _patch_override (no real LLM)."""

    def _make_slides_patch(self, index=2, new_title="Edited Title"):
        return {
            "artifact_type": "slides",
            "target": {"kind": "slide_index", "index": index},
            "ops": [{"op": "SET", "path": "title", "value": new_title}],
            "summary": f"Update slide {index} title",
        }

    def _make_doc_patch(self, section_id="sec1", new_content="Edited content."):
        return {
            "artifact_type": "document",
            "target": {"kind": "section_id", "id": section_id},
            "ops": [{"op": "SET", "path": "content", "value": new_content}],
            "summary": f"Update section {section_id}",
        }

    def _make_sheet_patch(self, tab_name="Revenue", new_value=9999):
        return {
            "artifact_type": "sheet",
            "target": {"kind": "tab_name", "name": tab_name},
            "ops": [{"op": "SET", "path": "rows[0][1]", "value": new_value}],
            "summary": f"Update {tab_name} data",
        }

    def test_edit_artifact_creates_revision(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline("Create slides", ArtifactType.slides))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        edit_result = _run(orchestrator.edit_artifact(
            result["artifact_id"],
            instruction="Change slide 2 title",
            _patch_override=self._make_slides_patch(),
        ))
        assert edit_result["edit_result"]["status"] == "applied"
        assert edit_result["edit_result"]["revision_id"] is not None

        revisions = storage.list_revisions(result["artifact_id"])
        assert len(revisions) == 2  # initial + edit

    def test_edit_artifact_no_op_no_revision(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline("Create slides", ArtifactType.slides))
        draft = _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        # SET with same value → no-op
        current_title = draft["content_tree"]["slides"][1]["title"]
        noop_patch = self._make_slides_patch(index=2, new_title=current_title)

        edit_result = _run(orchestrator.edit_artifact(
            result["artifact_id"],
            instruction="No change",
            _patch_override=noop_patch,
        ))
        assert edit_result["edit_result"]["status"] == "no_changes"
        revisions = storage.list_revisions(result["artifact_id"])
        assert len(revisions) == 1  # only initial, no new revision

    def test_edit_artifact_conflict_raises(self, orchestrator, storage, mock_llm_slides):
        from core.studio.orchestrator import ConflictError
        result = _run(orchestrator.generate_outline("Create slides", ArtifactType.slides))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        with pytest.raises(ConflictError):
            _run(orchestrator.edit_artifact(
                result["artifact_id"],
                instruction="Change title",
                base_revision_id="wrong-revision-id",
                _patch_override=self._make_slides_patch(),
            ))

    def test_edit_artifact_dry_run_no_persist(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline("Create slides", ArtifactType.slides))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))

        edit_result = _run(orchestrator.edit_artifact(
            result["artifact_id"],
            instruction="Preview edit",
            mode="dry_run",
            _patch_override=self._make_slides_patch(),
        ))
        assert edit_result["mode"] == "dry_run"
        assert "diff" in edit_result
        assert "patch" in edit_result

        # Should NOT have created a new revision
        revisions = storage.list_revisions(result["artifact_id"])
        assert len(revisions) == 1

    def test_edit_artifact_slides_export_after_edit(self, orchestrator, storage, mock_llm_slides):
        from core.schemas.studio_schema import ExportFormat
        result = _run(orchestrator.generate_outline("Create slides", ArtifactType.slides))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))
        _run(orchestrator.edit_artifact(
            result["artifact_id"],
            instruction="Edit slide 2",
            _patch_override=self._make_slides_patch(),
        ))

        # Export should still work after edit
        job = _run(orchestrator.export_artifact(result["artifact_id"], export_format=ExportFormat.pptx))
        assert job["status"] == "completed"

    def test_edit_artifact_document_export_after_edit(self, orchestrator, storage, mock_llm_document):
        from core.schemas.studio_schema import ExportFormat
        result = _run(orchestrator.generate_outline("Write report", ArtifactType.document))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))
        _run(orchestrator.edit_artifact(
            result["artifact_id"],
            instruction="Update intro",
            _patch_override=self._make_doc_patch(),
        ))

        job = _run(orchestrator.export_artifact(result["artifact_id"], export_format=ExportFormat.docx))
        assert job["status"] == "completed"

    def test_edit_artifact_sheet_export_after_edit(self, orchestrator, storage, mock_llm_sheet):
        from core.schemas.studio_schema import ExportFormat
        result = _run(orchestrator.generate_outline("Create model", ArtifactType.sheet))
        _run(orchestrator.approve_and_generate_draft(result["artifact_id"]))
        _run(orchestrator.edit_artifact(
            result["artifact_id"],
            instruction="Update revenue",
            _patch_override=self._make_sheet_patch(),
        ))

        job = _run(orchestrator.export_artifact(result["artifact_id"], export_format=ExportFormat.xlsx))
        assert job["status"] == "completed"

    def test_edit_artifact_no_content_tree_rejected(self, orchestrator, storage, mock_llm_slides):
        result = _run(orchestrator.generate_outline("Create slides", ArtifactType.slides))
        # Don't approve — no content tree
        with pytest.raises(ValueError, match="no content tree"):
            _run(orchestrator.edit_artifact(
                result["artifact_id"],
                instruction="Edit something",
                _patch_override=self._make_slides_patch(),
            ))
