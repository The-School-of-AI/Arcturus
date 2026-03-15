"""Tests for theme variant generation in core/studio/slides/themes.py."""

import re

import pytest

from core.studio.slides.themes import (
    _FONT_COMPAT_GROUPS,
    _THEME_FONT_GROUP,
    _check_contrast,
    generate_theme_variant,
    get_theme,
    get_theme_ids,
    list_themes,
)

HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
VARIANT_ID_PATTERN = re.compile(r"^.+--v\d{2}$")
_FLAT_FONTS = {f for pairs in _FONT_COMPAT_GROUPS.values() for pair in pairs for f in pair}


def test_generate_variant_deterministic():
    v1 = generate_theme_variant("corporate-blue", 1)
    v2 = generate_theme_variant("corporate-blue", 1)
    assert v1.id == v2.id
    assert v1.colors.primary == v2.colors.primary
    assert v1.font_heading == v2.font_heading


def test_generate_variant_different_seeds():
    v1 = generate_theme_variant("corporate-blue", 1)
    v2 = generate_theme_variant("corporate-blue", 3)
    assert v1.colors.primary != v2.colors.primary or v1.font_heading != v2.font_heading


def test_variant_id_format():
    v = generate_theme_variant("tech-dark", 2)
    assert VARIANT_ID_PATTERN.match(v.id)
    assert v.id == "tech-dark--v02"


def test_variant_has_base_theme_id():
    v = generate_theme_variant("startup-bold", 3)
    assert v.base_theme_id == "startup-bold"


def test_variant_has_variant_seed():
    v = generate_theme_variant("minimal-light", 4)
    assert v.variant_seed == 4


def test_variant_contrast_validation():
    for base_id in ["corporate-blue", "tech-dark", "minimal-light"]:
        for seed in range(1, 7):
            v = generate_theme_variant(base_id, seed)
            assert _check_contrast(v.colors.text, v.colors.background), (
                f"Contrast fail: {v.id} text={v.colors.text} bg={v.colors.background}"
            )


def test_variant_contrast_retry():
    # tech-dark has dark background — text should be light enough
    for seed in range(1, 7):
        v = generate_theme_variant("tech-dark", seed)
        assert _check_contrast(v.colors.text, v.colors.background)


def test_variant_hex_colors_valid():
    v = generate_theme_variant("corporate-blue", 1)
    for field in ["primary", "secondary", "accent", "background", "text", "text_light"]:
        val = getattr(v.colors, field)
        assert HEX_PATTERN.match(val), f"{field}={val} is not valid hex"


def test_variant_fonts_from_allowlist():
    """Variant fonts come from the mood-compatible group for each theme."""
    # One representative theme per mood group
    representatives = {
        "formal": "corporate-blue",
        "modern": "minimal-light",
        "warm": "nature-green",
        "bold": "startup-bold",
    }
    for group_name, theme_id in representatives.items():
        group_fonts = {f for pair in _FONT_COMPAT_GROUPS[group_name] for f in pair}
        for seed in range(1, 7):
            v = generate_theme_variant(theme_id, seed)
            assert v.font_heading in group_fonts, (
                f"font_heading={v.font_heading} not in {group_name} group for {theme_id}"
            )
            assert v.font_body in group_fonts, (
                f"font_body={v.font_body} not in {group_name} group for {theme_id}"
            )


def test_variant_fonts_in_flat_allowlist():
    """All variant fonts across all themes are in the global flat allowlist."""
    for seed in range(1, 7):
        v = generate_theme_variant("corporate-blue", seed)
        assert v.font_heading in _FLAT_FONTS, f"font_heading={v.font_heading} not in allowlist"
        assert v.font_body in _FLAT_FONTS, f"font_body={v.font_body} not in allowlist"


def test_all_themes_have_font_group():
    """Every registered theme has a mood group assignment."""
    base_ids = get_theme_ids(include_variants=False)
    for base_id in base_ids:
        assert base_id in _THEME_FONT_GROUP, f"{base_id} missing from _THEME_FONT_GROUP"


def test_variant_background_style_valid():
    for seed in range(1, 7):
        v = generate_theme_variant("corporate-blue", seed)
        assert v.background_style in ("solid", "gradient", "subtle_pattern")


def test_list_themes_with_variants_count():
    themes = list_themes(include_variants=True)
    assert len(themes) >= 112


def test_list_themes_base_only():
    themes = list_themes(include_variants=False)
    assert len(themes) == 16


def test_list_themes_filter_by_base_id():
    themes = list_themes(base_id="tech-dark")
    assert len(themes) == 7  # 1 base + 6 variants
    assert themes[0].id == "tech-dark"
    for t in themes[1:]:
        assert t.base_theme_id == "tech-dark"


def test_unknown_base_raises_error():
    with pytest.raises(ValueError, match="Unknown base theme"):
        generate_theme_variant("nonexistent", 1)
