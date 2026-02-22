"""Curated theme catalog for Forge slides."""

import colorsys
import random

from core.schemas.studio_schema import SlideTheme, SlideThemeColors

_THEMES: dict[str, SlideTheme] = {}


def _register(theme: SlideTheme) -> None:
    _THEMES[theme.id] = theme


# === Office-Safe Font Pairs ===

_FONT_PAIRS = [
    ("Calibri", "Calibri Light"),
    ("Georgia", "Arial"),
    ("Georgia", "Verdana"),
    ("Cambria", "Corbel"),
    ("Garamond", "Trebuchet MS"),
    ("Constantia", "Candara"),
    ("Century Gothic", "Calibri Light"),
    ("Book Antiqua", "Tahoma"),
]

# === Phase 2 Base Themes (8) ===

_register(SlideTheme(
    id="corporate-blue",
    name="Corporate Blue",
    colors=SlideThemeColors(
        primary="#1B365D",
        secondary="#4A90D9",
        accent="#F5A623",
        background="#FFFFFF",
        text="#1B365D",
        text_light="#6B7B8D",
        title_background="#1B365D",
    ),
    font_heading="Calibri",
    font_body="Calibri Light",
    description="Clean, professional theme suitable for enterprise presentations",
))

_register(SlideTheme(
    id="startup-bold",
    name="Startup Bold",
    colors=SlideThemeColors(
        primary="#FF6B35",
        secondary="#004E64",
        accent="#25A18E",
        background="#F7F7F7",
        text="#1A1A2E",
        text_light="#6C757D",
        title_background="#004E64",
    ),
    font_heading="Century Gothic",
    font_body="Calibri Light",
    description="Energetic theme for startup pitch decks and product launches",
))

_register(SlideTheme(
    id="minimal-light",
    name="Minimal Light",
    colors=SlideThemeColors(
        primary="#2D2D2D",
        secondary="#757575",
        accent="#00BCD4",
        background="#FAFAFA",
        text="#212121",
        text_light="#9E9E9E",
        title_background="#2D2D2D",
    ),
    font_heading="Arial",
    font_body="Calibri Light",
    description="Minimalist theme with clean typography and subtle accents",
))

_register(SlideTheme(
    id="nature-green",
    name="Nature Green",
    colors=SlideThemeColors(
        primary="#2E7D32",
        secondary="#81C784",
        accent="#FF8F00",
        background="#F1F8E9",
        text="#1B5E20",
        text_light="#689F38",
        title_background="#2E7D32",
    ),
    font_heading="Georgia",
    font_body="Verdana",
    description="Organic theme for sustainability, environment, and nature topics",
))

_register(SlideTheme(
    id="tech-dark",
    name="Tech Dark",
    colors=SlideThemeColors(
        primary="#00E5FF",
        secondary="#7C4DFF",
        accent="#FF4081",
        background="#121212",
        text="#E0E0E0",
        text_light="#9E9E9E",
        title_background="#0A0A0A",
    ),
    font_heading="Calibri",
    font_body="Calibri Light",
    description="Dark mode theme for technology and developer-focused decks",
))

_register(SlideTheme(
    id="warm-terracotta",
    name="Warm Terracotta",
    colors=SlideThemeColors(
        primary="#C75B39",
        secondary="#D4956A",
        accent="#5B8C5A",
        background="#FFF8F0",
        text="#3E2723",
        text_light="#8D6E63",
        title_background="#5C2A1A",
    ),
    font_heading="Constantia",
    font_body="Candara",
    description="Warm, earthy theme for creative and lifestyle presentations",
))

_register(SlideTheme(
    id="ocean-gradient",
    name="Ocean Gradient",
    colors=SlideThemeColors(
        primary="#006994",
        secondary="#40C4FF",
        accent="#FFAB40",
        background="#E3F2FD",
        text="#01579B",
        text_light="#4FC3F7",
        title_background="#006994",
    ),
    font_heading="Trebuchet MS",
    font_body="Verdana",
    description="Calming ocean-inspired theme with gradient accents",
))

_register(SlideTheme(
    id="monochrome-pro",
    name="Monochrome Pro",
    colors=SlideThemeColors(
        primary="#000000",
        secondary="#424242",
        accent="#F44336",
        background="#FFFFFF",
        text="#212121",
        text_light="#757575",
        title_background="#1A1A1A",
    ),
    font_heading="Arial",
    font_body="Arial",
    description="High-contrast black and white theme with red accent",
))

# === Phase 3 Base Themes (8 new) ===

_register(SlideTheme(
    id="finance-navy",
    name="Finance Navy",
    colors=SlideThemeColors(
        primary="#0A1F44",
        secondary="#2E5090",
        accent="#C9A84C",
        background="#FFFFFF",
        text="#0A1F44",
        text_light="#6B7B8D",
        title_background="#0A1F44",
    ),
    font_heading="Garamond",
    font_body="Trebuchet MS",
    description="Conservative theme for financial reports and investor decks",
))

