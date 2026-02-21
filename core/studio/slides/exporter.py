"""PPTX renderer for Forge slides — programmatic shapes, no templates."""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from core.schemas.studio_schema import SlideTheme, SlidesContentTree

# 16:9 widescreen dimensions
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

# Margins
MARGIN_LEFT = Inches(0.75)
MARGIN_TOP = Inches(0.75)
MARGIN_RIGHT = Inches(0.75)
MARGIN_BOTTOM = Inches(0.5)

# Content area
CONTENT_WIDTH = SLIDE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
CONTENT_HEIGHT = SLIDE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

# Title area
TITLE_TOP = Inches(0.5)
TITLE_LEFT = MARGIN_LEFT
TITLE_WIDTH = CONTENT_WIDTH
TITLE_HEIGHT = Inches(1.0)

# Body area (below title)
BODY_TOP = Inches(1.8)
BODY_LEFT = MARGIN_LEFT
BODY_WIDTH = CONTENT_WIDTH
BODY_HEIGHT = Inches(5.0)

# Two-column split
COLUMN_GAP = Inches(0.5)
COLUMN_WIDTH = (CONTENT_WIDTH - COLUMN_GAP) / 2


def export_to_pptx(
    content_tree: SlidesContentTree,
    theme: SlideTheme,
    output_path: Path,
) -> Path:
    """Export a SlidesContentTree to PPTX format.

    Returns the output file path.
    """
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    blank_layout = prs.slide_layouts[6]  # Blank layout

    for slide_data in content_tree.slides:
        pptx_slide = prs.slides.add_slide(blank_layout)

        renderer = _RENDERERS.get(slide_data.slide_type, _render_content)
        renderer(pptx_slide, slide_data, theme)

        if slide_data.speaker_notes:
            notes_slide = pptx_slide.notes_slide
            notes_slide.notes_text_frame.text = slide_data.speaker_notes

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    return output_path


# === Helper Functions ===

def _add_text_box(slide, text, left, top, width, height,
                  font_name="Calibri", font_size=Pt(18),
                  font_color="#000000", alignment=PP_ALIGN.LEFT,
                  bold=False):
    """Add a text box shape with styled text."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = str(text)
    p.font.name = font_name
    p.font.size = font_size
    p.font.bold = bold
    p.alignment = alignment
    if isinstance(font_color, str):
        font_color = RGBColor.from_string(font_color.lstrip("#"))
    p.font.color.rgb = font_color


def _add_bullet_list(slide, items, left, top, width, height,
                     font_name="Calibri", font_size=Pt(16),
                     font_color="#000000"):
    """Add a text box with bullet-point paragraphs."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = f"\u2022 {item}"
        p.font.name = font_name
        p.font.size = font_size
        if isinstance(font_color, str):
            p.font.color.rgb = RGBColor.from_string(font_color.lstrip("#"))
        p.space_after = Pt(6)


def _find_element(slide_data, element_type):
    """Find first element of a given type in slide data."""
    for el in slide_data.elements:
        if el.type == element_type:
            return el
    return None


def _set_slide_background(slide, color_hex):
    """Set solid background color for a slide."""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor.from_string(color_hex.lstrip("#"))


# === Slide-Type Renderer Functions ===

def _render_title(slide, slide_data, theme):
    """Title slide: centered title + subtitle."""
    _add_text_box(slide, slide_data.title or "",
                  left=MARGIN_LEFT, top=Inches(2.5),
                  width=CONTENT_WIDTH, height=Inches(1.5),
                  font_name=theme.font_heading, font_size=Pt(44),
                  font_color=theme.colors.primary, alignment=PP_ALIGN.CENTER,
                  bold=True)
    subtitle_el = _find_element(slide_data, "subtitle")
    if subtitle_el and subtitle_el.content:
        _add_text_box(slide, subtitle_el.content,
                      left=MARGIN_LEFT, top=Inches(4.2),
                      width=CONTENT_WIDTH, height=Inches(0.8),
                      font_name=theme.font_body, font_size=Pt(24),
                      font_color=theme.colors.text_light, alignment=PP_ALIGN.CENTER)
    _set_slide_background(slide, theme.colors.background)


