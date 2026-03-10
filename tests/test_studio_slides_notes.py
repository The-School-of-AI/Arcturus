"""Tests for core/studio/slides/notes.py — speaker notes quality."""

from core.schemas.studio_schema import Slide, SlideElement, SlidesContentTree
from core.studio.slides.notes import repair_speaker_notes, score_speaker_notes


def _make_slide(slide_type="content", title="Test Slide", body="Some body content.",
                speaker_notes=None):
    elements = [SlideElement(id="e1", type="body", content=body)]
    return Slide(
        id="s1", slide_type=slide_type, title=title,
        elements=elements, speaker_notes=speaker_notes,
    )


def test_score_empty_notes():
    slide = _make_slide(speaker_notes=None)
    score = score_speaker_notes(slide)
    assert score["is_empty"] is True
    assert score["passes"] is False


def test_score_too_short():
    slide = _make_slide(speaker_notes="Just a few words.")
    score = score_speaker_notes(slide)
    assert score["is_too_short"] is True
    assert score["passes"] is False


def test_score_too_long():
    long_notes = " ".join(["word"] * 200)
    slide = _make_slide(speaker_notes=long_notes)
    score = score_speaker_notes(slide)
    assert score["is_too_long"] is True
    assert score["passes"] is False


def test_score_good_notes():
    notes = ("Discuss the key findings from the analysis. "
             "Highlight the growth trend and connect it to the strategic initiative. "
             "Ask the audience for their perspective.")
    slide = _make_slide(speaker_notes=notes)
    score = score_speaker_notes(slide)
    assert score["passes"] is True
    assert score["is_empty"] is False
    assert score["is_too_short"] is False


def test_score_copy_detection():
    body = "The platform automates workflows and reduces manual effort significantly"
    notes = "The platform automates workflows and reduces manual effort significantly for teams"
    slide = _make_slide(body=body, speaker_notes=notes)
    score = score_speaker_notes(slide)
    assert score["is_copy"] is True
    assert score["passes"] is False


def test_score_title_slide_relaxed():
    slide = _make_slide(slide_type="title", speaker_notes="Welcome everyone to the opening of this presentation today.")
    score = score_speaker_notes(slide, index=0, total=10)
    assert score["passes"] is True


def test_repair_empty_notes():
    ct = SlidesContentTree(
        deck_title="Test",
        slides=[_make_slide(speaker_notes=None)],
    )
    repaired = repair_speaker_notes(ct)
    assert repaired.slides[0].speaker_notes
    assert len(repaired.slides[0].speaker_notes) > 10


def test_repair_too_short():
    ct = SlidesContentTree(
        deck_title="Test",
        slides=[_make_slide(speaker_notes="Short note.")],
    )
    repaired = repair_speaker_notes(ct)
    assert len(repaired.slides[0].speaker_notes.split()) >= 8


def test_repair_preserves_good_notes():
    good_notes = ("Discuss the key findings from the analysis. "
                  "Highlight the growth trend and connect it to the strategic initiative. "
                  "Ask the audience for their perspective.")
    ct = SlidesContentTree(
        deck_title="Test",
        slides=[_make_slide(speaker_notes=good_notes)],
    )
    repaired = repair_speaker_notes(ct)
    assert repaired.slides[0].speaker_notes == good_notes


def test_repair_returns_new_tree():
    original_notes = "Short."
    ct = SlidesContentTree(
        deck_title="Test",
        slides=[_make_slide(speaker_notes=original_notes)],
    )
    repaired = repair_speaker_notes(ct)
    # Input not mutated
    assert ct.slides[0].speaker_notes == original_notes
    assert repaired is not ct
