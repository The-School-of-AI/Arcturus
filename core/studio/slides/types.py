"""Slide type and element type constants for the Forge slides pipeline."""

# 13 supported slide types
SLIDE_TYPES = {
    "title",
    "content",
    "two_column",
    "comparison",
    "timeline",
    "chart",
    "image_text",
    "image_full",
    "quote",
    "code",
    "team",
    "stat",
    "section_divider",
}

# 11 supported element types
ELEMENT_TYPES = {
    "title",
    "subtitle",
    "kicker",
    "takeaway",
    "body",
    "bullet_list",
    "image",
    "chart",
    "code",
    "quote",
    "stat_callout",
}

# Slide-type-to-element mapping
SLIDE_TYPE_ELEMENTS = {
    "title":       ["title", "subtitle"],
    "content":     ["kicker", "title", "body", "bullet_list", "takeaway"],
    "two_column":  ["kicker", "title", "body", "bullet_list", "takeaway"],
    "comparison":  ["kicker", "title", "body", "bullet_list", "takeaway"],
    "timeline":    ["kicker", "title", "body", "bullet_list", "takeaway"],
    "chart":       ["kicker", "title", "chart", "body", "takeaway"],
    "image_text":  ["title", "image", "body"],
    "image_full":  ["title", "image", "body"],
    "quote":       ["quote", "body"],
    "code":        ["title", "code", "body"],
    "team":        ["title", "body", "bullet_list"],
    "stat":        ["kicker", "title", "stat_callout", "body", "takeaway"],
    "section_divider": ["title", "subtitle"],
}

# Narrative arc pattern — varied with no consecutive repeats
NARRATIVE_ARC = [
    "title",
    "content",
    "stat",
    "section_divider",
    "two_column",
    "timeline",
    "image_text",
    "section_divider",
    "chart",
    "quote",
    "content",
    "title",
]


def is_valid_slide_type(slide_type: str) -> bool:
    return slide_type in SLIDE_TYPES


def is_valid_element_type(element_type: str) -> bool:
    return element_type in ELEMENT_TYPES


def get_elements_for_slide_type(slide_type: str) -> list[str]:
    return SLIDE_TYPE_ELEMENTS.get(slide_type, ["title", "body"])
