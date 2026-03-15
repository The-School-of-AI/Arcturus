"""Layout repair for Forge slide exports.

When strict_layout is enabled, this module auto-fixes content that would
exceed layout density thresholds, so exports always succeed.
"""

import re
from typing import List

from core.schemas.studio_schema import Slide, SlideElement, SlidesContentTree
from core.studio.slides.validator import _PLACEHOLDER_PATTERNS

# Density thresholds (match validator.py values)
BLOCK_CHAR_LIMIT = 800
SLIDE_CHAR_LIMIT = 1600
TABLE_SLIDE_CHAR_LIMIT = 2400
TITLE_CHAR_LIMIT = 60

# Element types that contain string body text eligible for truncation
_STRING_BODY_TYPES = {"body", "takeaway", "kicker", "callout_box", "quote", "source_citation"}


def repair_layout(content_tree: SlidesContentTree) -> SlidesContentTree:
    """Repair layout density issues on an export copy of the content tree.

    Returns a new SlidesContentTree (does not mutate the input).
    """
    new_slides = []
    for slide in content_tree.slides:
        new_slide = _repair_slide(slide)
        new_slides.append(new_slide)

    return SlidesContentTree(
        deck_title=content_tree.deck_title,
        subtitle=content_tree.subtitle,
        slides=new_slides,
        metadata=content_tree.metadata,
    )


def _repair_slide(slide: Slide) -> Slide:
    """Repair a single slide's elements for layout density."""
    # Pass 1: repair individual elements
    new_elements = [_repair_element(el) for el in slide.elements]

    # Repair title if too long
    title = slide.title
    if title and len(title) > TITLE_CHAR_LIMIT:
        title = _truncate_at_word(title, TITLE_CHAR_LIMIT)

    # Pass 2: check slide-level total
    effective_limit = TABLE_SLIDE_CHAR_LIMIT if slide.slide_type == "table" else SLIDE_CHAR_LIMIT
    slide_total = _compute_slide_text_total(new_elements)

    if slide_total > effective_limit:
        new_elements = _trim_longest_element(new_elements, effective_limit)

    return Slide(
        id=slide.id,
        slide_type=slide.slide_type,
        title=title,
        elements=new_elements,
        speaker_notes=slide.speaker_notes,
        metadata=slide.metadata,
    )


def _repair_element(el: SlideElement) -> SlideElement:
    """Repair a single element for block-level density and placeholders."""
    content = el.content

    # String content: truncate + strip placeholders
    if el.type in _STRING_BODY_TYPES and isinstance(content, str):
        content = _strip_placeholders(content)
        if len(content) > BLOCK_CHAR_LIMIT:
            content = _truncate_at_sentence(content, BLOCK_CHAR_LIMIT)
        return SlideElement(id=el.id, type=el.type, content=content)

    # Bullet list: truncate individual items + trim list total
    if el.type == "bullet_list" and isinstance(content, list):
        cleaned: List[str] = []
        running = 0
        for item in content:
            item_str = str(item)
            item_str = _strip_placeholders(item_str)
            if not item_str:
                continue
            # Truncate individual oversized bullet items
            if len(item_str) > BLOCK_CHAR_LIMIT:
                item_str = _truncate_at_sentence(item_str, BLOCK_CHAR_LIMIT)
            if running + len(item_str) > BLOCK_CHAR_LIMIT and cleaned:
                break
            cleaned.append(item_str)
            running += len(item_str)
        return SlideElement(id=el.id, type=el.type, content=cleaned)

    # Title/subtitle: strip placeholders only (title length handled at slide level)
    if isinstance(content, str):
        stripped = _strip_placeholders(content)
        if stripped != content:
            return SlideElement(id=el.id, type=el.type, content=stripped)

    # Dict content (chart, table_data, stat_callout): leave as-is
    return el


def _compute_slide_text_total(elements: list[SlideElement]) -> int:
    """Sum the character length of all text in elements."""
    total = 0
    for el in elements:
        if isinstance(el.content, str):
            total += len(el.content)
        elif isinstance(el.content, list):
            total += sum(len(str(item)) for item in el.content)
    return total


def _trim_longest_element(elements: list[SlideElement], slide_limit: int) -> list[SlideElement]:
    """Trim the longest body/bullet element to bring slide total under limit."""
    # Find the longest trimmable element
    longest_idx = -1
    longest_len = 0
    for i, el in enumerate(elements):
        el_len = 0
        if el.type in _STRING_BODY_TYPES and isinstance(el.content, str):
            el_len = len(el.content)
        elif el.type == "bullet_list" and isinstance(el.content, list):
            el_len = sum(len(str(item)) for item in el.content)
        if el_len > longest_len:
            longest_len = el_len
            longest_idx = i

    if longest_idx < 0 or longest_len == 0:
        return elements

    excess = _compute_slide_text_total(elements) - slide_limit
    target_len = max(longest_len - excess, 100)  # keep at least 100 chars

    result = list(elements)
    el = elements[longest_idx]

    if el.type in _STRING_BODY_TYPES and isinstance(el.content, str):
        result[longest_idx] = SlideElement(
            id=el.id, type=el.type,
            content=_truncate_at_sentence(el.content, target_len),
        )
    elif el.type == "bullet_list" and isinstance(el.content, list):
        trimmed: List[str] = []
        running = 0
        for item in el.content:
            s = str(item)
            if running + len(s) > target_len and trimmed:
                break
            trimmed.append(s)
            running += len(s)
        result[longest_idx] = SlideElement(
            id=el.id, type=el.type, content=trimmed,
        )

    return result


def _truncate_at_sentence(text: str, limit: int) -> str:
    """Truncate text at the last sentence boundary within limit."""
    if len(text) <= limit:
        return text

    candidate = text[:limit]
    # Find last sentence-ending punctuation
    match = None
    for m in re.finditer(r'[.!?]', candidate):
        match = m
    if match and match.end() > limit // 3:
        return candidate[:match.end()].rstrip()

    # No good sentence boundary — truncate at word boundary
    return _truncate_at_word(candidate, limit)


def _truncate_at_word(text: str, limit: int) -> str:
    """Truncate text at the last word boundary within limit, append ellipsis."""
    if len(text) <= limit:
        return text
    candidate = text[:limit]
    last_space = candidate.rfind(" ")
    if last_space > limit // 3:
        return candidate[:last_space].rstrip() + "..."
    return candidate.rstrip() + "..."


def _strip_placeholders(text: str) -> str:
    """Remove placeholder text patterns from content."""
    result = text
    for pat in _PLACEHOLDER_PATTERNS:
        result = pat.sub("", result)
    return result.strip()
