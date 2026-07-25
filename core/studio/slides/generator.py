"""Deterministic slide sequence planner for Forge slides."""

import hashlib
import logging
import random
import re
from typing import Any, Dict, List

from core.studio.slides.types import NARRATIVE_ARC, SLIDE_TYPE_ELEMENTS

logger = logging.getLogger(__name__)

# Structural slide types that are auto-generated and do NOT count
# toward the user's requested slide_count.
_STRUCTURAL_TYPES = frozenset({"title", "section_divider"})

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

    - Resolves slide_count from parameters/prompt (content slides only)
    - Stores resolved slide_count in outline.parameters
    - Filters out structural slide items (title, section_divider)
    - Trims outline items if LLM generated too many
    """
    params = parameters or (outline.parameters if hasattr(outline, "parameters") else {}) or {}

    resolved = resolve_slide_count(params, user_prompt)

    # Store resolved slide_count in outline parameters
    if hasattr(outline, "parameters") and outline.parameters is not None:
        outline.parameters["slide_count"] = resolved
    elif hasattr(outline, "parameters"):
        outline.parameters = {"slide_count": resolved}

    # Filter out structural slide items (opening/closing title, section_divider).
    # These are auto-generated and should not appear in the outline.
    if hasattr(outline, "items"):
        filtered = []
        for item in outline.items:
            desc = (getattr(item, "description", None) or "").lower()
            is_structural = False
            for stype in _STRUCTURAL_TYPES:
                if f"slide_type: {stype}" in desc or f"slide_type:{stype}" in desc:
                    is_structural = True
                    break
            if not is_structural:
                filtered.append(item)
        if filtered:  # Only replace if filtering wouldn't remove everything
            outline.items = filtered

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

    ``slide_count`` refers to **content** slides only.  An opening title slide,
    a closing title slide, and (for larger decks) section dividers are added
    automatically and do **not** count toward ``slide_count``.

    Returns a list of dicts with slide_type, suggested_elements, position.
    """
    rng = random.Random(seed)
    arc = narrative_arc or NARRATIVE_ARC

    # Extract content (non-structural) types from the narrative arc
    content_arc = [t for t in arc if t not in _STRUCTURAL_TYPES]

    # Sample content slide types
    if slide_count <= len(content_arc):
        indices = sorted(rng.sample(range(len(content_arc)), slide_count))
        body_types = [content_arc[i] for i in indices]
    else:
        # Use all content types, then repeat body types to fill
        body_types = list(content_arc)
        extra_pool = ["content", "two_column", "comparison", "timeline", "chart"]
        while len(body_types) < slide_count:
            insert_pos = rng.randint(1, max(1, len(body_types) - 1))
            body_types.insert(insert_pos, rng.choice(extra_pool))

    # Insert section dividers for larger decks (8+ content slides)
    if slide_count >= 8:
        divider_count = 1 if slide_count < 12 else 2
        step = len(body_types) // (divider_count + 1)
        for i in range(divider_count):
            pos = step * (i + 1) + i  # +i compensates for previously inserted dividers
            body_types.insert(pos, "section_divider")

    # Build full sequence: opening title + body + closing title
    sequence = ["title"] + body_types + ["title"]

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


# ---------------------------------------------------------------------------
# Pre-validation normalization for raw LLM slide output
# ---------------------------------------------------------------------------

# Fields that the LLM sometimes uses instead of "content"
_CONTENT_ALIASES = ("text_content", "text", "value", "body", "description")

# Fields that the LLM sometimes uses instead of "type"
_TYPE_ALIASES = ("element_type", "kind", "role")


