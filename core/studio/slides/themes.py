"""Curated theme catalog for Forge slides."""

from core.schemas.studio_schema import SlideTheme, SlideThemeColors

_THEMES: dict[str, SlideTheme] = {}


def _register(theme: SlideTheme) -> None:
    _THEMES[theme.id] = theme


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
    ),
    font_heading="Montserrat",
    font_body="Open Sans",
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
    ),
    font_heading="Helvetica",
    font_body="Helvetica Light",
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
    ),
    font_heading="Georgia",
    font_body="Lato",
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
    ),
    font_heading="Roboto",
    font_body="Roboto Light",
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
    ),
    font_heading="Playfair Display",
    font_body="Source Sans Pro",
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
    ),
    font_heading="Poppins",
    font_body="Nunito",
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
    ),
    font_heading="Arial",
    font_body="Arial",
    description="High-contrast black and white theme with red accent",
))

DEFAULT_THEME_ID = "corporate-blue"


def get_theme(theme_id: str | None = None) -> SlideTheme:
    """Resolve theme by ID, falling back to default if not found."""
    if theme_id is None:
        return _THEMES[DEFAULT_THEME_ID]
    return _THEMES.get(theme_id, _THEMES[DEFAULT_THEME_ID])


def list_themes() -> list[SlideTheme]:
    """Return all available themes as a list."""
    return list(_THEMES.values())


def get_theme_ids() -> list[str]:
    """Return all available theme IDs."""
    return list(_THEMES.keys())
