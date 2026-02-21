"""Tests for core/studio/slides/generator.py — deterministic planner."""

import pytest

from core.schemas.studio_schema import Slide, SlideElement, SlidesContentTree
from core.studio.slides.generator import (
    MAX_SLIDES,
    MIN_SLIDES,
    clamp_slide_count,
    compute_seed,
    enforce_slide_count,
    plan_slide_sequence,
)
from core.studio.slides.types import SLIDE_TYPES


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
    seed = compute_seed("test-id")
    for count in [8, 10, 12, 15]:
        seq = plan_slide_sequence(count, seed)
        assert len(seq) == count


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
    ct = _make_content_tree(5)
    result = enforce_slide_count(ct)
    assert len(result.slides) == MIN_SLIDES


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
