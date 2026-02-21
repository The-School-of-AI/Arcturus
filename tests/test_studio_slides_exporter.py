"""Tests for core/studio/slides/exporter.py — PPTX rendering."""

import pytest
from pathlib import Path

from pptx import Presentation

from core.schemas.studio_schema import Slide, SlideElement, SlidesContentTree
from core.studio.slides.exporter import SLIDE_HEIGHT, SLIDE_WIDTH, export_to_pptx
from core.studio.slides.themes import get_theme


@pytest.fixture
def sample_content_tree():
    return SlidesContentTree(
        deck_title="Test Deck",
        subtitle="Test Subtitle",
        slides=[
            Slide(
                id="s1",
                slide_type="title",
                title="Welcome",
                elements=[
                    SlideElement(id="e1", type="title", content="Welcome"),
                    SlideElement(id="e2", type="subtitle", content="A test deck"),
                ],
                speaker_notes="Open with a greeting.",
            ),
            Slide(
                id="s2",
                slide_type="content",
                title="Agenda",
                elements=[
                    SlideElement(id="e3", type="title", content="Agenda"),
                    SlideElement(id="e4", type="bullet_list", content=["Item 1", "Item 2", "Item 3"]),
                ],
                speaker_notes="Walk through the agenda items.",
            ),
            Slide(
                id="s3",
                slide_type="two_column",
                title="Comparison",
                elements=[
                    SlideElement(id="e5", type="body", content="Left column content."),
                    SlideElement(id="e6", type="body", content="Right column content."),
                ],
                speaker_notes="Compare both sides.",
            ),
            Slide(
                id="s4",
                slide_type="quote",
                title="Inspiration",
                elements=[
                    SlideElement(id="e7", type="quote", content="The best way to predict the future is to invent it."),
                    SlideElement(id="e8", type="body", content="Alan Kay"),
                ],
                speaker_notes="Pause for effect.",
            ),
            Slide(
                id="s5",
                slide_type="code",
                title="Code Example",
                elements=[
                    SlideElement(id="e9", type="code", content="def hello():\n    print('Hello world')"),
                ],
                speaker_notes="Walk through the code.",
            ),
        ],
    )


@pytest.fixture
def default_theme():
    return get_theme()


def test_export_creates_file(sample_content_tree, default_theme, tmp_path):
    output = tmp_path / "test.pptx"
    result = export_to_pptx(sample_content_tree, default_theme, output)
    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_export_slide_count(sample_content_tree, default_theme, tmp_path):
    output = tmp_path / "test.pptx"
    export_to_pptx(sample_content_tree, default_theme, output)
    prs = Presentation(str(output))
    assert len(prs.slides) == 5


def test_export_speaker_notes_present(sample_content_tree, default_theme, tmp_path):
    output = tmp_path / "test.pptx"
    export_to_pptx(sample_content_tree, default_theme, output)
    prs = Presentation(str(output))
    has_notes = False
    for slide in prs.slides:
        try:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                has_notes = True
                break
        except Exception:
            continue
    assert has_notes


def test_export_all_slides_have_notes(sample_content_tree, default_theme, tmp_path):
    output = tmp_path / "test.pptx"
    export_to_pptx(sample_content_tree, default_theme, output)
    prs = Presentation(str(output))
    for i, slide in enumerate(prs.slides):
        notes = slide.notes_slide.notes_text_frame.text.strip()
        assert notes, f"Slide {i+1} missing speaker notes"


def test_export_slide_dimensions(sample_content_tree, default_theme, tmp_path):
    output = tmp_path / "test.pptx"
    export_to_pptx(sample_content_tree, default_theme, output)
    prs = Presentation(str(output))
    assert prs.slide_width == SLIDE_WIDTH
    assert prs.slide_height == SLIDE_HEIGHT


def test_export_title_slide_rendering(sample_content_tree, default_theme, tmp_path):
    output = tmp_path / "test.pptx"
    export_to_pptx(sample_content_tree, default_theme, output)
    prs = Presentation(str(output))
    title_slide = prs.slides[0]
    texts = [shape.text_frame.text for shape in title_slide.shapes if shape.has_text_frame]
    assert any("Welcome" in t for t in texts)


def test_export_content_slide_rendering(sample_content_tree, default_theme, tmp_path):
    output = tmp_path / "test.pptx"
    export_to_pptx(sample_content_tree, default_theme, output)
    prs = Presentation(str(output))
    content_slide = prs.slides[1]
    texts = [shape.text_frame.text for shape in content_slide.shapes if shape.has_text_frame]
    all_text = " ".join(texts)
    assert "Agenda" in all_text
    assert "Item 1" in all_text


def test_export_two_column_rendering(sample_content_tree, default_theme, tmp_path):
    output = tmp_path / "test.pptx"
    export_to_pptx(sample_content_tree, default_theme, output)
    prs = Presentation(str(output))
    two_col_slide = prs.slides[2]
    # Two-column should have at least 3 shapes (title + 2 columns)
    assert len(two_col_slide.shapes) >= 3


def test_export_quote_slide_rendering(sample_content_tree, default_theme, tmp_path):
    output = tmp_path / "test.pptx"
    export_to_pptx(sample_content_tree, default_theme, output)
    prs = Presentation(str(output))
    quote_slide = prs.slides[3]
    texts = [shape.text_frame.text for shape in quote_slide.shapes if shape.has_text_frame]
    all_text = " ".join(texts)
    assert "predict the future" in all_text


def test_export_code_slide_rendering(sample_content_tree, default_theme, tmp_path):
    output = tmp_path / "test.pptx"
    export_to_pptx(sample_content_tree, default_theme, output)
    prs = Presentation(str(output))
    code_slide = prs.slides[4]
    texts = [shape.text_frame.text for shape in code_slide.shapes if shape.has_text_frame]
    all_text = " ".join(texts)
    assert "hello" in all_text


def test_export_with_different_themes(sample_content_tree, tmp_path):
    for theme_id in ["corporate-blue", "tech-dark", "startup-bold"]:
        theme = get_theme(theme_id)
        output = tmp_path / f"{theme_id}.pptx"
        export_to_pptx(sample_content_tree, theme, output)
        prs = Presentation(str(output))
        assert len(prs.slides) == 5


def test_export_rejects_empty_slides_list(default_theme, tmp_path):
    ct = SlidesContentTree(deck_title="Empty", slides=[])
    output = tmp_path / "empty.pptx"
    # Empty slides produces a valid but empty PPTX (no crash)
    export_to_pptx(ct, default_theme, output)
    prs = Presentation(str(output))
    assert len(prs.slides) == 0


def test_export_output_directory_created(sample_content_tree, default_theme, tmp_path):
    output = tmp_path / "nested" / "deep" / "test.pptx"
    export_to_pptx(sample_content_tree, default_theme, output)
    assert output.exists()


def test_export_unknown_slide_type_fallback(default_theme, tmp_path):
    ct = SlidesContentTree(
        deck_title="Unknown Types",
        slides=[
            Slide(
                id="s1",
                slide_type="mystery_type",
                title="Unknown",
                elements=[
                    SlideElement(id="e1", type="body", content="Falls back to content renderer."),
                ],
                speaker_notes="Should not crash.",
            ),
        ],
    )
    output = tmp_path / "unknown.pptx"
    export_to_pptx(ct, default_theme, output)
    prs = Presentation(str(output))
    assert len(prs.slides) == 1
