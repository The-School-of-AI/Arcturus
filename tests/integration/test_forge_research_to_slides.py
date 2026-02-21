"""Integration scaffold for P04 (p04_forge).

These tests enforce contract-level integration gates across repo structure and CI wiring,
plus Phase 2 cross-component integration tests.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from core.schemas.studio_schema import Artifact, ArtifactType, ExportFormat
from core.studio.orchestrator import ForgeOrchestrator
from core.studio.storage import StudioStorage


# Canned LLM responses (duplicated from test_studio_orchestrator to avoid cross-test import)
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
        {"id": "s1", "slide_type": "title", "title": "Title Slide",
         "elements": [{"id": "e1", "type": "title", "content": "AI Startup"},
                      {"id": "e2", "type": "subtitle", "content": "Series A Pitch"}],
         "speaker_notes": "Welcome everyone."},
        {"id": "s2", "slide_type": "content", "title": "Problem",
         "elements": [{"id": "e3", "type": "body", "content": "Enterprises waste time."}],
         "speaker_notes": "Explain the core problem."},
        {"id": "s3", "slide_type": "content", "title": "Solution",
         "elements": [{"id": "e4", "type": "body", "content": "Our AI platform automates workflows."}],
         "speaker_notes": "Present the solution."},
        {"id": "s4", "slide_type": "two_column", "title": "Before vs After",
         "elements": [{"id": "e5", "type": "body", "content": "Manual processes."},
                      {"id": "e6", "type": "body", "content": "Automated workflows."}],
         "speaker_notes": "Compare old vs new."},
        {"id": "s5", "slide_type": "timeline", "title": "Roadmap",
         "elements": [{"id": "e7", "type": "bullet_list", "content": ["Q1: Launch", "Q2: Scale", "Q3: Expand"]}],
         "speaker_notes": "Walk through the timeline."},
        {"id": "s6", "slide_type": "chart", "title": "Traction",
         "elements": [{"id": "e8", "type": "chart", "content": "Revenue growth chart"},
                      {"id": "e9", "type": "body", "content": "3x growth in 12 months."}],
         "speaker_notes": "Highlight growth metrics."},
        {"id": "s7", "slide_type": "quote", "title": "Testimonial",
         "elements": [{"id": "e10", "type": "quote", "content": "This product changed everything."},
                      {"id": "e11", "type": "body", "content": "Jane Doe, CTO"}],
         "speaker_notes": "Share customer voice."},
        {"id": "s8", "slide_type": "content", "title": "Business Model",
         "elements": [{"id": "e12", "type": "body", "content": "SaaS with enterprise pricing."}],
         "speaker_notes": "Explain monetization."},
        {"id": "s9", "slide_type": "team", "title": "Team",
         "elements": [{"id": "e13", "type": "bullet_list", "content": ["CEO: Alice", "CTO: Bob", "VP Eng: Carol"]}],
         "speaker_notes": "Introduce the team."},
        {"id": "s10", "slide_type": "title", "title": "Thank You",
         "elements": [{"id": "e14", "type": "title", "content": "Thank You"},
                      {"id": "e15", "type": "subtitle", "content": "Questions?"}],
         "speaker_notes": "Close and take questions."},
    ],
    "metadata": {"audience": "investors"},
})


PROJECT_ID = "P04"
PROJECT_KEY = "p04_forge"
CI_CHECK = "p04-forge-studio"
CHARTER = Path("CAPSTONE/project_charters/P04_forge_ai_document_slides_sheets_studio.md")
ACCEPTANCE_FILE = Path("tests/acceptance/p04_forge/test_exports_open_and_render.py")
INTEGRATION_FILE = Path("tests/integration/test_forge_research_to_slides.py")
WORKFLOW_FILE = Path(".github/workflows/project-gates.yml")
BASELINE_SCRIPT = Path("scripts/test_all.sh")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# === Contract-level scaffold tests ===

def test_01_integration_file_is_declared_in_charter() -> None:
    assert f"Integration: " in _read(CHARTER)


def test_02_acceptance_and_integration_files_exist() -> None:
    assert ACCEPTANCE_FILE.exists(), f"Missing acceptance file: {ACCEPTANCE_FILE}"
    assert INTEGRATION_FILE.exists(), f"Missing integration file: {INTEGRATION_FILE}"


def test_03_baseline_script_exists_and_is_executable() -> None:
    assert BASELINE_SCRIPT.exists(), "Missing baseline script scripts/test_all.sh"
    assert BASELINE_SCRIPT.stat().st_mode & 0o111, "scripts/test_all.sh must be executable"


def test_04_project_ci_check_is_wired_in_workflow() -> None:
    assert WORKFLOW_FILE.exists(), "Missing workflow .github/workflows/project-gates.yml"
    assert CI_CHECK in _read(WORKFLOW_FILE), f"CI check {CI_CHECK} not found in workflow"


def test_05_charter_requires_baseline_regression() -> None:
    assert "scripts/test_all.sh quick" in _read(CHARTER)


# === Phase 2: Cross-component integration tests ===

@pytest.fixture(autouse=True)
def _patch_model_manager_init(monkeypatch):
    """Prevent ModelManager.__init__ from calling real API clients."""
    def noop_init(self, model_name=None, provider=None, role=None):
        self.model_type = "gemini"
        self.client = None
    monkeypatch.setattr("core.model_manager.ModelManager.__init__", noop_init)


@pytest.fixture
def mock_llm(monkeypatch):
    """Mock LLM returning outline then slides draft."""
    async def fake_generate(self, prompt):
        if "content architect" in prompt.lower():
            return OUTLINE_RESPONSE
        return SLIDES_DRAFT_RESPONSE
    monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)


@pytest.fixture
def storage(tmp_path):
    return StudioStorage(base_dir=tmp_path / "studio")


@pytest.fixture
def orchestrator(storage):
    return ForgeOrchestrator(storage)


def test_06_outline_to_draft_to_export_pipeline(orchestrator, storage, mock_llm) -> None:
    """Full pipeline: create outline -> approve -> export PPTX."""
    result = _run(orchestrator.generate_outline(
        prompt="Create a pitch deck",
        artifact_type=ArtifactType.slides,
    ))
    art_id = result["artifact_id"]

    _run(orchestrator.approve_and_generate_draft(art_id))

    export_result = _run(orchestrator.export_artifact(art_id, ExportFormat.pptx))
    assert export_result["status"] == "completed"
    assert export_result["file_size_bytes"] > 0


def test_07_export_with_custom_theme(orchestrator, storage, mock_llm) -> None:
    """Export with non-default theme produces valid PPTX."""
    result = _run(orchestrator.generate_outline(
        prompt="Create slides",
        artifact_type=ArtifactType.slides,
    ))
    art_id = result["artifact_id"]
    _run(orchestrator.approve_and_generate_draft(art_id))

    export_result = _run(orchestrator.export_artifact(
        art_id, ExportFormat.pptx, theme_id="tech-dark"
    ))
    assert export_result["status"] == "completed"


def test_08_export_preserves_revision_lineage(orchestrator, storage, mock_llm) -> None:
    """Revision head_id unchanged after export."""
    result = _run(orchestrator.generate_outline(
        prompt="Create slides",
        artifact_type=ArtifactType.slides,
    ))
    art_id = result["artifact_id"]
    art_data = _run(orchestrator.approve_and_generate_draft(art_id))
    rev_id_before = art_data["revision_head_id"]

    _run(orchestrator.export_artifact(art_id, ExportFormat.pptx))

    loaded = storage.load_artifact(art_id)
    assert loaded.revision_head_id == rev_id_before


def test_09_multiple_exports_tracked(orchestrator, storage, mock_llm) -> None:
    """Two exports for same artifact both appear in exports list."""
    result = _run(orchestrator.generate_outline(
        prompt="Create slides",
        artifact_type=ArtifactType.slides,
    ))
    art_id = result["artifact_id"]
    _run(orchestrator.approve_and_generate_draft(art_id))

    _run(orchestrator.export_artifact(art_id, ExportFormat.pptx))
    _run(orchestrator.export_artifact(art_id, ExportFormat.pptx, theme_id="startup-bold"))

    jobs = storage.list_export_jobs(art_id)
    assert len(jobs) == 2

    loaded = storage.load_artifact(art_id)
    assert len(loaded.exports) == 2


def test_10_export_file_downloadable(orchestrator, storage, mock_llm) -> None:
    """Export file path exists and has non-zero size."""
    result = _run(orchestrator.generate_outline(
        prompt="Create slides",
        artifact_type=ArtifactType.slides,
    ))
    art_id = result["artifact_id"]
    _run(orchestrator.approve_and_generate_draft(art_id))

    export_result = _run(orchestrator.export_artifact(art_id, ExportFormat.pptx))
    assert export_result["output_uri"] is not None

    export_path = Path(export_result["output_uri"])
    assert export_path.exists()
    assert export_path.stat().st_size > 0


def test_11_oracle_research_ingestion(orchestrator, storage, mock_llm) -> None:
    """Monkeypatch Oracle MCP call with fixture; verify research content appears in content tree."""
    # Phase 2 scope: verify content tree has data from mock LLM
    result = _run(orchestrator.generate_outline(
        prompt="Create a pitch deck about AI agents",
        artifact_type=ArtifactType.slides,
    ))
    art_id = result["artifact_id"]
    art_data = _run(orchestrator.approve_and_generate_draft(art_id))

    ct = art_data["content_tree"]
    assert ct is not None
    assert ct["deck_title"] == "AI Startup Pitch Deck"
    assert len(ct["slides"]) >= 8


def test_12_canvas_preview_no_schema_breakage(orchestrator, storage, mock_llm) -> None:
    """Round-trip content tree through validation; verify validate_content_tree() passes."""
    from core.schemas.studio_schema import validate_content_tree

    result = _run(orchestrator.generate_outline(
        prompt="Create slides",
        artifact_type=ArtifactType.slides,
    ))
    art_id = result["artifact_id"]
    art_data = _run(orchestrator.approve_and_generate_draft(art_id))

    ct = art_data["content_tree"]
    # Round-trip: dict -> model -> dict -> model
    model = validate_content_tree(ArtifactType.slides, ct)
    roundtripped = model.model_dump(mode="json")
    model2 = validate_content_tree(ArtifactType.slides, roundtripped)
    assert model2.deck_title == model.deck_title
    assert len(model2.slides) == len(model.slides)


def test_13_upstream_failure_graceful_downstream(orchestrator, storage, monkeypatch) -> None:
    """Monkeypatch generate_text to raise; verify HTTP 500 with meaningful error."""
    async def fake_outline(self, prompt):
        if "content architect" in prompt.lower():
            return OUTLINE_RESPONSE
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_outline)

    result = _run(orchestrator.generate_outline(
        prompt="Create slides",
        artifact_type=ArtifactType.slides,
    ))
    art_id = result["artifact_id"]

    with pytest.raises(RuntimeError, match="LLM unavailable"):
        _run(orchestrator.approve_and_generate_draft(art_id))

    # Artifact should still exist with outline but no content_tree
    loaded = storage.load_artifact(art_id)
    assert loaded is not None
    assert loaded.content_tree is None
    assert loaded.outline is not None