_register(SlideTheme(
    id="healthcare-teal",
    name="Healthcare Teal",
    colors=SlideThemeColors(
        primary="#007C91",
        secondary="#4DB6AC",
        accent="#FF7043",
        background="#FFFFFF",
        text="#004D5A",
        text_light="#78909C",
        title_background="#007C91",
    ),
    font_heading="Corbel",
    font_body="Corbel",
    description="Clean theme for healthcare and life sciences presentations",
))

_register(SlideTheme(
    id="education-purple",
    name="Education Purple",
    colors=SlideThemeColors(
        primary="#5C2D91",
        secondary="#9575CD",
        accent="#FFB300",
        background="#F5F0FA",
        text="#311B60",
        text_light="#7E57C2",
        title_background="#5C2D91",
    ),
    font_heading="Constantia",
    font_body="Candara",
    description="Academic theme for education and research presentations",
))

_register(SlideTheme(
    id="executive-charcoal",
    name="Executive Charcoal",
    colors=SlideThemeColors(
        primary="#333333",
        secondary="#616161",
        accent="#B8860B",
        background="#FAFAFA",
        text="#212121",
        text_light="#9E9E9E",
        title_background="#2A2A2A",
    ),
    font_heading="Garamond",
    font_body="Trebuchet MS",
    description="Refined theme for C-suite and board presentations",
))

_register(SlideTheme(
    id="creative-coral",
    name="Creative Coral",
    colors=SlideThemeColors(
        primary="#FF6F61",
        secondary="#FF8A80",
        accent="#00BFA5",
        background="#FFF3F0",
        text="#3E2723",
        text_light="#8D6E63",
        title_background="#8B2500",
    ),
    font_heading="Century Gothic",
    font_body="Century Gothic",
    description="Bold theme for creative agencies and design showcases",
))

_register(SlideTheme(
    id="legal-burgundy",
    name="Legal Burgundy",
    colors=SlideThemeColors(
        primary="#6B2737",
        secondary="#9C4154",
        accent="#C9A84C",
        background="#FFFAF5",
        text="#3E1520",
        text_light="#8D6E63",
        title_background="#6B2737",
    ),
    font_heading="Book Antiqua",
    font_body="Tahoma",
    description="Formal theme for legal and compliance presentations",
))

_register(SlideTheme(
    id="product-indigo",
    name="Product Indigo",
    colors=SlideThemeColors(
        primary="#3F51B5",
        secondary="#7986CB",
        accent="#FF5722",
        background="#F5F5FF",
        text="#1A237E",
        text_light="#7986CB",
        title_background="#3F51B5",
    ),
    font_heading="Calibri",
    font_body="Calibri Light",
    description="Modern theme for product launches and roadmap decks",
))

_register(SlideTheme(
    id="sunset-amber",
    name="Sunset Amber",
    colors=SlideThemeColors(
        primary="#FF8F00",
        secondary="#FFB74D",
        accent="#5C6BC0",
        background="#FFFDE7",
        text="#E65100",
        text_light="#FF8F00",
        title_background="#BF360C",
    ),
    font_heading="Trebuchet MS",
    font_body="Verdana",
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
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, int(r * 255 + 0.5))),
        max(0, min(255, int(g * 255 + 0.5))),
        max(0, min(255, int(b * 255 + 0.5))),
    )


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
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, bl))
    )


# === Variant Generation ===

def generate_theme_variant(base_id: str, variant_seed: int) -> SlideTheme:
    """Generate a deterministic theme variant from a base theme.

    Returns a new SlideTheme with id="{base_id}--v{NN}".
    Raises ValueError if base_id is not a registered base theme.
    """
    if base_id not in _THEMES:
        raise ValueError(f"Unknown base theme: {base_id}")
    base = _THEMES[base_id]

    rng = random.Random(variant_seed)
    offset = rng.choice([15, -15, 30, -30, 45, -45])

    # Color derivation
    new_primary = _hue_rotate(base.colors.primary, offset)
    new_secondary = _hue_rotate(base.colors.secondary, offset)
    # Accent: complementary of new primary (180° opposite)
    new_accent = _hue_rotate(new_primary, 180)
    new_background = base.colors.background

    # Text: auto-contrast based on background luminance
    bg_lum = _relative_luminance(new_background)
    if bg_lum < 0.5:
        new_text = "#E0E0E0"
        new_text_light = "#9E9E9E"
    else:
        new_text = "#212121"
        new_text_light = "#757575"

    # Contrast validation and fix
    new_text = _fix_contrast(new_text, new_background)
    new_text_light = _fix_contrast(new_text_light, new_background)

    # Font pairing: cycle through allow-list
    font_pair = _FONT_PAIRS[variant_seed % len(_FONT_PAIRS)]

    # Background style
    bg_style = _BACKGROUND_STYLES[(variant_seed - 1) % len(_BACKGROUND_STYLES)]

    # Carry over and hue-rotate title_background if present
    new_title_bg = None
    if base.colors.title_background:
        new_title_bg = _hue_rotate(base.colors.title_background, offset)

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
