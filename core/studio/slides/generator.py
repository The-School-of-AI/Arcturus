"""Deterministic slide sequence planner for Forge slides."""

import hashlib
import random

from core.studio.slides.types import NARRATIVE_ARC, SLIDE_TYPE_ELEMENTS

MIN_SLIDES = 8
MAX_SLIDES = 15
DEFAULT_SLIDES = 10


def compute_seed(artifact_id: str) -> int:
    """Compute a deterministic seed from artifact ID."""
    return int(hashlib.sha256(artifact_id.encode()).hexdigest()[:8], 16)


def clamp_slide_count(requested: int | float | str | None = None) -> int:
    """Clamp requested slide count to [8, 15] range.

    Returns DEFAULT_SLIDES if requested is None or invalid.
    """
    if requested is None:
        return DEFAULT_SLIDES

    normalized: int
    if isinstance(requested, bool):
        return DEFAULT_SLIDES
    if isinstance(requested, int):
        normalized = requested
    elif isinstance(requested, float):
        if not requested.is_integer():
            return DEFAULT_SLIDES
        normalized = int(requested)
    elif isinstance(requested, str):
        stripped = requested.strip()
        if not stripped:
            return DEFAULT_SLIDES
        try:
            normalized = int(stripped)
        except ValueError:
            return DEFAULT_SLIDES
    else:
        return DEFAULT_SLIDES

    return max(MIN_SLIDES, min(MAX_SLIDES, normalized))


def plan_slide_sequence(
    slide_count: int,
    seed: int,
    narrative_arc: list[str] | None = None,
) -> list[dict]:
    """Plan a deterministic slide type sequence based on seed and count.

    Returns a list of dicts with slide_type, suggested_elements, position.
    """
    rng = random.Random(seed)
    arc = narrative_arc or NARRATIVE_ARC

    if slide_count <= len(arc):
        # Sample evenly from arc, always keeping first and last
        indices = [0] + sorted(rng.sample(range(1, len(arc) - 1), slide_count - 2)) + [len(arc) - 1]
        sequence = [arc[i] for i in indices]
    else:
        # Repeat body slides to fill
        sequence = list(arc)
        body_types = ["content", "two_column", "comparison", "timeline", "chart"]
        while len(sequence) < slide_count:
            insert_pos = rng.randint(2, len(sequence) - 2)
            sequence.insert(insert_pos, rng.choice(body_types))

    result = []
    for i, slide_type in enumerate(sequence):
        if i == 0:
            position = "opening"
        elif i == len(sequence) - 1:
            position = "closing"
        else:
            position = "body"

        result.append({
            "slide_type": slide_type,
            "suggested_elements": SLIDE_TYPE_ELEMENTS.get(slide_type, ["title", "body"]),
            "position": position,
        })

    return result


def enforce_slide_count(
    content_tree: "SlidesContentTree",
    target_count: int | None = None,
) -> "SlidesContentTree":
    """Enforce [MIN_SLIDES, MAX_SLIDES] range on a content tree.

    - Over MAX_SLIDES: keep first + last slide, trim body from the end
    - Under MIN_SLIDES: insert filler 'content' slides before the closing slide
    - Within range: no-op (returns content_tree unchanged)

    Returns a new SlidesContentTree (does not mutate the input).
    """
    slides = list(content_tree.slides)
    if len(slides) == 0:
        raise ValueError("Cannot enforce slide count on empty slides list")

    # Over MAX: trim body slides from the end (preserve first and last)
    if len(slides) > MAX_SLIDES:
        opening = slides[0]
        closing = slides[-1]
        body = slides[1:-1]
        body = body[: MAX_SLIDES - 2]
        slides = [opening] + body + [closing]

    # Under MIN: pad with filler content slides before closing.
    # For a single-slide deck, preserve that original slide in the first slot.
    if len(slides) < MIN_SLIDES:
        from core.schemas.studio_schema import Slide, SlideElement
        if len(slides) == 1:
            opening = slides[0]
            padded = [opening]
            filler_count = MIN_SLIDES - 1
            for i in range(filler_count):
                filler = Slide(
                    id=f"filler-{i+1}",
                    slide_type="content",
                    title=f"Section {len(padded) + 1}",
                    elements=[
                        SlideElement(id=f"filler-e-{i+1}", type="body", content="Content to be developed."),
                    ],
                    speaker_notes="Expand on this section with relevant details.",
                )
                padded.append(filler)
            slides = padded
        else:
            closing = slides[-1]
            body = slides[:-1]
            filler_count = MIN_SLIDES - len(slides)
            for i in range(filler_count):
                filler = Slide(
                    id=f"filler-{i+1}",
                    slide_type="content",
                    title=f"Section {len(body) + 1}",
                    elements=[
                        SlideElement(id=f"filler-e-{i+1}", type="body", content="Content to be developed."),
                    ],
                    speaker_notes="Expand on this section with relevant details.",
                )
                body.append(filler)
            slides = body + [closing]

    return content_tree.model_copy(update={"slides": slides})
