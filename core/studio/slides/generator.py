"""Deterministic slide sequence planner for Forge slides."""

import hashlib
import random
import re

from core.studio.slides.types import NARRATIVE_ARC, SLIDE_TYPE_ELEMENTS

# Varied filler templates: (title, body, slide_type)
_FILLER_TEMPLATES = [
    ("Key Takeaways", "Summarize the core insights from this section.", "content"),
    ("Additional Context", "Background information that supports the main argument.", "two_column"),
    ("Next Steps", "Outline the recommended actions moving forward.", "content"),
    ("Supporting Evidence", "Data and references that reinforce key claims.", "content"),
    ("Deep Dive", "Detailed exploration of a critical subtopic.", "content"),
    ("Lessons Learned", "Practical wisdom gained from experience.", "two_column"),
    ("Agenda Overview", "Preview the key topics and structure of this presentation.", "agenda"),
    ("Data Summary", "Tabular comparison of key metrics and dimensions.", "table"),
]

MIN_SLIDES = 3
MAX_SLIDES = 15
DEFAULT_SLIDES = 10


def compute_seed(artifact_id: str) -> int:
    """Compute a deterministic seed from artifact ID."""
    return int(hashlib.sha256(artifact_id.encode()).hexdigest()[:8], 16)


def clamp_slide_count(requested: int | float | str | None = None) -> int:
    """Clamp requested slide count to [MIN_SLIDES, MAX_SLIDES] range.

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


_SLIDE_COUNT_RE = re.compile(r'\b(\d+)[\s-]*(?:slide|page)s?\b', re.IGNORECASE)


def resolve_slide_count(
    parameters: dict | None,
    user_prompt: str | None = None,
) -> int:
    """Resolve slide count for initial generation.

    Priority: explicit parameter > prompt parse > DEFAULT_SLIDES.
    NOTE: outline_item_count is NOT used here — it's only used after
    outline edits (see approve_and_generate_draft).
    """
    # 1. Explicit parameter (from API field or stored outline parameters)
    if parameters and parameters.get("slide_count") is not None:
        return clamp_slide_count(parameters["slide_count"])

    # 2. Parse from user prompt text
    if user_prompt:
        m = _SLIDE_COUNT_RE.search(user_prompt)
        if m:
            return clamp_slide_count(int(m.group(1)))

    # 3. Default
    return DEFAULT_SLIDES


def normalize_slide_outline(outline, parameters=None, user_prompt=None):
    """Normalize a slides outline after LLM generation.

    - Resolves slide_count from parameters/prompt
    - Stores resolved slide_count in outline.parameters
    - Trims outline items if LLM generated too many
    """
    params = parameters or (outline.parameters if hasattr(outline, "parameters") else {}) or {}

    resolved = resolve_slide_count(params, user_prompt)

    # Store resolved slide_count in outline parameters
    if hasattr(outline, "parameters") and outline.parameters is not None:
        outline.parameters["slide_count"] = resolved
    elif hasattr(outline, "parameters"):
        outline.parameters = {"slide_count": resolved}

    # Trim outline items if LLM generated too many
    if hasattr(outline, "items") and len(outline.items) > resolved:
        outline.items = outline.items[:resolved]

    return outline


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

    sequence = _prevent_consecutive_types(sequence, rng)
    _ensure_image_slide(sequence, rng)

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


def _ensure_image_slide(sequence: list[str], rng: random.Random) -> None:
    """Guarantee at least one image_text slide for visual variety.

    If no image slide exists in the sequence, replace a body-position
    content or two_column slide with image_text.  Mutates in place.
    """
    _IMAGE_TYPES = {"image_text", "image_full"}
    if any(t in _IMAGE_TYPES for t in sequence):
        return

    # Find replaceable body positions (skip opening at 0 / closing at -1)
    # Prefer content/two_column; fall back to other generic body types
    replaceable = [
        i for i in range(2, len(sequence) - 1)
        if sequence[i] in ("content", "two_column")
    ]
    if not replaceable:
        replaceable = [
            i for i in range(1, len(sequence) - 1)
            if sequence[i] not in ("title", "section_divider", "chart")
        ]
    if replaceable:
        idx = rng.choice(replaceable)
        sequence[idx] = "image_text"


def _prevent_consecutive_types(sequence: list[str], rng: random.Random) -> list[str]:
    """Swap consecutive same-type body slides to ensure layout variety."""
    swap_pool = ["content", "two_column", "stat", "comparison", "image_text", "agenda", "table"]
    result = list(sequence)
    for i in range(1, len(result) - 1):  # skip opening/closing
        if result[i] == result[i - 1] and result[i] not in ("title", "section_divider"):
            alternatives = [t for t in swap_pool if t != result[i]]
            result[i] = rng.choice(alternatives)
    return result


def enforce_slide_count(
    content_tree: "SlidesContentTree",
    target_count: int | None = None,
) -> "SlidesContentTree":
    """Enforce slide count on a content tree.

    When target_count is provided: trim/pad to exactly that count (clamped to
    [MIN_SLIDES, MAX_SLIDES]).  When target_count is None: only enforce the
    global [MIN_SLIDES, MAX_SLIDES] range (preserves legacy behavior for
    patch_apply.py edits).

    Returns a new SlidesContentTree (does not mutate the input).
    """
    slides = list(content_tree.slides)
    if len(slides) == 0:
        raise ValueError("Cannot enforce slide count on empty slides list")

    if target_count is not None:
        target = clamp_slide_count(target_count)
        effective_max = target
        effective_min = target
    else:
        effective_max = MAX_SLIDES
        effective_min = MIN_SLIDES

    # Over effective_max: trim body slides from the end (preserve first and last)
    if len(slides) > effective_max:
        opening = slides[0]
        closing = slides[-1]
        body = slides[1:-1]
        body = body[: effective_max - 2]
        slides = [opening] + body + [closing]

    # Under effective_min: pad with filler content slides before closing.
    # For a single-slide deck, preserve that original slide in the first slot.
    if len(slides) < effective_min:
        from core.schemas.studio_schema import Slide, SlideElement
        if len(slides) == 1:
            opening = slides[0]
            padded = [opening]
            filler_count = effective_min - 1
            for i in range(filler_count):
                tmpl = _FILLER_TEMPLATES[i % len(_FILLER_TEMPLATES)]
                filler = Slide(
                    id=f"filler-{i+1}",
                    slide_type=tmpl[2],
                    title=tmpl[0],
                    elements=[
                        SlideElement(id=f"filler-e-{i+1}", type="body", content=tmpl[1]),
                    ],
                    speaker_notes="Expand on this section with relevant details.",
                )
                padded.append(filler)
            slides = padded
        else:
            closing = slides[-1]
            body = slides[:-1]
            filler_count = effective_min - len(slides)
            for i in range(filler_count):
                tmpl = _FILLER_TEMPLATES[i % len(_FILLER_TEMPLATES)]
                filler = Slide(
                    id=f"filler-{i+1}",
                    slide_type=tmpl[2],
                    title=tmpl[0],
                    elements=[
                        SlideElement(id=f"filler-e-{i+1}", type="body", content=tmpl[1]),
                    ],
                    speaker_notes="Expand on this section with relevant details.",
                )
                body.append(filler)
            slides = body + [closing]

    return content_tree.model_copy(update={"slides": slides})
