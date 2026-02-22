"""Tests for core/studio/slides/types.py — slide type registry."""

from core.studio.slides.types import (
    ELEMENT_TYPES,
    SLIDE_TYPE_ELEMENTS,
    SLIDE_TYPES,
    get_elements_for_slide_type,
    is_valid_element_type,
    is_valid_slide_type,
)


def test_all_slide_types_defined():
    assert len(SLIDE_TYPES) == 13


def test_all_element_types_defined():
    assert len(ELEMENT_TYPES) == 11


def test_slide_type_elements_complete():
    for st in SLIDE_TYPES:
        assert st in SLIDE_TYPE_ELEMENTS, f"Missing mapping for slide type: {st}"


def test_element_types_in_mapping_are_valid():
    for st, elements in SLIDE_TYPE_ELEMENTS.items():
        for el in elements:
            assert el in ELEMENT_TYPES, f"Invalid element '{el}' in slide type '{st}'"


def test_is_valid_slide_type():
    assert is_valid_slide_type("title") is True
    assert is_valid_slide_type("content") is True
    assert is_valid_slide_type("unknown_type") is False
    assert is_valid_slide_type("") is False


def test_is_valid_element_type():
    assert is_valid_element_type("body") is True
    assert is_valid_element_type("bullet_list") is True
    assert is_valid_element_type("unknown") is False
    assert is_valid_element_type("") is False


def test_get_elements_for_slide_type_known():
    elements = get_elements_for_slide_type("title")
    assert elements == ["title", "subtitle"]


def test_get_elements_for_slide_type_unknown():
    elements = get_elements_for_slide_type("nonexistent")
    assert elements == ["title", "body"]
