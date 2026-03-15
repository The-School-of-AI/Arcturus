"""Curated theme catalog for Forge slides."""

import colorsys
import random

from core.schemas.studio_schema import SlideTheme, SlideThemeColors

_THEMES: dict[str, SlideTheme] = {}


def _register(theme: SlideTheme) -> None:
    _THEMES[theme.id] = theme


# === Office-Safe Font Pairs ===

_FONT_PAIRS = [
    ("Calibri", "Corbel"),
    ("Georgia", "Arial"),
    ("Cambria", "Calibri"),
    ("Cambria", "Corbel"),
    ("Garamond", "Calibri"),
    ("Constantia", "Candara"),
    ("Century Gothic", "Corbel"),
    ("Book Antiqua", "Tahoma"),
]

# === Mood-Based Font Compatibility Groups ===

_FONT_COMPAT_GROUPS = {
    "formal": [
        ("Cambria", "Calibri"),
        ("Garamond", "Calibri"),
        ("Constantia", "Candara"),
        ("Book Antiqua", "Tahoma"),
    ],
    "modern": [
        ("Calibri", "Corbel"),
        ("Cambria", "Calibri"),
        ("Cambria", "Corbel"),
    ],
    "warm": [
        ("Georgia", "Candara"),
        ("Constantia", "Candara"),
        ("Cambria", "Calibri"),
    ],
    "bold": [
        ("Century Gothic", "Corbel"),
        ("Calibri", "Corbel"),
        ("Cambria", "Corbel"),
    ],
}

_THEME_FONT_GROUP = {
    "corporate-blue": "formal",
    "finance-navy": "formal",
    "legal-burgundy": "formal",
    "executive-charcoal": "formal",
    "minimal-light": "modern",
    "monochrome-pro": "modern",
    "product-indigo": "modern",
    "healthcare-teal": "modern",
    "nature-green": "warm",
    "warm-terracotta": "warm",
    "education-purple": "warm",
    "sunset-amber": "warm",
    "startup-bold": "bold",
    "tech-dark": "bold",
    "creative-coral": "bold",
    "ocean-gradient": "bold",
}

# === Phase 2 Base Themes (8) ===

_register(SlideTheme(
    id="corporate-blue",
    name="Corporate Blue",
    colors=SlideThemeColors(
        primary="#1E3A5F",
        secondary="#4A7FB5",
        accent="#A87A22",
        background="#F5F6F8",
        text="#1C2D3F",
        text_light="#7B8FA3",
        title_background="#152C47",
    ),
    font_heading="Calibri",
    font_body="Corbel",
    description="Clean, professional theme suitable for enterprise presentations",
))

_register(SlideTheme(
    id="startup-bold",
    name="Startup Bold",
    colors=SlideThemeColors(
        primary="#D95B3F",
        secondary="#2B6B7F",
        accent="#2D8A5A",
        background="#FAF8F5",
        text="#2A2035",
        text_light="#8A7F91",
        title_background="#1F4F5F",
    ),
    font_heading="Century Gothic",
    font_body="Corbel",
    description="Energetic theme for startup pitch decks and product launches",
))

_register(SlideTheme(
    id="minimal-light",
    name="Minimal Light",
    colors=SlideThemeColors(
        primary="#363636",
        secondary="#7A7A7A",
        accent="#1A8A94",
        background="#F9F9F7",
        text="#262626",
        text_light="#858580",
        title_background="#2A2A2A",
    ),
    font_heading="Calibri",
    font_body="Corbel",
    description="Minimalist theme with clean typography and subtle accents",
))

_register(SlideTheme(
    id="nature-green",
    name="Nature Green",
    colors=SlideThemeColors(
        primary="#3D7A47",
        secondary="#4D8A55",
        accent="#A07028",
        background="#F2F5EE",
        text="#2A4A2E",
        text_light="#7B9473",
        title_background="#2C5A34",
    ),
    font_heading="Georgia",
    font_body="Candara",
    description="Organic theme for sustainability, environment, and nature topics",
))