def normalize_slides_content_tree_raw(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize raw LLM JSON for slides before Pydantic validation.

    Fixes common LLM deviations:
    - Missing ``id`` on slides and elements (auto-generates them)
    - Wrong field names: ``text_content`` → ``content``, etc.
    - Dict-for-string coercion on top-level and element fields
    - Missing ``elements`` list (creates empty list)
    - Missing ``slide_type`` (defaults to "content")

    Mutates ``parsed`` in-place and returns it.
    """
    # --- Top-level string coercion ---
    for key in ("deck_title", "subtitle"):
        if isinstance(parsed.get(key), dict):
            parsed[key] = _extract_text(parsed[key]) or ""

    slides = parsed.get("slides")
    if not isinstance(slides, list):
        return parsed

    for si, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue

        # Auto-generate slide id
        if "id" not in slide or not slide["id"]:
            slide["id"] = f"s{si + 1}"

        # Default slide_type
        if "slide_type" not in slide or not slide["slide_type"]:
            slide["slide_type"] = "content"

        # Coerce slide-level string fields from dicts
        for key in ("title", "speaker_notes"):
            if isinstance(slide.get(key), dict):
                slide[key] = _extract_text(slide[key]) or ""

        # Ensure elements is a list
        if "elements" not in slide or not isinstance(slide.get("elements"), list):
            slide["elements"] = []

        for ei, el in enumerate(slide["elements"]):
            if not isinstance(el, dict):
                continue

            # Auto-generate element id
            if "id" not in el or not el["id"]:
                el["id"] = f"s{si + 1}_e{ei + 1}"

            # Fix type aliases
            if "type" not in el or not el["type"]:
                for alias in _TYPE_ALIASES:
                    if alias in el:
                        el["type"] = el.pop(alias)
                        break
                else:
                    el["type"] = "body"  # safe default

            # Fix content aliases: text_content, text, value, body → content
            if "content" not in el:
                for alias in _CONTENT_ALIASES:
                    if alias in el:
                        el["content"] = el.pop(alias)
                        break

            # Coerce id/type from dicts
            for key in ("id", "type"):
                if isinstance(el.get(key), dict):
                    el[key] = _extract_text(el[key]) or el[key]

    logger.debug("Normalized slides raw content tree (%d slides)", len(slides))
    return parsed


def _extract_text(d: dict) -> str | None:
    """Extract a string value from a dict the LLM created instead of a string.

    Tries common keys: text, value, content, title, name, label, body.
    """
    for key in ("text", "value", "content", "title", "name", "label", "body"):
        v = d.get(key)
        if isinstance(v, str) and v:
            return v
    # Last resort: first string value
    for v in d.values():
        if isinstance(v, str) and v:
            return v
    return None


def enforce_slide_count(
    content_tree: "SlidesContentTree",
    target_count: int | None = None,
) -> "SlidesContentTree":
    """Enforce slide count on a content tree.

    When target_count is provided: trim/pad so that the number of **content**
    slides (non-structural: not title or section_divider) equals exactly
    target_count (clamped to [MIN_SLIDES, MAX_SLIDES]).  Structural slides
    (opening title, closing title, section dividers) are preserved and not
    counted.

    When target_count is None: only enforce the global [MIN_SLIDES, MAX_SLIDES]
    range on total slide count (preserves legacy behavior for patch_apply.py
    edits).

    Returns a new SlidesContentTree (does not mutate the input).
    """
    slides = list(content_tree.slides)
    if len(slides) == 0:
        raise ValueError("Cannot enforce slide count on empty slides list")

    # Legacy path (patch edits): enforce global range on total slides
    if target_count is None:
        if len(slides) > MAX_SLIDES:
            opening = slides[0]
            closing = slides[-1]
            body = slides[1:-1]
            body = body[: MAX_SLIDES - 2]
            slides = [opening] + body + [closing]

        if len(slides) < MIN_SLIDES:
            from core.schemas.studio_schema import Slide, SlideElement
            if len(slides) == 1:
                opening = slides[0]
                padded = [opening]
                filler_count = MIN_SLIDES - 1
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
                filler_count = MIN_SLIDES - len(slides)
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

    # Content-aware path: count only non-structural slides
    target = clamp_slide_count(target_count)

    opening = slides[0]
    closing = slides[-1]
    body = slides[1:-1]

    content_count = sum(1 for s in body if s.slide_type not in _STRUCTURAL_TYPES)

    # Trim: remove excess content slides from the end, preserving structural
    if content_count > target:
        excess = content_count - target
        new_body = []
        removed = 0
        for s in reversed(body):
            if removed < excess and s.slide_type not in _STRUCTURAL_TYPES:
                removed += 1
                continue
            new_body.insert(0, s)
        body = new_body

    # Pad: add filler content slides before closing
    if content_count < target:
        from core.schemas.studio_schema import Slide, SlideElement
        deficit = target - content_count
        for i in range(deficit):
            tmpl = _FILLER_TEMPLATES[(content_count + i) % len(_FILLER_TEMPLATES)]
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

    slides = [opening] + body + [closing]
    return content_tree.model_copy(update={"slides": slides})


# ── Per-slide visual style normalization ────────────────────────────────────


def _migrate_visual_style(vs: dict) -> dict:
    """Convert old enum-based visual_style to new slide_style format."""
    result: dict = {}
    bg_variant = vs.get("bg_variant", "solid")
    if bg_variant == "gradient":
        result["background"] = {"value": "linear-gradient(135deg, var(--theme-bg), var(--theme-primary-8))"}
    elif bg_variant == "accent_wash":
        result["background"] = {"value": "var(--theme-accent-wash)"}
    elif bg_variant == "dark_invert":
        result["background"] = {"value": "var(--theme-title-bg)"}
    # solid = no override, use theme default

    card_style = vs.get("card_style")
    if card_style == "glass":
        result["card"] = {
            "background": "rgba(255,255,255,0.06)",
            "border": "1px solid rgba(255,255,255,0.1)",
            "backdropFilter": "blur(8px)",
        }
    elif card_style == "elevated":
        result["card"] = {"boxShadow": "0 4px 12px rgba(0,0,0,0.1)"}
    elif card_style == "outlined":
        result["card"] = {"border": "1px solid rgba(0,0,0,0.12)", "background": "transparent"}

    return result


def normalize_visual_styles(content_tree: "SlidesContentTree") -> "SlidesContentTree":
    """Ensure every slide has a slide_style in metadata.

    Migrates old visual_style format to slide_style if present.
    No aesthetic guardrails — LLM has full creative control.
    Only validates structural correctness.
    """
    slides = list(content_tree.slides)
    if not slides:
        return content_tree

    for slide in slides:
        meta = dict(slide.metadata or {})

        # Migration: if old visual_style exists but no slide_style, convert
        if "visual_style" in meta and "slide_style" not in meta:
            meta["slide_style"] = _migrate_visual_style(meta.pop("visual_style"))

        # Ensure slide_style exists as a dict
        if not isinstance(meta.get("slide_style"), dict):
            meta["slide_style"] = {}

        slide.metadata = meta

    return content_tree.model_copy(update={"slides": slides})
