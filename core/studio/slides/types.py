"""Slide type and element type constants for the Forge slides pipeline."""

# 10 supported slide types
SLIDE_TYPES = {
    "title",
    "content",
    "two_column",
    "comparison",
    "timeline",
    "chart",
    "image_text",
    "quote",
    "code",
    "team",
}

# 8 supported element types
ELEMENT_TYPES = {
    "title",
    "subtitle",
    "body",
    "bullet_list",
    "image",
    "chart",
    "code",
    "quote",
}

# Slide-type-to-element mapping
SLIDE_TYPE_ELEMENTS = {
    "title":       ["title", "subtitle"],
    "content":     ["title", "body", "bullet_list"],
    "two_column":  ["title", "body", "bullet_list"],
    "comparison":  ["title", "body", "bullet_list"],
    "timeline":    ["title", "body", "bullet_list"],
    "chart":       ["title", "chart", "body"],
    "image_text":  ["title", "image", "body"],
    "quote":       ["quote", "body"],
    "code":        ["title", "code", "body"],
    "team":        ["title", "body", "bullet_list"],
}

# Narrative arc pattern for planning slide sequences
NARRATIVE_ARC = [
    "title",
    "content",
    "content",
    "two_column",
    "timeline",
    "chart",
    "quote",
    "content",
    "team",
    "title",
]


def is_valid_slide_type(slide_type: str) -> bool:
    return slide_type in SLIDE_TYPES


def is_valid_element_type(element_type: str) -> bool:
    return element_type in ELEMENT_TYPES


def get_elements_for_slide_type(slide_type: str) -> list[str]:
    return SLIDE_TYPE_ELEMENTS.get(slide_type, ["title", "body"])
