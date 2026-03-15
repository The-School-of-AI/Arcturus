"""Tests for core/studio/slides/generator.py — deterministic planner."""

import pytest

from core.schemas.studio_schema import Slide, SlideElement, SlidesContentTree
from core.studio.slides.generator import (
    DEFAULT_SLIDES,
    MAX_SLIDES,
    MIN_SLIDES,
    _STRUCTURAL_TYPES,
    clamp_slide_count,
    compute_seed,
    enforce_slide_count,
    normalize_slide_outline,
    plan_slide_sequence,
    resolve_slide_count,
)
from core.studio.slides.types import SLIDE_TYPES


def _count_content_slides(seq_or_slides):
    """Count non-structural slides (not title or section_divider)."""
    if isinstance(seq_or_slides, list) and seq_or_slides and isinstance(seq_or_slides[0], dict):
        # plan_slide_sequence result
        return sum(1 for s in seq_or_slides if s["slide_type"] not in _STRUCTURAL_TYPES)
    # SlidesContentTree.slides
    return sum(1 for s in seq_or_slides if s.slide_type not in _STRUCTURAL_TYPES)


# === compute_seed ===

def test_compute_seed_deterministic():
    seed1 = compute_seed("artifact-abc-123")
    seed2 = compute_seed("artifact-abc-123")
    assert seed1 == seed2


def test_compute_seed_different_inputs():
    seed1 = compute_seed("artifact-abc-123")
    seed2 = compute_seed("artifact-xyz-789")
    assert seed1 != seed2


# === clamp_slide_count ===

def test_clamp_slide_count_default():
    assert clamp_slide_count(None) == 10


def test_clamp_slide_count_within_range():
    assert clamp_slide_count(12) == 12


def test_clamp_slide_count_below_min():
    assert clamp_slide_count(3) == MIN_SLIDES


def test_clamp_slide_count_above_max():
    assert clamp_slide_count(50) == MAX_SLIDES


def test_clamp_slide_count_numeric_string():
    assert clamp_slide_count("10") == 10


def test_clamp_slide_count_numeric_string_with_whitespace():
    assert clamp_slide_count("  9  ") == 9


def test_clamp_slide_count_float_integer_value():
    assert clamp_slide_count(12.0) == 12


def test_clamp_slide_count_invalid_string_uses_default():
    assert clamp_slide_count("abc") == 10


def test_clamp_slide_count_non_integer_float_uses_default():
    assert clamp_slide_count(10.5) == 10


# === plan_slide_sequence ===

def test_plan_slide_sequence_count():
    """slide_count refers to content slides only; total includes structural."""
    seed = compute_seed("test-id")
    for count in [3, 5, 8, 10, 12, 15]:
        seq = plan_slide_sequence(count, seed)
        content = _count_content_slides(seq)
        assert content == count, f"Expected {count} content slides, got {content}"
        # Must always have opening + closing title
        assert seq[0]["slide_type"] == "title"
        assert seq[-1]["slide_type"] == "title"
        # Total must be > content (at least +2 for opening/closing)
        assert len(seq) >= count + 2


def test_plan_slide_sequence_deterministic():
    seed = compute_seed("test-id")
    seq1 = plan_slide_sequence(10, seed)
    seq2 = plan_slide_sequence(10, seed)
    assert seq1 == seq2


def test_plan_slide_sequence_different_seeds():
    # Use count < arc length so sampling has actual randomness
    seq1 = plan_slide_sequence(8, compute_seed("id-a"))
    seq2 = plan_slide_sequence(8, compute_seed("id-b"))
    types1 = [s["slide_type"] for s in seq1]
    types2 = [s["slide_type"] for s in seq2]
    assert types1 != types2


def test_plan_slide_sequence_opens_with_title():
    seed = compute_seed("test-id")
    seq = plan_slide_sequence(10, seed)
    assert seq[0]["slide_type"] == "title"


def test_plan_slide_sequence_closes_with_title():
    seed = compute_seed("test-id")
    seq = plan_slide_sequence(10, seed)
    assert seq[-1]["slide_type"] == "title"


def test_plan_slide_sequence_positions():
    seed = compute_seed("test-id")
    seq = plan_slide_sequence(10, seed)
    assert seq[0]["position"] == "opening"
    assert seq[-1]["position"] == "closing"
    for s in seq[1:-1]:
        assert s["position"] == "body"


def test_plan_slide_sequence_all_types_valid():
    seed = compute_seed("test-id")
    seq = plan_slide_sequence(15, seed)
    for s in seq:
        assert s["slide_type"] in SLIDE_TYPES


# === enforce_slide_count ===

def _make_content_tree(n_slides: int) -> SlidesContentTree:
    slides = []
    for i in range(n_slides):
        stype = "title" if i == 0 or i == n_slides - 1 else "content"
        slides.append(Slide(
            id=f"s{i+1}",
            slide_type=stype,
            title=f"Slide {i+1}",
            elements=[SlideElement(id=f"e{i+1}", type="body", content=f"Content {i+1}")],
            speaker_notes=f"Notes for slide {i+1}",
        ))
    return SlidesContentTree(deck_title="Test", slides=slides)


def test_enforce_slide_count_over_max():
    ct = _make_content_tree(20)
    result = enforce_slide_count(ct)
    assert len(result.slides) == MAX_SLIDES


def test_enforce_slide_count_under_min():
    ct = _make_content_tree(2)
    result = enforce_slide_count(ct)
    assert len(result.slides) == MIN_SLIDES