def _render_content(slide, slide_data, theme):
    """Standard content slide: title + body/bullets."""
    _add_text_box(slide, slide_data.title or "",
                  left=TITLE_LEFT, top=TITLE_TOP,
                  width=TITLE_WIDTH, height=TITLE_HEIGHT,
                  font_name=theme.font_heading, font_size=Pt(32),
                  font_color=theme.colors.primary, bold=True)

    body_el = _find_element(slide_data, "body")
    bullet_el = _find_element(slide_data, "bullet_list")

    if bullet_el and isinstance(bullet_el.content, list):
        _add_bullet_list(slide, bullet_el.content,
                         left=BODY_LEFT, top=BODY_TOP,
                         width=BODY_WIDTH, height=BODY_HEIGHT,
                         font_name=theme.font_body, font_size=Pt(18),
                         font_color=theme.colors.text)
    elif body_el and body_el.content:
        _add_text_box(slide, body_el.content,
                      left=BODY_LEFT, top=BODY_TOP,
                      width=BODY_WIDTH, height=BODY_HEIGHT,
                      font_name=theme.font_body, font_size=Pt(18),
                      font_color=theme.colors.text)

    _set_slide_background(slide, theme.colors.background)


def _render_two_column(slide, slide_data, theme):
    """Two-column layout: title + left/right body areas."""
    _add_text_box(slide, slide_data.title or "",
                  left=TITLE_LEFT, top=TITLE_TOP,
                  width=TITLE_WIDTH, height=TITLE_HEIGHT,
                  font_name=theme.font_heading, font_size=Pt(32),
                  font_color=theme.colors.primary, bold=True)

    body_elements = [el for el in slide_data.elements if el.type == "body"]
    bullet_elements = [el for el in slide_data.elements if el.type == "bullet_list"]

    # Left column
    left_content = body_elements[0].content if body_elements else ""
    if bullet_elements and isinstance(bullet_elements[0].content, list):
        _add_bullet_list(slide, bullet_elements[0].content,
                         left=MARGIN_LEFT, top=BODY_TOP,
                         width=COLUMN_WIDTH, height=BODY_HEIGHT,
                         font_name=theme.font_body, font_size=Pt(16),
                         font_color=theme.colors.text)
    else:
        _add_text_box(slide, left_content,
                      left=MARGIN_LEFT, top=BODY_TOP,
                      width=COLUMN_WIDTH, height=BODY_HEIGHT,
                      font_name=theme.font_body, font_size=Pt(16),
                      font_color=theme.colors.text)

    # Right column
    right_content = body_elements[1].content if len(body_elements) > 1 else ""
    if len(bullet_elements) > 1 and isinstance(bullet_elements[1].content, list):
        _add_bullet_list(slide, bullet_elements[1].content,
                         left=MARGIN_LEFT + COLUMN_WIDTH + COLUMN_GAP, top=BODY_TOP,
                         width=COLUMN_WIDTH, height=BODY_HEIGHT,
                         font_name=theme.font_body, font_size=Pt(16),
                         font_color=theme.colors.text)
    else:
        _add_text_box(slide, right_content,
                      left=MARGIN_LEFT + COLUMN_WIDTH + COLUMN_GAP, top=BODY_TOP,
                      width=COLUMN_WIDTH, height=BODY_HEIGHT,
                      font_name=theme.font_body, font_size=Pt(16),
                      font_color=theme.colors.text)

    _set_slide_background(slide, theme.colors.background)