_register(SlideTheme(
    id="tech-dark",
    name="Tech Dark",
    colors=SlideThemeColors(
        primary="#4DC9E6",
        secondary="#9B7AE8",
        accent="#E8607A",
        background="#161619",
        text="#D8D8DC",
        text_light="#9090A0",
        title_background="#0E0E11",
    ),
    font_heading="Cambria",
    font_body="Calibri",
    description="Dark mode theme for technology and developer-focused decks",
))

_register(SlideTheme(
    id="warm-terracotta",
    name="Warm Terracotta",
    colors=SlideThemeColors(
        primary="#984830",
        secondary="#9A7048",
        accent="#4A7548",
        background="#FBF6F0",
        text="#3A271F",
        text_light="#9C8574",
        title_background="#5A2B1A",
    ),
    font_heading="Constantia",
    font_body="Candara",
    description="Warm, earthy theme for creative and lifestyle presentations",
))

_register(SlideTheme(
    id="ocean-gradient",
    name="Ocean Gradient",
    colors=SlideThemeColors(
        primary="#1B6E8C",
        secondary="#3A8AA8",
        accent="#B07C20",
        background="#F5F7F9",
        text="#14475B",
        text_light="#5A8A9A",
        title_background="#134058",
    ),
    font_heading="Cambria",
    font_body="Corbel",
    description="Calming ocean-inspired theme with gradient accents",
))

_register(SlideTheme(
    id="monochrome-pro",
    name="Monochrome Pro",
    colors=SlideThemeColors(
        primary="#1A1A1A",
        secondary="#525252",
        accent="#C44A3A",
        background="#FCFCFC",
        text="#242424",
        text_light="#858585",
        title_background="#141414",
    ),
    font_heading="Calibri",
    font_body="Calibri",
    description="High-contrast black and white theme with red accent",
))

# === Phase 3 Base Themes (8 new) ===

_register(SlideTheme(
    id="finance-navy",
    name="Finance Navy",
    colors=SlideThemeColors(
        primary="#0E2240",
        secondary="#345C8A",
        accent="#8A7520",
        background="#F7F7F5",
        text="#0C1C35",
        text_light="#7B8B9E",
        title_background="#091830",
    ),
    font_heading="Garamond",
    font_body="Calibri",
    description="Conservative theme for financial reports and investor decks",
))

_register(SlideTheme(
    id="healthcare-teal",
    name="Healthcare Teal",
    colors=SlideThemeColors(
        primary="#0F6F82",
        secondary="#3A8A80",
        accent="#D16B47",
        background="#F5F8F8",
        text="#0C4553",
        text_light="#5A8890",
        title_background="#0A4D5C",
    ),
    font_heading="Cambria",
    font_body="Calibri",
    description="Clean theme for healthcare and life sciences presentations",
))

_register(SlideTheme(
    id="education-purple",
    name="Education Purple",
    colors=SlideThemeColors(
        primary="#4E2D7A",
        secondary="#8B72B8",
        accent="#C06030",
        background="#F5F2F8",
        text="#2D1A52",
        text_light="#897AAD",
        title_background="#3A2060",
    ),
    font_heading="Constantia",
    font_body="Candara",
    description="Academic theme for education and research presentations",
))

_register(SlideTheme(
    id="executive-charcoal",
    name="Executive Charcoal",
    colors=SlideThemeColors(
        primary="#3A3A3A",
        secondary="#686868",
        accent="#9A7A10",
        background="#F8F7F5",
        text="#282828",
        text_light="#7A7670",
        title_background="#2A2A28",
    ),
    font_heading="Garamond",
    font_body="Calibri",
    description="Refined theme for C-suite and board presentations",
))