def test_enforce_slide_count_five_slides_no_padding():
    """A 5-slide deck should stay at 5 slides (no filler padding)."""
    ct = _make_content_tree(5)
    result = enforce_slide_count(ct)
    assert len(result.slides) == 5
    # No filler slides injected
    assert all(not s.id.startswith("filler") for s in result.slides)


def test_enforce_slide_count_single_slide_keeps_original_first():
    ct = _make_content_tree(1)
    result = enforce_slide_count(ct)
    assert len(result.slides) == MIN_SLIDES
    assert result.slides[0].id == "s1"
    assert result.slides[0].slide_type == "title"


def test_enforce_slide_count_preserves_opening_closing():
    ct = _make_content_tree(20)
    result = enforce_slide_count(ct)
    assert result.slides[0].id == "s1"
    assert result.slides[-1].id == "s20"

    ct2 = _make_content_tree(5)
    result2 = enforce_slide_count(ct2)
    assert result2.slides[0].id == "s1"
    assert result2.slides[-1].id == "s5"


def test_enforce_slide_count_within_range_no_change():
    ct = _make_content_tree(10)
    result = enforce_slide_count(ct)
    assert len(result.slides) == 10
    assert result.slides == ct.slides


# === enforce_slide_count with target_count ===

def test_enforce_slide_count_target_trims_to_exact():
    """10-slide tree with target_count=5 → exactly 5 content slides."""
    ct = _make_content_tree(10)
    result = enforce_slide_count(ct, target_count=5)
    content = _count_content_slides(result.slides)
    assert content == 5
    # Structural slides (opening/closing) preserved
    assert result.slides[0].id == "s1"
    assert result.slides[-1].id == "s10"


def test_enforce_slide_count_target_pads_to_exact():
    """3-slide tree with target_count=6 → exactly 6 content slides (filler added)."""
    ct = _make_content_tree(3)
    result = enforce_slide_count(ct, target_count=6)
    content = _count_content_slides(result.slides)
    assert content == 6


def test_enforce_slide_count_target_clamped_to_max():
    """target_count=20 is clamped to MAX_SLIDES content slides."""
    ct = _make_content_tree(20)
    result = enforce_slide_count(ct, target_count=20)
    content = _count_content_slides(result.slides)
    assert content == MAX_SLIDES


def test_enforce_slide_count_target_clamped_to_min():
    """target_count=1 is clamped to MIN_SLIDES content slides."""
    ct = _make_content_tree(1)
    result = enforce_slide_count(ct, target_count=1)
    content = _count_content_slides(result.slides)
    assert content == MIN_SLIDES


def test_enforce_slide_count_none_target_legacy_behavior():
    """target_count=None preserves legacy [MIN, MAX] range enforcement."""
    ct = _make_content_tree(10)
    result = enforce_slide_count(ct, target_count=None)
    assert len(result.slides) == 10


# === resolve_slide_count ===

def test_resolve_slide_count_explicit_parameter():
    assert resolve_slide_count({"slide_count": 5}) == 5


def test_resolve_slide_count_parameter_takes_priority():
    """Explicit parameter wins over prompt text."""
    assert resolve_slide_count(
        {"slide_count": 5},
        user_prompt="create a 3 slide deck",
    ) == 5


def test_resolve_slide_count_from_prompt():
    assert resolve_slide_count(None, "create a 3 slide deck on global warming") == MIN_SLIDES


def test_resolve_slide_count_from_prompt_pages():
    assert resolve_slide_count({}, "make 7 pages about AI") == 7


def test_resolve_slide_count_hyphenated():
    assert resolve_slide_count(None, "create a 5-slide deck") == 5
    assert resolve_slide_count(None, "7-page presentation on AI") == 7


def test_resolve_slide_count_prompt_clamps_high():
    assert resolve_slide_count(None, "create a 50 slide deck") == MAX_SLIDES


def test_resolve_slide_count_default_fallback():
    assert resolve_slide_count(None) == DEFAULT_SLIDES
    assert resolve_slide_count({}) == DEFAULT_SLIDES
    assert resolve_slide_count({}, "no number here") == DEFAULT_SLIDES


# === normalize_slide_outline ===

class _MockOutline:
    """Minimal outline-like object for testing."""
    def __init__(self, items=None, parameters=None):
        self.items = items or []
        self.parameters = parameters


def test_normalize_slide_outline_stores_resolved_count():
    outline = _MockOutline(items=[1, 2, 3, 4, 5], parameters={})
    result = normalize_slide_outline(outline, user_prompt="create 5 slides")
    assert result.parameters["slide_count"] == 5
    assert len(result.items) == 5


def test_normalize_slide_outline_trims_excess_items():
    """LLM generated 10 items but user asked for 4 slides."""
    items = list(range(10))
    outline = _MockOutline(items=items, parameters={})
    result = normalize_slide_outline(outline, user_prompt="make 4 slides on AI")
    assert len(result.items) == 4
    assert result.parameters["slide_count"] == 4


def test_normalize_slide_outline_no_trim_when_fewer():
    """Don't trim if items <= resolved count."""
    outline = _MockOutline(items=[1, 2, 3], parameters={})
    result = normalize_slide_outline(outline, user_prompt="create 5 slides")
    assert len(result.items) == 3
    assert result.parameters["slide_count"] == 5


def test_normalize_slide_outline_creates_parameters_if_none():
    outline = _MockOutline(items=[1, 2], parameters=None)
    result = normalize_slide_outline(outline, user_prompt="create 5 slides")
    assert result.parameters == {"slide_count": 5}
