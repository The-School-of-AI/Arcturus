"""Acceptance scaffold for P04 (p04_forge).

Replace these contract tests with feature-level assertions as implementation matures.
"""

from pathlib import Path

import pytest

PROJECT_ID = "P04"
PROJECT_KEY = "p04_forge"
CI_CHECK = "p04-forge-studio"
CHARTER = Path("CAPSTONE/project_charters/P04_forge_ai_document_slides_sheets_studio.md")
DELIVERY_README = Path("CAPSTONE/project_charters/P04_DELIVERY_README.md")
DEMO_SCRIPT = Path("scripts/demos/p04_forge.sh")
THIS_FILE = Path("tests/acceptance/p04_forge/test_exports_open_and_render.py")


def _sample_content_tree_dict() -> dict:
    """Return a 10-slide content tree dict for testing."""
    return {
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
             "elements": [{"id": "e4", "type": "body", "content": "AI platform."}],
             "speaker_notes": "Present the solution."},
            {"id": "s4", "slide_type": "two_column", "title": "Before vs After",
             "elements": [{"id": "e5", "type": "body", "content": "Manual."},
                          {"id": "e6", "type": "body", "content": "Automated."}],
             "speaker_notes": "Compare."},
            {"id": "s5", "slide_type": "timeline", "title": "Roadmap",
             "elements": [{"id": "e7", "type": "bullet_list", "content": ["Q1", "Q2", "Q3"]}],
             "speaker_notes": "Timeline."},
            {"id": "s6", "slide_type": "chart", "title": "Traction",
             "elements": [{"id": "e8", "type": "chart", "content": "Growth chart"}],
             "speaker_notes": "Metrics."},
            {"id": "s7", "slide_type": "quote", "title": "Testimonial",
             "elements": [{"id": "e10", "type": "quote", "content": "Amazing."}],
             "speaker_notes": "Customer."},
            {"id": "s8", "slide_type": "content", "title": "Business Model",
             "elements": [{"id": "e12", "type": "body", "content": "SaaS."}],
             "speaker_notes": "Monetization."},
            {"id": "s9", "slide_type": "team", "title": "Team",
             "elements": [{"id": "e13", "type": "bullet_list", "content": ["Alice", "Bob"]}],
             "speaker_notes": "Team."},
            {"id": "s10", "slide_type": "title", "title": "Thank You",
             "elements": [{"id": "e14", "type": "title", "content": "Thank You"}],
             "speaker_notes": "Close."},
        ],
        "metadata": {"audience": "investors"},
    }


def _charter_text() -> str:
    return CHARTER.read_text(encoding="utf-8")


def test_01_charter_exists() -> None:
    assert CHARTER.exists(), f"Missing charter: {CHARTER}"


def test_02_expanded_gate_contract_present() -> None:
    assert "Expanded Mandatory Test Gate Contract (10 Hard Conditions)" in _charter_text()


def test_03_acceptance_path_declared_in_charter() -> None:
    assert f"Acceptance: " in _charter_text()


def test_04_demo_script_exists() -> None:
    assert DEMO_SCRIPT.exists(), f"Missing demo script: {DEMO_SCRIPT}"


def test_05_demo_script_is_executable() -> None:
    assert DEMO_SCRIPT.stat().st_mode & 0o111, f"Demo script not executable: {DEMO_SCRIPT}"


def test_06_delivery_readme_exists() -> None:
    assert DELIVERY_README.exists(), f"Missing delivery README: {DELIVERY_README}"


def test_07_delivery_readme_has_required_sections() -> None:
    required = [
        "## 1. Scope Delivered",
        "## 2. Architecture Changes",
        "## 3. API And UI Changes",
        "## 4. Mandatory Test Gate Definition",
        "## 5. Test Evidence",
        "## 8. Known Gaps",
        "## 10. Demo Steps",
    ]
    text = DELIVERY_README.read_text(encoding="utf-8")
    for section in required:
        assert section in text, f"Missing section {section} in {DELIVERY_README}"


def test_08_ci_check_declared_in_charter() -> None:
    assert f"CI required check: " in _charter_text()


# === Phase 2: Export + Render Functional Tests ===

def test_09_slides_content_tree_validates() -> None:
    """A sample SlidesContentTree passes Pydantic validation."""
    from core.schemas.studio_schema import Slide, SlideElement, SlidesContentTree

    ct = SlidesContentTree(
        deck_title="Test Deck",
        slides=[
            Slide(
                id="s1",
                slide_type="title",
                title="Welcome",
                elements=[SlideElement(id="e1", type="title", content="Hello")],
                speaker_notes="Greet the audience.",
            ),
        ],
    )
    assert ct.deck_title == "Test Deck"
    assert len(ct.slides) == 1


def test_10_pptx_export_produces_file(tmp_path) -> None:
    """export_to_pptx() creates a valid PPTX file."""
    from core.schemas.studio_schema import Slide, SlideElement, SlidesContentTree
    from core.studio.slides.exporter import export_to_pptx
    from core.studio.slides.themes import get_theme

    ct = SlidesContentTree(
        deck_title="Export Test",
        slides=[
            Slide(
                id="s1", slide_type="title", title="Hello",
                elements=[SlideElement(id="e1", type="title", content="Hello")],
                speaker_notes="Open.",
            ),
        ],
    )
    output = tmp_path / "test.pptx"
    export_to_pptx(ct, get_theme(), output)
    assert output.exists()
    assert output.stat().st_size > 0