_register(SlideTheme(
    id="creative-coral",
    name="Creative Coral",
    colors=SlideThemeColors(
        primary="#C04A40",
        secondary="#C45A70",
        accent="#1A8874",
        background="#FBF4F2",
        text="#3B2520",
        text_light="#A08278",
        title_background="#7A2B1E",
    ),
    font_heading="Century Gothic",
    font_body="Corbel",
    description="Bold theme for creative agencies and design showcases",
))

_register(SlideTheme(
    id="legal-burgundy",
    name="Legal Burgundy",
    colors=SlideThemeColors(
        primary="#602435",
        secondary="#8C4358",
        accent="#8A7020",
        background="#FAF7F3",
        text="#381420",
        text_light="#957B75",
        title_background="#451A28",
    ),
    font_heading="Book Antiqua",
    font_body="Tahoma",
    description="Formal theme for legal and compliance presentations",
))

_register(SlideTheme(
    id="product-indigo",
    name="Product Indigo",
    colors=SlideThemeColors(
        primary="#3C4DA8",
        secondary="#7480BD",
        accent="#D05530",
        background="#F5F5F8",
        text="#1E2360",
        text_light="#6A72A8",
        title_background="#2E3A7A",
    ),
    font_heading="Century Gothic",
    font_body="Calibri",
    description="Modern theme for product launches and roadmap decks",
))

_register(SlideTheme(
    id="sunset-amber",
    name="Sunset Amber",
    colors=SlideThemeColors(
        primary="#A86808",
        secondary="#A07830",
        accent="#5465A8",
        background="#FBF8F0",
        text="#4A3008",
        text_light="#9A8B6E",
        title_background="#8B4E10",
    ),
    font_heading="Cambria",
    font_body="Calibri",
    description="Warm theme for lifestyle and community presentations",
))

DEFAULT_THEME_ID = "corporate-blue"

# === HSL Color Utilities ===

_VARIANTS_PER_BASE = 6
_BACKGROUND_STYLES = ["solid", "gradient", "solid", "gradient", "solid", "solid"]