def _render_comparison(slide, slide_data, theme):
    """Comparison slide: title + two labeled columns."""
    _add_text_box(slide, slide_data.title or "",
                  left=TITLE_LEFT, top=TITLE_TOP,
                  width=TITLE_WIDTH, height=TITLE_HEIGHT,
                  font_name=theme.font_heading, font_size=Pt(32),
                  font_color=theme.colors.primary, bold=True)

    body_elements = [el for el in slide_data.elements if el.type == "body"]
    left_text = body_elements[0].content if body_elements else ""
    right_text = body_elements[1].content if len(body_elements) > 1 else ""

    _add_text_box(slide, left_text,
                  left=MARGIN_LEFT, top=BODY_TOP,
                  width=COLUMN_WIDTH, height=BODY_HEIGHT,
                  font_name=theme.font_body, font_size=Pt(16),
                  font_color=theme.colors.text)

    _add_text_box(slide, right_text,
                  left=MARGIN_LEFT + COLUMN_WIDTH + COLUMN_GAP, top=BODY_TOP,
                  width=COLUMN_WIDTH, height=BODY_HEIGHT,
                  font_name=theme.font_body, font_size=Pt(16),
                  font_color=theme.colors.text)

    _set_slide_background(slide, theme.colors.background)


def _render_timeline(slide, slide_data, theme):
    """Timeline/roadmap slide: title + sequential items."""
    _add_text_box(slide, slide_data.title or "",
                  left=TITLE_LEFT, top=TITLE_TOP,
                  width=TITLE_WIDTH, height=TITLE_HEIGHT,
                  font_name=theme.font_heading, font_size=Pt(32),
                  font_color=theme.colors.primary, bold=True)

    bullet_el = _find_element(slide_data, "bullet_list")
    body_el = _find_element(slide_data, "body")

    if bullet_el and isinstance(bullet_el.content, list):
        _add_bullet_list(slide, bullet_el.content,
                         left=BODY_LEFT, top=BODY_TOP,
                         width=BODY_WIDTH, height=BODY_HEIGHT,
                         font_name=theme.font_body, font_size=Pt(18),
                         font_color=theme.colors.text)
    elif body_el and body_el.content:
        _add_text_box(slide, body_el.content,
                      left=BODY_LEFT, top=BODY_TOP,
                      width=BODY_WIDTH, height=BODY_HEIGHT,
                      font_name=theme.font_body, font_size=Pt(18),
                      font_color=theme.colors.text)

    _set_slide_background(slide, theme.colors.background)


def _render_chart(slide, slide_data, theme):
    """Chart slide: title + placeholder for chart data."""
    _add_text_box(slide, slide_data.title or "",
                  left=TITLE_LEFT, top=TITLE_TOP,
                  width=TITLE_WIDTH, height=TITLE_HEIGHT,
                  font_name=theme.font_heading, font_size=Pt(32),
                  font_color=theme.colors.primary, bold=True)

    chart_el = _find_element(slide_data, "chart")
    body_el = _find_element(slide_data, "body")

    # Chart rendering is a placeholder in Phase 2 — render as text
    if chart_el and chart_el.content:
        content = chart_el.content if isinstance(chart_el.content, str) else str(chart_el.content)
        _add_text_box(slide, f"[Chart: {content}]",
                      left=BODY_LEFT, top=BODY_TOP,
                      width=BODY_WIDTH, height=Inches(3.0),
                      font_name=theme.font_body, font_size=Pt(16),
                      font_color=theme.colors.secondary,
                      alignment=PP_ALIGN.CENTER)

    if body_el and body_el.content:
        _add_text_box(slide, body_el.content,
                      left=BODY_LEFT, top=Inches(5.0),
                      width=BODY_WIDTH, height=Inches(1.5),
                      font_name=theme.font_body, font_size=Pt(16),
                      font_color=theme.colors.text)

    _set_slide_background(slide, theme.colors.background)


def _render_image_text(slide, slide_data, theme):
    """Image+text slide: split layout with image placeholder and body."""
    _add_text_box(slide, slide_data.title or "",
                  left=TITLE_LEFT, top=TITLE_TOP,
                  width=TITLE_WIDTH, height=TITLE_HEIGHT,
                  font_name=theme.font_heading, font_size=Pt(32),
                  font_color=theme.colors.primary, bold=True)

    image_el = _find_element(slide_data, "image")
    body_el = _find_element(slide_data, "body")

    # Image placeholder (Phase 2 — no actual image rendering)
    placeholder_text = "[Image]"
    if image_el and image_el.content:
        placeholder_text = f"[Image: {image_el.content}]"
    _add_text_box(slide, placeholder_text,
                  left=MARGIN_LEFT, top=BODY_TOP,
                  width=COLUMN_WIDTH, height=BODY_HEIGHT,
                  font_name=theme.font_body, font_size=Pt(16),
                  font_color=theme.colors.secondary,
                  alignment=PP_ALIGN.CENTER)

    if body_el and body_el.content:
        _add_text_box(slide, body_el.content,
                      left=MARGIN_LEFT + COLUMN_WIDTH + COLUMN_GAP, top=BODY_TOP,
                      width=COLUMN_WIDTH, height=BODY_HEIGHT,
                      font_name=theme.font_body, font_size=Pt(16),
                      font_color=theme.colors.text)

    _set_slide_background(slide, theme.colors.background)