def test_11_pptx_open_validation_passes(tmp_path) -> None:
    """validate_pptx() confirms the exported file opens cleanly."""
    from core.schemas.studio_schema import Slide, SlideElement, SlidesContentTree
    from core.studio.slides.exporter import export_to_pptx
    from core.studio.slides.themes import get_theme
    from core.studio.slides.validator import validate_pptx

    ct = SlidesContentTree(
        deck_title="Validation Test",
        slides=[
            Slide(
                id="s1", slide_type="content", title="Slide",
                elements=[SlideElement(id="e1", type="body", content="Content here.")],
                speaker_notes="Talk about this.",
            ),
        ],
    )
    output = tmp_path / "valid.pptx"
    export_to_pptx(ct, get_theme(), output)

    result = validate_pptx(output, expected_slide_count=1)
    assert result["valid"] is True
    assert result["slide_count"] == 1


def test_12_slide_count_in_range() -> None:
    """clamp_slide_count enforces [8, 15] range."""
    from core.studio.slides.generator import clamp_slide_count

    assert clamp_slide_count(3) == 8
    assert clamp_slide_count(50) == 15
    assert 8 <= clamp_slide_count(10) <= 15


def test_13_speaker_notes_present_in_export(tmp_path) -> None:
    """At least one slide has speaker notes in the PPTX."""
    from pptx import Presentation as PptxPresentation
    from core.schemas.studio_schema import Slide, SlideElement, SlidesContentTree
    from core.studio.slides.exporter import export_to_pptx
    from core.studio.slides.themes import get_theme

    ct = SlidesContentTree(
        deck_title="Notes Test",
        slides=[
            Slide(
                id="s1", slide_type="title", title="Intro",
                elements=[SlideElement(id="e1", type="title", content="Intro")],
                speaker_notes="This is a speaker note.",
            ),
        ],
    )
    output = tmp_path / "notes.pptx"
    export_to_pptx(ct, get_theme(), output)

    prs = PptxPresentation(str(output))
    has_notes = any(
        s.notes_slide.notes_text_frame.text.strip()
        for s in prs.slides
    )
    assert has_notes


def test_14_export_job_status_completed(tmp_path) -> None:
    """Export job ends with status=completed for valid input."""
    import asyncio
    from core.schemas.studio_schema import ExportFormat
    from core.studio.orchestrator import ForgeOrchestrator
    from core.studio.storage import StudioStorage
    storage = StudioStorage(base_dir=tmp_path / "studio")
    orch = ForgeOrchestrator(storage)

    import json
    from datetime import datetime, timezone
    from uuid import uuid4
    from core.schemas.studio_schema import Artifact, ArtifactType

    art_id = str(uuid4())
    ct = _sample_content_tree_dict()
    artifact = Artifact(
        id=art_id,
        type=ArtifactType.slides,
        title="Test",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        content_tree=ct,
    )
    storage.save_artifact(artifact)

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            orch.export_artifact(art_id, ExportFormat.pptx)
        )
    finally:
        loop.close()

    assert result["status"] == "completed"


def test_15_invalid_format_returns_error() -> None:
    """Requesting unsupported format returns controlled error."""
    from core.schemas.studio_schema import ExportFormat
    with pytest.raises(ValueError):
        ExportFormat("pdf")


def test_16_export_job_has_validator_results(tmp_path) -> None:
    """Export job includes validator_results."""
    import asyncio
    import json
    from datetime import datetime, timezone
    from uuid import uuid4
    from core.schemas.studio_schema import Artifact, ArtifactType, ExportFormat
    from core.studio.orchestrator import ForgeOrchestrator
    from core.studio.storage import StudioStorage
    storage = StudioStorage(base_dir=tmp_path / "studio")
    orch = ForgeOrchestrator(storage)

    art_id = str(uuid4())
    ct = _sample_content_tree_dict()
    artifact = Artifact(
        id=art_id,
        type=ArtifactType.slides,
        title="Test",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        content_tree=ct,
    )
    storage.save_artifact(artifact)

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            orch.export_artifact(art_id, ExportFormat.pptx)
        )
    finally:
        loop.close()

    vr = result["validator_results"]
    assert "valid" in vr
    assert "slide_count" in vr
    assert "has_notes" in vr
    assert "errors" in vr


def test_17_layout_validator_detects_overflow(tmp_path) -> None:
    """Slide with 2000+ chars triggers layout_valid=False."""
    from core.schemas.studio_schema import Slide, SlideElement, SlidesContentTree
    from core.studio.slides.exporter import export_to_pptx
    from core.studio.slides.themes import get_theme
    from core.studio.slides.validator import validate_pptx

    long_text = "A" * 2500
    ct = SlidesContentTree(
        deck_title="Overflow Test",
        slides=[
            Slide(
                id="s1", slide_type="content", title="Overflow",
                elements=[SlideElement(id="e1", type="body", content=long_text)],
                speaker_notes="Check overflow.",
            ),
        ],
    )
    output = tmp_path / "overflow.pptx"
    export_to_pptx(ct, get_theme(), output)

    result = validate_pptx(output)
    assert result["layout_valid"] is False
    assert len(result["layout_warnings"]) > 0