def _hex_to_hls(hex_color: str) -> tuple[float, float, float]:
    """Convert hex color to HLS (hue, lightness, saturation)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16) / 255, int(hex_color[2:4], 16) / 255, int(hex_color[4:6], 16) / 255
    return colorsys.rgb_to_hls(r, g, b)


def _hls_to_hex(h: float, l: float, s: float) -> str:
    """Convert HLS to hex color string."""
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return f"#{max(0, min(255, int(r * 255 + 0.5))):02X}{max(0, min(255, int(g * 255 + 0.5))):02X}{max(0, min(255, int(b * 255 + 0.5))):02X}"


def _hue_rotate(hex_color: str, degrees: float) -> str:
    """Rotate hue of a hex color by the given degrees."""
    h, l, s = _hex_to_hls(hex_color)
    h = (h + degrees / 360.0) % 1.0
    return _hls_to_hex(h, l, s)


def _relative_luminance(hex_color: str) -> float:
    """Calculate relative luminance per WCAG 2.1."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16) / 255, int(hex_color[2:4], 16) / 255, int(hex_color[4:6], 16) / 255

    def linearize(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _check_contrast(text_hex: str, bg_hex: str) -> bool:
    """WCAG AA check: luminance ratio >= 4.5:1 for text on background."""
    l1 = _relative_luminance(text_hex)
    l2 = _relative_luminance(bg_hex)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    ratio = (lighter + 0.05) / (darker + 0.05)
    return ratio >= 4.5


def _fix_contrast(text_hex: str, bg_hex: str) -> str:
    """Deterministically adjust text color lightness to meet WCAG AA."""
    if _check_contrast(text_hex, bg_hex):
        return text_hex
    bg_lum = _relative_luminance(bg_hex)
    h, l, s = _hex_to_hls(text_hex)
    # If background is dark, lighten text; if light, darken text
    direction = 0.10 if bg_lum < 0.5 else -0.10
    for _ in range(3):
        l = max(0.0, min(1.0, l + direction))
        candidate = _hls_to_hex(h, l, s)
        if _check_contrast(candidate, bg_hex):
            return candidate
    # Final fallback: black or white
    return "#FFFFFF" if bg_lum < 0.5 else "#000000"


def _blend_color(color_hex: str, bg_hex: str, ratio: float) -> str:
    """Blend color_hex toward bg_hex by ratio (0.0 = all bg, 1.0 = all color)."""
    c = color_hex.lstrip("#")
    b = bg_hex.lstrip("#")
    cr, cg, cb = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    br, bg_r, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
    r = int(cr * ratio + br * (1 - ratio) + 0.5)
    g = int(cg * ratio + bg_r * (1 - ratio) + 0.5)
    bl = int(cb * ratio + bb * (1 - ratio) + 0.5)
    return f"#{max(0, min(255, r)):02X}{max(0, min(255, g)):02X}{max(0, min(255, bl)):02X}"


def _lightness_shift(hex_color: str, delta: float) -> str:
    """Shift lightness of a hex color by delta (-1.0 to 1.0)."""
    h, l, s = _hex_to_hls(hex_color)
    l = max(0.0, min(1.0, l + delta))
    return _hls_to_hex(h, l, s)


def _saturation_shift(hex_color: str, delta: float) -> str:
    """Shift saturation of a hex color by delta (-1.0 to 1.0)."""
    h, l, s = _hex_to_hls(hex_color)
    s = max(0.0, min(1.0, s + delta))
    return _hls_to_hex(h, l, s)


def _tint_background(base_bg: str, tint_source: str, strength: float = 0.06) -> str:
    """Subtly tint a background color toward a source hue."""
    return _blend_color(tint_source, base_bg, strength)


# === Variant Generation ===

_VARIANT_STRATEGIES = ["hue_shift", "tonal", "temperature"]


def generate_theme_variant(base_id: str, variant_seed: int) -> SlideTheme:
    """Generate a deterministic theme variant from a base theme.

    Returns a new SlideTheme with id="{base_id}--v{NN}".
    Raises ValueError if base_id is not a registered base theme.

    Uses three strategies (deterministic via seeded RNG):
    - hue_shift: small hue rotation (5-12°)
    - tonal: lightness/saturation adjustment, same hue family
    - temperature: warm/cool temperature shift via small hue nudge
    """
    if base_id not in _THEMES:
        raise ValueError(f"Unknown base theme: {base_id}")
    base = _THEMES[base_id]

    rng = random.Random(variant_seed)
    strategy = _VARIANT_STRATEGIES[variant_seed % len(_VARIANT_STRATEGIES)]

    if strategy == "hue_shift":
        offset = rng.choice([5, -5, 8, -8, 10, -10, 12, -12])
        new_primary = _hue_rotate(base.colors.primary, offset)
        new_secondary = _hue_rotate(base.colors.secondary, offset)
        # Accent: small rotation in opposite direction
        accent_offset = rng.choice([-5, -8, -10, 5, 8, 10])
        new_accent = _hue_rotate(base.colors.accent, accent_offset)
    elif strategy == "tonal":
        l_delta = rng.choice([-0.08, -0.05, 0.05, 0.08])
        s_delta = rng.choice([-0.10, -0.06, 0.06, 0.10])
        new_primary = _saturation_shift(_lightness_shift(base.colors.primary, l_delta), s_delta)
        new_secondary = _saturation_shift(_lightness_shift(base.colors.secondary, l_delta * 0.5), s_delta * 0.5)
        new_accent = _saturation_shift(base.colors.accent, rng.choice([-0.08, 0.08]))
    else:  # temperature
        temp_offset = rng.choice([6, -6, 10, -10])
        new_primary = _hue_rotate(base.colors.primary, temp_offset)
        new_secondary = _hue_rotate(base.colors.secondary, temp_offset * 0.7)
        new_accent = _hue_rotate(base.colors.accent, -temp_offset * 0.5)

    # Preserve base theme's text colors instead of resetting to generic grays
    new_text = base.colors.text
    new_text_light = base.colors.text_light

    # Subtle background tinting from new primary
    new_background = _tint_background(base.colors.background, new_primary, strength=0.04)

    # Contrast validation and fix
    new_text = _fix_contrast(new_text, new_background)
    new_text_light = _fix_contrast(new_text_light, new_background)

    # Font pairing: cycle through mood-compatible group for this theme
    group_name = _THEME_FONT_GROUP.get(base_id, "modern")
    group_pairs = _FONT_COMPAT_GROUPS[group_name]
    font_pair = group_pairs[variant_seed % len(group_pairs)]

    # Background style
    bg_style = _BACKGROUND_STYLES[(variant_seed - 1) % len(_BACKGROUND_STYLES)]

    # Carry over and adjust title_background
    new_title_bg = None
    if base.colors.title_background:
        if strategy == "hue_shift":
            new_title_bg = _hue_rotate(base.colors.title_background, offset)
        elif strategy == "tonal":
            new_title_bg = _lightness_shift(base.colors.title_background, l_delta * 0.5)
        else:
            new_title_bg = _hue_rotate(base.colors.title_background, temp_offset)

    nn = f"{variant_seed:02d}"
    return SlideTheme(
        id=f"{base_id}--v{nn}",
        name=f"{base.name} Variant {nn}",
        colors=SlideThemeColors(
            primary=new_primary,
            secondary=new_secondary,
            accent=new_accent,
            background=new_background,
            text=new_text,
            text_light=new_text_light,
            title_background=new_title_bg,
        ),
        font_heading=font_pair[0],
        font_body=font_pair[1],
        description=f"Variant {nn} of {base.name}",
        base_theme_id=base_id,
        variant_seed=variant_seed,
        background_style=bg_style,
    )


# === Public API ===

def get_theme(theme_id: str | None = None) -> SlideTheme:
    """Resolve theme by ID — checks bases first, then generates variant on demand."""
    if theme_id is None:
        return _THEMES[DEFAULT_THEME_ID]
    if theme_id in _THEMES:
        return _THEMES[theme_id]
    # Parse variant suffix: {base_id}--v{NN}
    if "--v" in theme_id:
        parts = theme_id.rsplit("--v", 1)
        if len(parts) == 2:
            base_id, nn_str = parts
            try:
                nn = int(nn_str)
                if base_id in _THEMES and 1 <= nn <= _VARIANTS_PER_BASE:
                    return generate_theme_variant(base_id, nn)
            except ValueError:
                pass
    return _THEMES[DEFAULT_THEME_ID]


def list_themes(
    include_variants: bool = False,
    base_id: str | None = None,
    limit: int | None = None,
) -> list[SlideTheme]:
    """Return available themes.

    include_variants=False (default): return only base themes.
    include_variants=True: return bases + all generated variants.
    base_id: when provided, returns the base theme + all its variants.
    limit: cap the number of returned themes.
    """
    if base_id is not None:
        if base_id not in _THEMES:
            return []
        result = [_THEMES[base_id]]
        for seed in range(1, _VARIANTS_PER_BASE + 1):
            result.append(generate_theme_variant(base_id, seed))
        if limit is not None:
            result = result[:limit]
        return result

    result = list(_THEMES.values())
    if include_variants:
        for tid in list(_THEMES.keys()):
            for seed in range(1, _VARIANTS_PER_BASE + 1):
                result.append(generate_theme_variant(tid, seed))
    if limit is not None:
        result = result[:limit]
    return result


def get_theme_ids(include_variants: bool = False) -> list[str]:
    """Return all available theme IDs."""
    ids = list(_THEMES.keys())
    if include_variants:
        for tid in list(_THEMES.keys()):
            for seed in range(1, _VARIANTS_PER_BASE + 1):
                ids.append(f"{tid}--v{seed:02d}")
    return ids
