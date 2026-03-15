"""Tests for core/studio/slides/layout.py — layout repair for exports."""

from core.schemas.studio_schema import Slide, SlideElement, SlidesContentTree
from core.studio.slides.layout import (
    BLOCK_CHAR_LIMIT,
    SLIDE_CHAR_LIMIT,
    repair_layout,
)


def _make_tree(slides):
    return SlidesContentTree(deck_title="Test", slides=slides)


def _make_slide(elements, slide_type="content", title="Slide"):
    return Slide(
        id="s1", slide_type=slide_type, title=title,
        elements=elements, speaker_notes="Notes.",
    )


def test_repair_truncates_long_body():
    """Body text exceeding 800 chars is truncated at sentence boundary."""
    # Build text: 750 chars of sentences + padding beyond 800
    sentences = "This is a test sentence. " * 30  # ~750 chars
    long_body = sentences + "A" * 200  # pushes well past 800
    assert len(long_body) > BLOCK_CHAR_LIMIT

    tree = _make_tree([_make_slide([
        SlideElement(id="e1", type="body", content=long_body),
    ])])
    repaired = repair_layout(tree)

    body = repaired.slides[0].elements[0].content
    assert len(body) <= BLOCK_CHAR_LIMIT
    # Should end at a sentence boundary (period) since sentences exist
    assert body.rstrip().endswith(".")


def test_repair_trims_bullet_list():
    """Bullet list exceeding block limit has items removed."""
    bullets = [f"Bullet point number {i} with some explanatory text here." for i in range(30)]
    total = sum(len(b) for b in bullets)
    assert total > BLOCK_CHAR_LIMIT

    tree = _make_tree([_make_slide([
        SlideElement(id="e1", type="bullet_list", content=bullets),
    ])])
    repaired = repair_layout(tree)

    result_bullets = repaired.slides[0].elements[0].content
    assert len(result_bullets) < len(bullets)
    assert sum(len(b) for b in result_bullets) <= BLOCK_CHAR_LIMIT


def test_repair_truncates_single_oversized_bullet():
    """A single bullet item exceeding 800 chars is truncated individually."""
    huge_bullet = "This is a very long bullet point. " * 30  # ~1020 chars
    assert len(huge_bullet) > BLOCK_CHAR_LIMIT

    tree = _make_tree([_make_slide([
        SlideElement(id="e1", type="bullet_list", content=[huge_bullet]),
    ])])
    repaired = repair_layout(tree)

    result_bullets = repaired.slides[0].elements[0].content
    assert len(result_bullets) == 1  # still one bullet, just truncated
    assert len(result_bullets[0]) <= BLOCK_CHAR_LIMIT


def test_repair_strips_placeholders():
    """Placeholder patterns are removed from content."""
    tree = _make_tree([_make_slide([
        SlideElement(id="e1", type="body", content="Real content. This is placeholder text to be added later."),
    ])])
    repaired = repair_layout(tree)

    body = repaired.slides[0].elements[0].content
    assert "placeholder" not in body.lower()
    assert "to be added" not in body.lower()
    assert "Real content." in body


def test_repair_preserves_short_content():
    """Content under limits passes through unchanged."""
    original_text = "This is fine."
    tree = _make_tree([_make_slide([
        SlideElement(id="e1", type="body", content=original_text),
    ])])
    repaired = repair_layout(tree)

    assert repaired.slides[0].elements[0].content == original_text


def test_repair_returns_new_tree():
    """Input tree is not mutated; a new tree is returned."""
    original_text = "Original text."
    tree = _make_tree([_make_slide([
        SlideElement(id="e1", type="body", content=original_text),
    ])])
    repaired = repair_layout(tree)

    assert repaired is not tree
    assert repaired.slides[0] is not tree.slides[0]
    # Original should be unchanged
    assert tree.slides[0].elements[0].content == original_text


def test_repair_slide_total_excess():
    """Slide total > 1600 triggers second-pass trim on longest element."""
    # Two body elements that individually are under 800 but together exceed 1600
    text_a = "First sentence here. " + "A" * 790
    text_b = "Second sentence here. " + "B" * 790
    assert len(text_a) + len(text_b) > SLIDE_CHAR_LIMIT

    tree = _make_tree([_make_slide([
        SlideElement(id="e1", type="body", content=text_a),
        SlideElement(id="e2", type="body", content=text_b),
    ])])
    repaired = repair_layout(tree)

    total = sum(
        len(el.content) for el in repaired.slides[0].elements
        if isinstance(el.content, str)
    )
    assert total <= SLIDE_CHAR_LIMIT


def test_repair_title_truncation():
    """Titles longer than 60 chars are truncated at word boundary."""
    long_title = "This is a very long presentation slide title that exceeds the sixty character limit for good layout"
    assert len(long_title) > 60

    tree = _make_tree([_make_slide(
        [SlideElement(id="e1", type="body", content="Content.")],
        title=long_title,
    )])
    repaired = repair_layout(tree)
    assert len(repaired.slides[0].title) <= 63  # 60 + "..."


def test_repair_preserves_dict_content():
    """Chart/table dict content passes through untouched."""
    chart_data = {"chart_type": "bar", "categories": ["Q1", "Q2"], "series": []}
    tree = _make_tree([_make_slide([
        SlideElement(id="e1", type="chart", content=chart_data),
    ])])
    repaired = repair_layout(tree)

    assert repaired.slides[0].elements[0].content == chart_data
