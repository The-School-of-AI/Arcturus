"""Tests for core/studio/slides/themes.py — curated theme catalog."""

import re

from core.schemas.studio_schema import SlideTheme
from core.studio.slides.themes import (
    DEFAULT_THEME_ID,
    get_theme,
    get_theme_ids,
    list_themes,
)

HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_all_themes_load():
    themes = list_themes()
    assert len(themes) == 8


def test_get_theme_by_id():
    theme = get_theme("corporate-blue")
    assert theme.id == "corporate-blue"
    assert theme.name == "Corporate Blue"


def test_get_theme_default():
    theme = get_theme()
    assert theme.id == DEFAULT_THEME_ID


def test_get_theme_unknown_falls_back():
    theme = get_theme("nonexistent")
    assert theme.id == DEFAULT_THEME_ID


def test_get_theme_none_falls_back():
    theme = get_theme(None)
    assert theme.id == DEFAULT_THEME_ID


def test_theme_has_required_colors():
    for theme in list_themes():
        colors = theme.colors
        assert colors.primary
        assert colors.secondary
        assert colors.accent
        assert colors.background
        assert colors.text
        assert colors.text_light


def test_theme_colors_are_hex():
    for theme in list_themes():
        for field_name in ["primary", "secondary", "accent", "background", "text", "text_light"]:
            value = getattr(theme.colors, field_name)
            assert HEX_PATTERN.match(value), f"Theme {theme.id}.{field_name} = '{value}' is not valid hex"


def test_theme_has_fonts():
    for theme in list_themes():
        assert theme.font_heading, f"Theme {theme.id} missing font_heading"
        assert theme.font_body, f"Theme {theme.id} missing font_body"


def test_theme_ids_are_unique():
    ids = get_theme_ids()
    assert len(ids) == len(set(ids))


def test_get_theme_ids():
    ids = get_theme_ids()
    assert "corporate-blue" in ids
    assert "tech-dark" in ids
    assert len(ids) == 8


def test_theme_roundtrip_serialization():
    for theme in list_themes():
        roundtripped = SlideTheme(**theme.model_dump())
        assert roundtripped == theme