def _render_quote(slide, slide_data, theme):
    """Quote slide: large quote text with attribution."""
    quote_el = _find_element(slide_data, "quote")
    body_el = _find_element(slide_data, "body")

    quote_text = ""
    if quote_el and quote_el.content:
        quote_text = f"\u201C{quote_el.content}\u201D"
    elif slide_data.title:
        quote_text = slide_data.title

    _add_text_box(slide, quote_text,
                  left=Inches(1.5), top=Inches(2.0),
                  width=Inches(10.333), height=Inches(2.5),
                  font_name=theme.font_heading, font_size=Pt(36),
                  font_color=theme.colors.primary,
                  alignment=PP_ALIGN.CENTER)

    if body_el and body_el.content:
        _add_text_box(slide, f"\u2014 {body_el.content}",
                      left=Inches(1.5), top=Inches(5.0),
                      width=Inches(10.333), height=Inches(0.8),
                      font_name=theme.font_body, font_size=Pt(20),
                      font_color=theme.colors.text_light,
                      alignment=PP_ALIGN.CENTER)

    _set_slide_background(slide, theme.colors.background)


def _render_code(slide, slide_data, theme):
    """Code slide: title + monospace code block."""
    _add_text_box(slide, slide_data.title or "",
                  left=TITLE_LEFT, top=TITLE_TOP,
                  width=TITLE_WIDTH, height=TITLE_HEIGHT,
                  font_name=theme.font_heading, font_size=Pt(32),
                  font_color=theme.colors.primary, bold=True)

    code_el = _find_element(slide_data, "code")
    if code_el and code_el.content:
        _add_text_box(slide, code_el.content,
                      left=Inches(1.0), top=BODY_TOP,
                      width=Inches(11.333), height=BODY_HEIGHT,
                      font_name="Courier New", font_size=Pt(14),
                      font_color=theme.colors.text)

    _set_slide_background(slide, theme.colors.background)


def _render_team(slide, slide_data, theme):
    """Team/credits slide: title + team member list."""
    _add_text_box(slide, slide_data.title or "",
                  left=TITLE_LEFT, top=TITLE_TOP,
                  width=TITLE_WIDTH, height=TITLE_HEIGHT,
                  font_name=theme.font_heading, font_size=Pt(32),
                  font_color=theme.colors.primary, bold=True)

    bullet_el = _find_element(slide_data, "bullet_list")
    body_el = _find_element(slide_data, "body")

    if bullet_el and isinstance(bullet_el.content, list):
        _add_bullet_list(slide, bullet_el.content,
                         left=BODY_LEFT, top=BODY_TOP,
                         width=BODY_WIDTH, height=BODY_HEIGHT,
                         font_name=theme.font_body, font_size=Pt(18),
                         font_color=theme.colors.text)
    elif body_el and body_el.content:
        _add_text_box(slide, body_el.content,
                      left=BODY_LEFT, top=BODY_TOP,
                      width=BODY_WIDTH, height=BODY_HEIGHT,
                      font_name=theme.font_body, font_size=Pt(18),
                      font_color=theme.colors.text)

    _set_slide_background(slide, theme.colors.background)


# Renderer dispatch table
_RENDERERS = {
    "title": _render_title,
    "content": _render_content,
    "two_column": _render_two_column,
    "comparison": _render_comparison,
    "timeline": _render_timeline,
    "chart": _render_chart,
    "image_text": _render_image_text,
    "quote": _render_quote,
    "code": _render_code,
    "team": _render_team,
}
