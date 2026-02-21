# Forge Phase 3 — Implementation Plan: Slides Quality Pass (Days 9-10)

## Context

Phase 1 (Days 1-5) established canonical Pydantic schemas (`core/schemas/studio_schema.py`), outline-first orchestration (`core/studio/orchestrator.py`), file-based storage with revision tracking (`core/studio/storage.py`), LLM prompt templates (`core/studio/prompts.py`), and 8 API endpoints — all backed by 65+ tests across 5 test files.

Phase 2 (Days 6-8) delivered a production-usable Slides MVP: deterministic slide generation with seed-based structural planning (`core/studio/slides/generator.py`), 8 curated themes (`core/studio/slides/themes.py`), PPTX export using programmatic shapes (`core/studio/slides/exporter.py`), open-validation with layout heuristics (`core/studio/slides/validator.py`), export job tracking with persistence and 6 new API endpoints — adding 78 new tests and bringing the combined total to 143+.

Phase 3 builds on Phase 2 to deliver a quality pass that upgrades slide output from "functional" to "polished":

- **Theme bundle system** that expands from 8 curated bases to 16 bases + procedural variants, reaching 112+ total themes
- **Native chart rendering** using python-pptx chart objects for bar/line/pie/funnel/scatter
- **Speaker notes quality pass** with prompt strengthening and deterministic post-generation repair
- **Blocking layout-quality validator** that promotes Phase 2 advisory warnings to export gate enforcement

This plan is derived from:

- `docs/forge_20_day_plan.md` (Phase 3 scope: Days 9-10, gates, exit criteria)
- `docs/forge_specs.md` (FR-SL2: 100+ themes, FR-SL4: auto-chart/notes, NFR: layout-quality validator)

### Scope Boundaries

**In scope:**
- Expand theme catalog from 8 to 16 curated bases; add deterministic variant generator to reach 112+ themes
- Replace `_render_chart` text placeholder with native `python-pptx` `add_chart()` using `CategoryChartData`/`XyChartData`
- Add `charts.py` with chart spec parsing, normalization, and type inference
- Add `notes.py` with speaker notes scoring and post-generation repair
- Strengthen prompts for chart JSON schema and speaker notes rubric
- Upgrade `validator.py` to v2 with blocking layout checks, chart quality checks, notes quality checks, and quality score
- Wire notes repair into draft path and strict validator into export path in `orchestrator.py`
- Add `strict_layout` export parameter and theme listing controls to `routers/studio.py`
- ~81 new tests across 4 new + 5 modified test files

**Out of scope:**
- New export formats (PDF/HTML/Google Slides) — Phase 4-5
- Document and Sheet export engines — Phase 4-5
- Pixel-perfect rendering parity against design tools
- External image generation quality improvements
- Real-time WYSIWYG editing workflows — Phase 6
- Fully asynchronous export queue redesign

### Codebase Patterns Referenced

| Pattern | Source File | What to Replicate |
|---------|-----------|-------------------|
| Pydantic schema evolution with backward-safe optional fields | `core/schemas/studio_schema.py` | Add optional chart/theme/quality fields without breaking existing artifacts |
| Deterministic utility functions with seed-based behavior | `core/studio/slides/generator.py` | `compute_seed()` + `random.Random(seed)` pattern for stable variant generation |
| Data-driven registries (plain model instances in dict) | `core/studio/slides/themes.py` | `_THEMES` dict + `_register()` pattern; avoid class hierarchies |
| Renderer dispatch table | `core/studio/slides/exporter.py` | `_RENDERERS` dict dispatches to per-type functions |
| Export dispatch and status lifecycle | `core/studio/orchestrator.py` | `export_artifact()` preserves pending/completed/failed workflow |
| Router validation + static route ordering | `routers/studio.py` | `_validate_artifact_id()` + static routes before `/{artifact_id}` |
| Acceptance/integration gate format | `tests/acceptance/p04_forge/test_exports_open_and_render.py` | Extend existing numbered tests (test_18+) |

---

## 1. Directory & File Structure

```
Arcturus/
├── core/
│   ├── schemas/
│   │   └── studio_schema.py                               # MODIFY — ChartType enum, ChartSpec/ChartSeries/ScatterPoint, SlideTheme variant fields
│   └── studio/
│       ├── orchestrator.py                                # MODIFY — notes repair in draft path, strict validator in export path
│       ├── prompts.py                                     # MODIFY — chart JSON schema guidance, stronger notes rubric
│       └── slides/
│           ├── themes.py                                  # MODIFY — 8 new curated bases, variant generator, variant-aware list/resolve
│           ├── exporter.py                                # MODIFY — native chart rendering via add_chart(), chart layout constants
│           ├── validator.py                               # MODIFY — v2 blocking layout checks, chart/notes quality, quality score
│           ├── charts.py                                  # NEW — parse_chart_spec(), normalize_chart_spec(), infer_chart_type()
│           └── notes.py                                   # NEW — score_speaker_notes(), repair_speaker_notes()
├── routers/
│   └── studio.py                                          # MODIFY — strict_layout export param, theme listing query params
├── tests/
│   ├── test_studio_slides_theme_variants.py               # NEW — 14 tests
│   ├── test_studio_slides_charts.py                       # NEW — 14 tests
│   ├── test_studio_slides_notes.py                        # NEW — 10 tests
│   ├── test_studio_slides_validator.py                    # NEW — 14 tests
│   ├── test_studio_slides_themes.py                       # MODIFY — +6 tests
│   ├── test_studio_slides_exporter.py                     # MODIFY — +10 tests
│   ├── test_studio_export_router.py                       # MODIFY — +4 tests
│   ├── acceptance/p04_forge/test_exports_open_and_render.py   # MODIFY — +4 tests (test_18 through test_21)
│   └── integration/test_forge_research_to_slides.py           # MODIFY — +4 tests (test_14 through test_17)
└── docs/
    └── forge_phase3_implementation_plan.md                 # THIS DOCUMENT
```

**Total: 2 new files + 7 modified files + 4 new test files + 5 modified test files**

---

## 2. Schema Additions

**File:** `core/schemas/studio_schema.py`

Phase 3 adds typed structures for chart data and theme variant metadata. All new fields are optional — existing artifacts and export jobs deserialize without migration.

### 2.1 New Enum

```python
class ChartType(str, Enum):
    bar = "bar"
    line = "line"
    pie = "pie"
    funnel = "funnel"
    scatter = "scatter"
```

### 2.2 Chart Models

```python
class ChartSeries(BaseModel):
    name: str
    values: List[float]


class ScatterPoint(BaseModel):
    x: float
    y: float


class ChartSpec(BaseModel):
    chart_type: Optional[ChartType] = None
    title: Optional[str] = None
    categories: List[str] = Field(default_factory=list)       # bar/line/pie/funnel
    series: List[ChartSeries] = Field(default_factory=list)   # bar/line/pie/funnel
    points: List[ScatterPoint] = Field(default_factory=list)  # scatter only
    x_label: Optional[str] = None
    y_label: Optional[str] = None
```

### 2.3 Theme Variant Metadata

Add three optional fields to the existing `SlideTheme` model:

```python
class SlideTheme(BaseModel):
    id: str
    name: str
    colors: SlideThemeColors
    font_heading: str
    font_body: str
    description: Optional[str] = None
    base_theme_id: Optional[str] = None      # NEW — links variant to its base
    variant_seed: Optional[int] = None       # NEW — deterministic seed used to generate this variant
    background_style: Optional[str] = None   # NEW — "solid" | "gradient" | "subtle_pattern"
```

**Backward compatibility:** All three fields are `Optional` with `None` defaults. Existing themes remain valid. The 8 Phase 2 base themes have `base_theme_id=None`, distinguishing them from generated variants.

### 2.4 Validator Results Convention

`ExportJob.validator_results` remains `Optional[Dict[str, Any]]` for flexibility. Phase 3 standardizes the keys written by the upgraded validator:

| Key | Type | Description |
|-----|------|-------------|
| `valid` | `bool` | Structural integrity (PPTX opens, slide count matches) |
| `slide_count` | `int` | Number of slides in PPTX |
| `has_notes` | `bool` | At least one slide has speaker notes |
| `errors` | `list[str]` | Structural errors |
| `layout_valid` | `bool` | No layout violations (text overflow, out-of-bounds shapes) |
| `layout_warnings` | `list[str]` | Non-blocking layout concerns |
| `layout_errors` | `list[str]` | Blocking layout violations |
| `notes_quality_valid` | `bool` | Deck-level notes quality pass |
| `chart_quality_valid` | `bool` | Chart slides contain chart object or fallback marker |
| `quality_score` | `int` | Overall quality score 0-100 |
| `strict_layout` | `bool` | Whether strict layout enforcement was applied (set by orchestrator) |

---

## 3. Theme Bundle System

**File:** `core/studio/slides/themes.py`

### 3.1 Curated Base Theme Expansion (8 → 16)

Keep existing 8 theme IDs stable to avoid breaking saved artifacts that reference them. Add 8 new curated bases:

| ID | Name | Primary | Font Heading | Description |
|----|------|---------|-------------|-------------|
| `finance-navy` | Finance Navy | `#0A1F44` | Garamond | Conservative theme for financial reports and investor decks |
| `healthcare-teal` | Healthcare Teal | `#007C91` | Nunito Sans | Clean theme for healthcare and life sciences presentations |
| `education-purple` | Education Purple | `#5C2D91` | Merriweather | Academic theme for education and research presentations |
| `executive-charcoal` | Executive Charcoal | `#333333` | Didot | Refined theme for C-suite and board presentations |
| `creative-coral` | Creative Coral | `#FF6F61` | Futura | Bold theme for creative agencies and design showcases |
| `legal-burgundy` | Legal Burgundy | `#6B2737` | Baskerville | Formal theme for legal and compliance presentations |
| `product-indigo` | Product Indigo | `#3F51B5` | Inter | Modern theme for product launches and roadmap decks |
| `sunset-amber` | Sunset Amber | `#FF8F00` | Josefin Sans | Warm theme for lifestyle and community presentations |

Each new theme follows the same `_register(SlideTheme(...))` pattern as the existing 8.

### 3.2 Procedural Variant Generation

Deterministic variant generation using HSL color space transformations:

```python
def generate_theme_variant(base_id: str, variant_seed: int) -> SlideTheme:
    """Generate a deterministic theme variant from a base theme.

    Transformations applied per seed:
    - Hue rotation: ±15°, ±30°, ±45° on primary color
    - Font pairing: cycle through allow-list of compatible pairs
    - Background style: solid / gradient / subtle_pattern
      Gradient is functional (not metadata-only); see _set_slide_background() in exporter.

    Returns a new SlideTheme with id="{base_id}--v{NN}".
    Raises ValueError if base_id is not a registered base theme.
    """
```

**ID format:** `{base_theme_id}--v{NN}` where NN is zero-padded (01-06).

**Deterministic seed mapping:** `variant_seed = NN` — the zero-padded number IS the seed. So `corporate-blue--v01` has `variant_seed=1`, `--v06` has `variant_seed=6`. This mapping is permanent — `get_theme("X--v03")` always regenerates the same theme because seed=3 is deterministic.

**`get_theme()` resolution for variant IDs:** Parse `--v{NN}` suffix → extract `base_id` and `NN` → call `generate_theme_variant(base_id, variant_seed=NN)`. If the suffix is not present, look up the base registry directly.

**Variant count:** 6 variants per base × 16 bases = 96 variants + 16 bases = **112 total themes**.

**Font allow-list** (PPTX-safe, widely available):

```python
_FONT_PAIRS = [
    ("Calibri", "Calibri Light"),
    ("Arial", "Arial"),
    ("Georgia", "Lato"),
    ("Roboto", "Roboto Light"),
    ("Poppins", "Nunito"),
    ("Montserrat", "Open Sans"),
]
```

**Variant color derivation rules:**

```
primary:    hue_rotate(base.primary, offset)
secondary:  hue_rotate(base.secondary, offset)
accent:     complementary(new_primary)  # 180° opposite
background: base.background (preserved)
text:       auto_contrast(background)   # black if bg is light, white if dark
text_light: lighten(text, 30%)
```

The `offset` is derived from the variant seed (e.g., `seed * 30°`). These rules ensure variant palettes are visually coherent while maintaining readability via the contrast check in Section 3.3.

### 3.3 Contrast Validation

Before a variant is accepted, validate text-on-background contrast:

```python
def _check_contrast(text_hex: str, bg_hex: str) -> bool:
    """WCAG AA check: luminance ratio >= 4.5:1 for text on background."""

def _fix_contrast(text_hex: str, bg_hex: str) -> str:
    """Deterministically adjust text color lightness to meet WCAG AA.

    Steps lightness ±10% (up to 3 steps) until ratio >= 4.5:1.
    If background is dark, lighten text; if light, darken text.
    Returns adjusted text hex. Seed is never changed.
    """
```

If a variant's text-on-background contrast fails WCAG AA, `_fix_contrast()` deterministically adjusts the text color lightness until the ratio passes. The seed is never changed, preserving strict ID→seed→output determinism.

### 3.4 Updated Public API

```python
DEFAULT_THEME_ID = "corporate-blue"

def get_theme(theme_id: str | None = None) -> SlideTheme:
    """Resolve theme by ID — checks bases first, then generates variant on demand.

    Falls back to corporate-blue if not found.
    """

def list_themes(
    include_variants: bool = False,
    base_id: str | None = None,
    limit: int | None = None,
) -> list[SlideTheme]:
    """Return available themes.

    include_variants=False (default): return only base themes (backward compatible).
    include_variants=True: return bases + all generated variants.
    base_id: when provided, returns the base theme + all its variants
             (ignoring include_variants). When not provided, include_variants
             controls whether variants are included.
    limit: cap the number of returned themes.
    """

def get_theme_ids(include_variants: bool = False) -> list[str]:
    """Return all available theme IDs."""
```

**Backward compatibility:** `list_themes()` with no args returns 16 base themes (superset of Phase 2's 8). Existing callers unaffected.

---

## 4. Chart Data Contract

**File:** `core/studio/slides/charts.py` (NEW)

### 4.1 Accepted Chart Element Payload

For `SlideElement(type="chart")`, the preferred `content` format is a structured dict:

```json
{
  "chart_type": "bar",
  "title": "Quarterly Revenue",
  "categories": ["Q1", "Q2", "Q3", "Q4"],
  "series": [{"name": "Revenue", "values": [1.2, 1.8, 2.6, 3.1]}],
  "x_label": "Quarter",
  "y_label": "USD (Millions)"
}
```

### 4.2 Helper Functions

```python
from typing import Any, Optional
from core.schemas.studio_schema import ChartSpec, ChartType


def parse_chart_spec(content: Any) -> Optional[ChartSpec]:
    """Parse a SlideElement.content value into a ChartSpec.

    Accepts:
    - dict with categories/series or points → ChartSpec
    - str → attempt JSON parse; return None if not structured chart data

    When chart_type is None after parsing, calls infer_chart_type() to fill it.
    Returns None only if inference also fails (no points AND no series).
    """


def normalize_chart_spec(spec: ChartSpec) -> ChartSpec:
    """Normalize a parsed ChartSpec for rendering.

    - Truncate category labels to 30 chars
    - Ensure series.values length matches categories length (pad with 0.0 or trim)
    - Coerce numeric strings in values to float
    - Sort scatter points by x value
    """


def infer_chart_type(spec: ChartSpec) -> ChartType:
    """Infer the best chart type when chart_type is ambiguous.

    Heuristic rules:
    - Has points → scatter
    - Single series, all positive → pie candidate
    - Multiple series → line or bar (prefer bar for ≤ 6 categories)
    """
```

### 4.3 Funnel Strategy

`python-pptx` does not have a native funnel chart type. Phase 3 renders funnel as a **descending horizontal bar** chart:

- Categories ordered from largest to smallest
- Bar colors follow theme accent gradient
- Chart title preserves "Funnel" label
- Original `chart_type: "funnel"` preserved in `ChartSpec` metadata

### 4.4 Validation Rules

| Condition | Behavior |
|-----------|----------|
| `content` is a string (not JSON) | `parse_chart_spec()` returns `None` → exporter uses text placeholder |
| `categories` and `series[*].values` length mismatch | `normalize_chart_spec()` pads/trims values |
| `chart_type: "scatter"` but no `points` | Return `None` (invalid spec) |
| Categorical chart with no `series` | Return `None` (invalid spec) |

---

## 5. PPTX Chart Rendering

**File:** `core/studio/slides/exporter.py`

### 5.1 New Layout Constants

```python
# Chart area (used when slide_type == "chart")
CHART_TOP = Inches(2.0)
CHART_LEFT = MARGIN_LEFT
CHART_WIDTH = CONTENT_WIDTH
CHART_HEIGHT = Inches(3.8)

# Caption below chart
CAPTION_TOP = Inches(6.0)
CAPTION_HEIGHT = Inches(1.0)
```

### 5.2 Updated `_render_chart()` — Native Chart Objects

Replace the Phase 2 text placeholder with actual chart rendering:

```python
def _render_chart(slide, slide_data, theme):
    """Chart slide: title + native chart or text fallback."""
    from core.studio.slides.charts import parse_chart_spec, normalize_chart_spec

    # Title (unchanged from Phase 2)
    _add_text_box(slide, slide_data.title or "",
                  left=TITLE_LEFT, top=TITLE_TOP,
                  width=TITLE_WIDTH, height=TITLE_HEIGHT,
                  font_name=theme.font_heading, font_size=Pt(32),
                  font_color=theme.colors.primary, bold=True)

    chart_el = _find_element(slide_data, "chart")
    body_el = _find_element(slide_data, "body")
    chart_rendered = False

    if chart_el and chart_el.content:
        spec = parse_chart_spec(chart_el.content)
        if spec is not None:
            spec = normalize_chart_spec(spec)
            chart_rendered = _add_chart(slide, spec, theme)

    # Fallback: text placeholder if chart parse/render failed
    if not chart_rendered and chart_el and chart_el.content:
        content = chart_el.content if isinstance(chart_el.content, str) else str(chart_el.content)
        _add_text_box(slide, f"[Chart: {content}]",
                      left=BODY_LEFT, top=BODY_TOP,
                      width=BODY_WIDTH, height=Inches(3.0),
                      font_name=theme.font_body, font_size=Pt(16),
                      font_color=theme.colors.secondary,
                      alignment=PP_ALIGN.CENTER)

    # Body/caption below chart
    if body_el and body_el.content:
        caption_top = CAPTION_TOP if chart_rendered else Inches(5.0)
        _add_text_box(slide, body_el.content,
                      left=BODY_LEFT, top=caption_top,
                      width=BODY_WIDTH, height=CAPTION_HEIGHT,
                      font_name=theme.font_body, font_size=Pt(16),
                      font_color=theme.colors.text)

    _set_slide_background(slide, theme)
```

### 5.3 Gradient Background Support

Update `_set_slide_background()` to accept the full theme object and apply gradient when specified:

```python
def _set_slide_background(slide, theme):
    """Set slide background — supports solid and gradient fills."""
    bg_hex = theme.colors.background.lstrip("#")
    if getattr(theme, "background_style", None) == "gradient":
        primary_hex = theme.colors.primary.lstrip("#")
        fill = slide.background.fill
        fill.gradient()
        fill.gradient_stops[0].color.rgb = RGBColor.from_string(bg_hex)
        fill.gradient_stops[1].color.rgb = RGBColor.from_string(primary_hex)
        fill.gradient_angle = 270  # Top to bottom
    else:
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor.from_string(bg_hex)
```

All existing renderer functions that call `_set_slide_background()` must be updated to pass the full theme object instead of just `theme.colors.background`.

### 5.4 New Helper: `_add_chart()`

```python
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.enum.chart import XL_CHART_TYPE

def _add_chart(slide, spec: "ChartSpec", theme: "SlideTheme") -> bool:
    """Add a native python-pptx chart to the slide. Returns True on success."""
    try:
        if spec.chart_type.value == "scatter":
            chart_data = XyChartData()
            series = chart_data.add_series(spec.title or "Data")
            for pt in spec.points:
                series.add_data_point(pt.x, pt.y)
            chart_type = XL_CHART_TYPE.XY_SCATTER
        else:
            chart_data = CategoryChartData()
            chart_data.categories = spec.categories
            series_list = spec.series
            if spec.chart_type == ChartType.pie and len(series_list) > 1:
                series_list = series_list[:1]  # Pie supports single series only
            for s in series_list:
                chart_data.add_series(s.name, s.values)
            chart_type = _CHART_TYPE_MAP.get(spec.chart_type.value, XL_CHART_TYPE.COLUMN_CLUSTERED)

        chart_frame = slide.shapes.add_chart(
            chart_type, CHART_LEFT, CHART_TOP, CHART_WIDTH, CHART_HEIGHT, chart_data
        )
        # Apply theme colors to chart
        chart = chart_frame.chart
        chart.has_legend = len(spec.series) > 1 or spec.chart_type.value == "pie"

        # Minimal theme application
        if chart.chart_title:
            chart.chart_title.text_frame.paragraphs[0].font.color.rgb = RGBColor.from_string(
                theme.colors.primary.lstrip("#")
            )
        # Apply theme accent as first series fill (when accessible)
        return True
    except Exception:
        return False


_CHART_TYPE_MAP = {
    "bar": XL_CHART_TYPE.COLUMN_CLUSTERED,    # Vertical columns (user-facing "bar chart")
    "line": XL_CHART_TYPE.LINE,
    "pie": XL_CHART_TYPE.PIE,
    "funnel": XL_CHART_TYPE.BAR_CLUSTERED,    # Horizontal bars; visual distinction from "bar"
}
# Product convention: "bar" renders as vertical columns (COLUMN_CLUSTERED).
# Funnel uses BAR_CLUSTERED (horizontal) for visual distinction.
```

### 5.5 Placement Rules

| Slide condition | Placement rule |
|-----------------|----------------|
| `slide_type == "chart"` with valid `ChartSpec` | Chart at `CHART_TOP/CHART_HEIGHT`, caption below at `CAPTION_TOP` |
| `slide_type == "chart"` with invalid spec | Text placeholder fallback `[Chart: ...]`, no crash |
| Any slide with chart element + body | Chart in primary zone, body below |
| Multiple chart elements | Render first valid chart, ignore extras |

### 5.6 Safety

- `_add_chart()` wraps all chart operations in try/except and returns `False` on failure
- Exporter never crashes on malformed chart payloads — always falls back to text placeholder
- Invalid chart triggers validator warning (not exporter crash)

---

## 6. Speaker Notes Quality Pass

**Files:** `core/studio/slides/notes.py` (NEW), `core/studio/prompts.py`, `core/studio/orchestrator.py`

### 6.1 Notes Quality Module

**File:** `core/studio/slides/notes.py` (NEW)

```python
from core.schemas.studio_schema import Slide, SlidesContentTree


def score_speaker_notes(slide: Slide) -> dict:
    """Score the quality of a single slide's speaker notes.

    Returns:
        {
            "word_count": int,
            "sentence_count": int,
            "is_empty": bool,
            "is_too_short": bool,   # < 15 words
            "is_too_long": bool,    # > 140 words
            "is_copy": bool,        # > 60% overlap with slide body text
            "passes": bool,         # meets quality threshold
        }
    """


def repair_speaker_notes(content_tree: SlidesContentTree) -> SlidesContentTree:
    """Post-generation repair pass for speaker notes.

    Repair triggers (applied per slide):
    - Empty/missing notes: generate template filler based on slide type and title
    - Too short (< 15 words): expand with slide-context filler sentence
    - Near-copy of slide body text (> 60% overlap): replace with reframed version
    - Title/closing slides: relaxed threshold (1 sentence, 8+ words is acceptable)

    Returns a new SlidesContentTree (does not mutate the input).
    """
```

### 6.2 Quality Thresholds

| Metric | Threshold | Exceptions |
|--------|-----------|------------|
| Min words per slide | 15 | Title/closing slides: 8 |
| Max words per slide | 140 | None |
| Min sentences per slide | 2 | Title/closing slides: 1 |
| Body text overlap | < 60% | None |
| Deck-level pass rate | >= 90% slides pass | None |
| Empty notes | 0 allowed | None |

### 6.3 Prompt Strengthening

**File:** `core/studio/prompts.py`

Update `_get_type_specific_draft_schema()` for slides to strengthen notes guidance:

```python
# Add to the existing slides draft instructions in get_draft_prompt():
"""
SPEAKER NOTES REQUIREMENTS (mandatory for every slide):
- Write 2-4 concise sentences of presenter guidance per slide
- Include at least one key talking point not visible on the slide
- Include a transition or callout for the next topic
- Do NOT repeat bullet points or slide text verbatim
- Title/closing slides may have 1-2 shorter sentences
- Target 15-60 words per slide's speaker notes
"""
```

### 6.4 Orchestrator Integration

**File:** `core/studio/orchestrator.py`

In `approve_and_generate_draft()`, after `enforce_slide_count()`:

```python
# After enforce_slide_count (existing):
if artifact.type == ArtifactType.slides:
    from core.studio.slides.generator import enforce_slide_count
    content_tree_model = enforce_slide_count(content_tree_model)

    # NEW Phase 3: notes quality repair pass
    from core.studio.slides.notes import repair_speaker_notes
    content_tree_model = repair_speaker_notes(content_tree_model)
```

This ensures every saved content tree has baseline-quality speaker notes before it reaches the export path.

---

## 7. Layout-Quality Validator v2

**File:** `core/studio/slides/validator.py`

### 7.1 Validation Layers

Phase 2 validator performs structural open-check + advisory text density warnings. Phase 3 adds enforceable quality checks:

**Layer 1 — Structural (unchanged):**
- PPTX opens cleanly via `Presentation(str(file_path))`
- Slide count matches expected count

**Layer 2 — Layout (promoted to blocking):**
- Per-shape char limit: 800 chars max
- Per-slide char limit: 1600 chars max
- Out-of-bounds shape detection: shapes with `left + width > SLIDE_WIDTH` or `top + height > SLIDE_HEIGHT`
- Minimum font size: text shapes with font size < 10pt → `layout_warnings` (advisory)
- Violations go to `layout_errors` (blocking), not `layout_warnings` (advisory)

**Layer 3 — Chart quality (advisory):**
- Chart slides (slide_type == "chart") should contain a chart shape object or explicit `[Chart: ...]` fallback marker
- Chart area is non-trivial (chart shape exists with non-zero dimensions)

**Layer 4 — Notes quality (advisory):**
- Calls `score_speaker_notes()` from `notes.py` for each slide
- Deck-level pass: >= 90% of slides meet quality threshold AND no slide has empty notes

### 7.2 Updated Function Signature

```python
def validate_pptx(
    file_path: Path,
    expected_slide_count: int | None = None,
    content_tree: "SlidesContentTree | None" = None,  # NEW — for chart/notes cross-validation
) -> Dict[str, Any]:
    """Validate a PPTX file with structural, layout, chart, and notes checks.

    Returns:
        {
            "valid": bool,               # structural integrity
            "slide_count": int,
            "has_notes": bool,
            "errors": list[str],         # structural errors
            "layout_valid": bool,        # no blocking layout violations
            "layout_warnings": list[str],# advisory layout concerns
            "layout_errors": list[str],  # blocking layout violations (NEW)
            "notes_quality_valid": bool, # deck-level notes pass (NEW)
            "chart_quality_valid": bool, # chart slides have chart objects (NEW)
            "quality_score": int,        # 0-100 overall score (NEW)
        }
    """
```

### 7.3 Quality Score Calculation

```python
# Scoring weights (total = 100)
score = 100
if not layout_valid:
    score -= 40  # Layout violations are severe
score -= min(len(layout_warnings), 4) * 5  # Advisory warnings cost 5 each, capped at 20
if not notes_quality_valid:
    score -= 20
if not chart_quality_valid:
    score -= 20
quality_score = max(0, min(100, score))
```

### 7.4 Blocking Policy

`layout_valid` always reflects ground truth (violations exist or not). The `strict_layout` parameter controls whether the orchestrator treats `layout_valid=False` as blocking.

Export completion in `orchestrator.py` requires:

| Check | Blocking? | Behavior on Failure |
|-------|-----------|---------------------|
| `valid` | **Yes** | `status=failed` |
| `layout_valid` | **Conditional** | Blocks when `strict_layout=True`; advisory when `False` |
| `notes_quality_valid` | No (advisory) | Warning in `validator_results`, export completes |
| `chart_quality_valid` | No (advisory) | Warning in `validator_results`, export completes |

API responses include the `strict_layout` value in `validator_results` so clients can distinguish policy from truth.

**Rationale for advisory notes/chart checks:** LLM-generated content has inherent variability. Making notes and chart quality blocking in Phase 3 risks false positive export failures. The notes repair pass in the draft path mitigates most quality issues upstream. If quality consistently passes in practice, Phase 4 can promote these to blocking.

---

## 8. Orchestrator Changes

**File:** `core/studio/orchestrator.py`

### 8.1 Draft Path Update

After `enforce_slide_count()`, add notes repair:

```python
# In approve_and_generate_draft(), after enforce_slide_count:
if artifact.type == ArtifactType.slides:
    from core.studio.slides.notes import repair_speaker_notes
    content_tree_model = repair_speaker_notes(content_tree_model)
```

The repaired notes are included in the revision snapshot, so they persist correctly.

### 8.2 Export Path Update

Before calling the exporter, apply non-persisting notes repair on a copy. This ensures even Phase 2 artifacts get quality notes on export without modifying stored revisions:

```python
# Non-persisting notes repair for pre-Phase3 artifacts
from core.studio.slides.notes import repair_speaker_notes
export_content_tree = repair_speaker_notes(content_tree_model)  # copy, not saved
export_to_pptx(export_content_tree, theme, output_path)
```

Pass `content_tree` to the validator so chart/notes quality checks can cross-reference the source data:

```python
validation = validate_pptx(
    output_path,
    expected_slide_count=len(content_tree_model.slides),
    content_tree=export_content_tree,  # Validate what was actually exported
)
```

Update the validation check in `export_artifact()` to use blocking policy with `strict_layout`:

```python
# Current Phase 2 logic:
if validation["valid"]:
    export_job.status = ExportStatus.completed
else:
    export_job.status = ExportStatus.failed

# Phase 3 update — layout_valid conditional on strict_layout:
layout_ok = validation.get("layout_valid", True) or not strict_layout
if validation["valid"] and layout_ok:
    export_job.status = ExportStatus.completed
    export_job.output_uri = str(output_path)
    export_job.file_size_bytes = output_path.stat().st_size
    validation["strict_layout"] = strict_layout  # Record policy in results
    export_job.validator_results = validation
    export_job.completed_at = datetime.now(timezone.utc)
else:
    export_job.status = ExportStatus.failed
    all_errors = validation.get("errors", []) + validation.get("layout_errors", [])
    export_job.error = "; ".join(all_errors) if all_errors else "Quality validation failed"
    validation["strict_layout"] = strict_layout
    export_job.validator_results = validation
    export_job.completed_at = datetime.now(timezone.utc)
```

### 8.3 Strict Layout Parameter

Pass `strict_layout` from the export request through to the validator:

```python
async def export_artifact(
    self,
    artifact_id: str,
    export_format: "ExportFormat",
    theme_id: Optional[str] = None,
    strict_layout: bool = False,       # NEW — default preserves Phase 2 advisory behavior
) -> Dict[str, Any]:
```

When `strict_layout=True`, layout violations block export. When `False` (default), layout issues are advisory-only, matching Phase 2 behavior.

---

## 9. Router Changes

**File:** `routers/studio.py`

### 9.1 Export Request Model Update

```python
class ExportArtifactRequest(BaseModel):
    format: str = "pptx"
    theme_id: Optional[str] = None
    strict_layout: bool = False   # NEW — default preserves Phase 2 advisory behavior
```

### 9.2 Export Endpoint Update

Pass `strict_layout` through to orchestrator:

```python
@router.post("/{artifact_id}/export")
async def export_artifact(artifact_id: str, request: ExportArtifactRequest):
    _validate_artifact_id(artifact_id)
    # ... existing validation ...
    result = await orchestrator.export_artifact(
        artifact_id=artifact_id,
        export_format=export_format,
        theme_id=request.theme_id,
        strict_layout=request.strict_layout,  # NEW
    )
    return result
```

### 9.3 Theme Listing Controls

Update `GET /studio/themes` to support query params:

```python
@router.get("/themes")
async def list_themes_endpoint(
    include_variants: bool = False,   # NEW
    base_id: Optional[str] = None,    # NEW
    limit: Optional[int] = None,      # NEW
):
    """List available themes. Defaults to base themes only for backward compatibility."""
    from core.studio.slides.themes import list_themes
    themes = list_themes(
        include_variants=include_variants,
        base_id=base_id,
        limit=limit,
    )
    return [t.model_dump() for t in themes]
```

Default behavior (`include_variants=False`, no `base_id`, no `limit`) returns 16 base themes — a superset of Phase 2's 8. Existing clients unaffected.

---

## 10. Prompt Improvements

**File:** `core/studio/prompts.py`

### 10.1 Chart JSON Schema Guidance

Add to `_get_type_specific_draft_schema()` for slides, in the element type descriptions:

```python
"""
For elements with type="chart", content MUST be a structured JSON object:
{
  "chart_type": "bar" | "line" | "pie" | "funnel" | "scatter",
  "title": "Chart Title",
  "categories": ["Label1", "Label2", ...],
  "series": [{"name": "Series Name", "values": [1.0, 2.0, ...]}],
  "x_label": "X Axis Label",
  "y_label": "Y Axis Label"
}
For scatter charts, use "points": [{"x": 1.0, "y": 2.0}, ...] instead of categories/series.
Do NOT use plain text strings for chart content — always use structured JSON.
"""
```

### 10.2 Notes Rubric

Add to the existing speaker notes section in `_get_type_specific_draft_schema()`:

```python
"""
SPEAKER NOTES REQUIREMENTS (mandatory for every slide):
- Write 2-4 concise sentences of presenter guidance per slide
- Include at least one key talking point not visible on the slide
- Include a transition sentence or audience callout
- Do NOT repeat bullet points or body text verbatim in notes
- Title/closing slides may have 1-2 shorter sentences
- Target 15-60 words per slide's speaker notes
"""
```

### 10.3 Deterministic Sequence Hints

No changes needed — `get_draft_prompt_with_sequence()` already injects planned slide sequence into the draft prompt. Phase 3 appends the chart schema and notes rubric to the same prompt, so sequence hints + quality guidance are combined.

---

## 11. Backward Compatibility

| Area | Strategy |
|------|----------|
| **Existing artifacts** | New `SlideTheme` fields are `Optional[None]`; existing `theme_id` values (`corporate-blue`, etc.) remain valid |
| **Existing chart content** | `parse_chart_spec()` returns `None` for string content → exporter falls back to Phase 2 text placeholder behavior |
| **Existing API clients** | `POST /export` without `strict_layout` preserves Phase 2 advisory behavior; clients opt in to strict mode with `strict_layout=true` |
| **Theme listing** | `GET /studio/themes` without params returns base themes only (superset of Phase 2's 8) |
| **Validator results** | New keys (`layout_errors`, `notes_quality_valid`, `chart_quality_valid`, `quality_score`) are additive; existing keys unchanged |
| **Phase 2 tests** | Tests checking `layout_warnings` remain valid; tests checking export `status=completed` updated where validator behavior intentionally changes from warning to blocking |

---

## 12. Test Plan

Tests are organized into **unit tests** (model/logic correctness), **component tests** (exporter/validator behavior), **router tests** (HTTP endpoint wiring), **acceptance tests** (P04 gate criteria), and **integration tests** (cross-component flows).

### `tests/test_studio_slides_theme_variants.py` — 14 tests (NEW)

| Test | What It Verifies |
|------|-----------------|
| `test_generate_variant_deterministic` | Same base_id + seed always produces same variant |
| `test_generate_variant_different_seeds` | Different seeds produce different color palettes |
| `test_variant_id_format` | ID follows `{base}--v{NN}` format |
| `test_variant_has_base_theme_id` | `base_theme_id` field matches source base |
| `test_variant_has_variant_seed` | `variant_seed` field matches input seed |
| `test_variant_contrast_validation` | Text-on-background luminance ratio >= 4.5:1 |
| `test_variant_contrast_retry` | Low-contrast seed retries and produces valid output |
| `test_variant_hex_colors_valid` | All 6 color fields match `#[0-9A-Fa-f]{6}` |
| `test_variant_fonts_from_allowlist` | Font heading and body are from the font allow-list |
| `test_variant_background_style_valid` | `background_style` is one of: solid, gradient, subtle_pattern |
| `test_list_themes_with_variants_count` | `list_themes(include_variants=True)` returns 112+ themes |
| `test_list_themes_base_only` | `list_themes(include_variants=False)` returns 16 themes |
| `test_list_themes_filter_by_base_id` | `list_themes(base_id="tech-dark")` returns base + 6 variants (7 total) |
| `test_unknown_base_raises_error` | `generate_theme_variant("nonexistent", 1)` raises ValueError |

### `tests/test_studio_slides_charts.py` — 14 tests (NEW)

| Test | What It Verifies |
|------|-----------------|
| `test_parse_bar_chart_spec` | Valid bar chart dict → ChartSpec with correct type/categories/series |
| `test_parse_line_chart_spec` | Valid line chart dict → ChartSpec |
| `test_parse_pie_chart_spec` | Valid pie chart dict → ChartSpec |
| `test_parse_scatter_chart_spec` | Valid scatter dict with points → ChartSpec |
| `test_parse_funnel_chart_spec` | Funnel dict → ChartSpec with chart_type="funnel" |
| `test_parse_string_returns_none` | Plain string content → returns None |
| `test_parse_empty_dict_returns_none` | Empty dict → returns None |
| `test_parse_missing_chart_type_infers` | Dict without chart_type but with categories/series → inferred as bar or pie |
| `test_normalize_truncates_categories` | Categories longer than 30 chars are truncated |
| `test_normalize_pads_values` | Series with fewer values than categories → padded with 0.0 |
| `test_normalize_trims_values` | Series with more values than categories → trimmed |
| `test_normalize_sorts_scatter_points` | Scatter points sorted by x value |
| `test_infer_chart_type_scatter` | Spec with points → inferred as scatter |
| `test_infer_chart_type_pie` | Single series, small categories → inferred as pie |

### `tests/test_studio_slides_notes.py` — 10 tests (NEW)

| Test | What It Verifies |
|------|-----------------|
| `test_score_empty_notes` | Empty speaker_notes → `is_empty=True`, `passes=False` |
| `test_score_too_short` | 5-word notes → `is_too_short=True`, `passes=False` |
| `test_score_too_long` | 200-word notes → `is_too_long=True`, `passes=False` |
| `test_score_good_notes` | 30-word, 2-sentence notes → `passes=True` |
| `test_score_copy_detection` | Notes that repeat slide body → `is_copy=True`, `passes=False` |
| `test_score_title_slide_relaxed` | Title slide with 1 short sentence → `passes=True` |
| `test_repair_empty_notes` | Slide with no notes → repaired to template filler |
| `test_repair_too_short` | Short notes → expanded with context sentence |
| `test_repair_preserves_good_notes` | Good notes → unchanged |
| `test_repair_returns_new_tree` | Input content tree not mutated |

### `tests/test_studio_slides_validator.py` — 15 tests (NEW)

| Test | What It Verifies |
|------|-----------------|
| `test_valid_pptx_passes` | Well-formed PPTX → `valid=True`, `layout_valid=True` |
| `test_invalid_file_fails` | Non-PPTX file → `valid=False`, error message |
| `test_slide_count_mismatch` | Expected 10, actual 5 → error in `errors` |
| `test_block_char_overflow` | Shape with 1000+ chars → `layout_valid=False`, entry in `layout_errors` |
| `test_slide_char_overflow` | Slide total 2000+ chars → `layout_valid=False`, entry in `layout_errors` |
| `test_out_of_bounds_shape` | Shape positioned outside slide dimensions → `layout_errors` |
| `test_chart_quality_valid_with_chart` | Chart slide with chart shape → `chart_quality_valid=True` |
| `test_chart_quality_valid_with_fallback` | Chart slide with `[Chart: ...]` text → `chart_quality_valid=True` |
| `test_chart_quality_invalid` | Chart slide with neither chart nor fallback → `chart_quality_valid=False` |
| `test_notes_quality_valid` | Deck with good notes → `notes_quality_valid=True` |
| `test_notes_quality_invalid` | Deck with empty notes → `notes_quality_valid=False` |
| `test_quality_score_perfect` | All checks pass → `quality_score` >= 90 |
| `test_quality_score_degraded` | Layout warnings present → `quality_score` < 90 |
| `test_small_font_warning` | Text shape with 8pt font → entry in `layout_warnings` |
| `test_result_has_all_keys` | Result dict contains all 10 expected keys |

### `tests/test_studio_slides_themes.py` — +6 tests (MODIFY)

| Test | What It Verifies |
|------|-----------------|
| `test_16_curated_bases_load` | `list_themes()` returns 16 base themes |
| `test_new_base_ids_exist` | Each of the 8 new base IDs is accessible via `get_theme()` |
| `test_new_bases_have_required_colors` | New bases have all 6 color fields, hex format |
| `test_new_bases_have_fonts` | New bases have non-empty heading and body fonts |
| `test_list_themes_include_variants_returns_more` | `list_themes(include_variants=True)` > `list_themes()` |
| `test_variant_metadata_roundtrip` | `SlideTheme` with `base_theme_id`/`variant_seed`/`background_style` round-trips |

### `tests/test_studio_slides_exporter.py` — +10 tests (MODIFY)

| Test | What It Verifies |
|------|-----------------|
| `test_export_chart_bar_native` | Bar chart spec → PPTX contains chart shape (not just text) |
| `test_export_chart_line_native` | Line chart spec → PPTX contains chart shape |
| `test_export_chart_pie_native` | Pie chart spec → PPTX contains chart shape |
| `test_export_chart_scatter_native` | Scatter spec with points → PPTX contains chart shape |
| `test_export_chart_funnel_fallback` | Funnel spec → rendered as bar chart shape |
| `test_export_chart_invalid_fallback` | Invalid chart content → text placeholder, no crash |
| `test_export_chart_string_fallback` | String chart content → text placeholder (Phase 2 behavior) |
| `test_export_chart_pie_multi_series` | Pie with 3 series → only first series rendered, no crash |
| `test_export_gradient_background` | Theme with gradient background_style → PPTX slide has gradient fill |
| `test_export_with_variant_theme` | Variant theme ID → valid PPTX with variant colors applied |

### `tests/test_studio_export_router.py` — +4 tests (MODIFY)

| Test | What It Verifies |
|------|-----------------|
| `test_export_strict_layout_failure` | `POST /export` with `strict_layout=true` on overflow deck → 200 with `status=failed` |
| `test_export_strict_layout_opt_out` | `POST /export` with `strict_layout=false` → layout issues are advisory |
| `test_list_themes_with_variants` | `GET /studio/themes?include_variants=true` returns 112+ themes |
| `test_list_themes_filter_base_id` | `GET /studio/themes?base_id=corporate-blue` returns 7 themes (1 base + 6 variants) |

### Acceptance Tests — `tests/acceptance/p04_forge/test_exports_open_and_render.py` — +4 tests (MODIFY)

Continue from existing `test_17`. Add:

| Test | What It Verifies |
|------|-----------------|
| `test_18_theme_catalog_reaches_100_plus` | `list_themes(include_variants=True)` returns >= 100 themes |
| `test_19_chart_slide_renders_native_chart` | Export a deck with bar chart spec → PPTX has chart shape object |
| `test_20_notes_quality_passes_baseline` | `repair_speaker_notes()` on sample deck → >= 90% slides pass `score_speaker_notes()` |
| `test_21_layout_quality_blocks_bad_export` | Export deck with 2500-char body → export `status=failed` with `layout_valid=False` |

### Integration Tests — `tests/integration/test_forge_research_to_slides.py` — +4 tests (MODIFY)

Continue from existing `test_13`. Add:

| Test | What It Verifies |
|------|-----------------|
| `test_14_outline_to_draft_with_notes_repair` | Draft path applies notes repair → saved content tree has no empty notes |
| `test_15_chart_payload_to_export_pipeline` | Structured chart data in mock LLM response → export succeeds with chart shape |
| `test_16_variant_theme_export_pipeline` | Export with variant theme ID (`corporate-blue--v01`) → `status=completed` |
| `test_17_quality_rejection_preserves_artifact_state` | Failed strict export → artifact content_tree and revision_head_id unchanged |

### Test Count Summary

| Test File | New Tests | Category |
|-----------|-----------|----------|
| `test_studio_slides_theme_variants.py` (NEW) | 14 | Unit |
| `test_studio_slides_charts.py` (NEW) | 14 | Unit |
| `test_studio_slides_notes.py` (NEW) | 10 | Unit |
| `test_studio_slides_validator.py` (NEW) | 15 | Unit |
| `test_studio_slides_themes.py` (MODIFY) | +6 | Unit |
| `test_studio_slides_exporter.py` (MODIFY) | +10 | Component |
| `test_studio_export_router.py` (MODIFY) | +4 | Router |
| `test_exports_open_and_render.py` (MODIFY) | +4 | Acceptance |
| `test_forge_research_to_slides.py` (MODIFY) | +4 | Integration |
| **Total new tests** | **81** | |
| Existing Phase 1+2 tests (unchanged) | 143+ | |
| **Combined total** | **224+** | |

### Gate Commands

```bash
# Phase 3 new unit/component tests
uv run pytest tests/test_studio_slides_theme_variants.py tests/test_studio_slides_charts.py tests/test_studio_slides_notes.py tests/test_studio_slides_validator.py -q

# Modified slide/export tests
uv run pytest tests/test_studio_slides_themes.py tests/test_studio_slides_exporter.py tests/test_studio_export_router.py -q

# Acceptance + integration gates
uv run pytest tests/acceptance/p04_forge/test_exports_open_and_render.py tests/integration/test_forge_research_to_slides.py -v

# Baseline non-regression
scripts/test_all.sh quick
```

---

## 13. Day-by-Day Execution Sequence

### Day 9: Theme Bundles + Chart and Notes Foundations

1. Update `core/schemas/studio_schema.py` — add `ChartType`, `ChartSeries`, `ScatterPoint`, `ChartSpec` models; add `base_theme_id`, `variant_seed`, `background_style` fields to `SlideTheme`
2. Expand `core/studio/slides/themes.py` — add 8 new curated base themes, implement `generate_theme_variant()` with HSL rotation + contrast validation, update `list_themes()`/`get_theme_ids()` signatures
3. Create `core/studio/slides/charts.py` — `parse_chart_spec()`, `normalize_chart_spec()`, `infer_chart_type()`
4. Create `core/studio/slides/notes.py` — `score_speaker_notes()`, `repair_speaker_notes()`
5. Update `core/studio/prompts.py` — chart JSON schema guidance in draft prompt, stronger notes rubric
6. Write tests:
   - `tests/test_studio_slides_theme_variants.py` (14 tests)
   - `tests/test_studio_slides_charts.py` (14 tests)
   - `tests/test_studio_slides_notes.py` (10 tests)
   - Update `tests/test_studio_slides_themes.py` (+6 tests)
7. Run targeted suite:

```bash
uv run pytest tests/test_studio_slides_theme_variants.py tests/test_studio_slides_charts.py tests/test_studio_slides_notes.py tests/test_studio_slides_themes.py -q
```

**Day 9 exit gate:** All 44 new tests pass (14 + 14 + 10 + 6). Schema backward compatibility verified (existing schema tests still pass). Theme catalog returns 112+ with `include_variants=True`.

### Day 10: Exporter + Validator + Pipeline Enforcement

1. Update `core/studio/slides/exporter.py` — add chart layout constants, `_add_chart()` helper, replace `_render_chart()` with native chart rendering
2. Upgrade `core/studio/slides/validator.py` — add `layout_errors`, out-of-bounds detection, chart quality check, notes quality check, quality score
3. Update `core/studio/orchestrator.py` — add `repair_speaker_notes()` in draft path after `enforce_slide_count()`, add `strict_layout` parameter to `export_artifact()`, enforce blocking layout validation in export status decision
4. Update `routers/studio.py` — add `strict_layout` to `ExportArtifactRequest`, add `include_variants`/`base_id`/`limit` params to theme listing endpoint
5. Write tests:
   - `tests/test_studio_slides_validator.py` (15 tests)
   - Update `tests/test_studio_slides_exporter.py` (+10 tests)
   - Update `tests/test_studio_export_router.py` (+4 tests)
   - Update acceptance tests (+4 tests: test_18 through test_21)
   - Update integration tests (+4 tests: test_14 through test_17)
6. Run full Phase 3 test matrix + baseline:

```bash
# All Phase 3 tests
uv run pytest tests/test_studio_slides_theme_variants.py tests/test_studio_slides_charts.py tests/test_studio_slides_notes.py tests/test_studio_slides_validator.py tests/test_studio_slides_themes.py tests/test_studio_slides_exporter.py tests/test_studio_export_router.py -v

# Acceptance + integration
uv run pytest tests/acceptance/p04_forge/ tests/integration/test_forge_research_to_slides.py -v

# Baseline
scripts/test_all.sh quick
```

7. Manual spot-check:

```bash
uv run api.py &

# Create + approve + export with chart data and variant theme
curl -X POST http://localhost:8000/api/studio/slides \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create a 10-slide pitch deck with revenue charts"}'

curl -X POST http://localhost:8000/api/studio/{artifact_id}/outline/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'

curl -X POST http://localhost:8000/api/studio/{artifact_id}/export \
  -H "Content-Type: application/json" \
  -d '{"format": "pptx", "theme_id": "corporate-blue--v01"}'

# Verify 100+ themes
curl "http://localhost:8000/api/studio/themes?include_variants=true" | python -c "import json,sys; print(len(json.load(sys.stdin)))"

# Download and verify chart in PPTX
curl -o output.pptx http://localhost:8000/api/studio/{artifact_id}/exports/{export_job_id}/download
open output.pptx
```

**Day 10 exit gate:** All 81 new tests pass. Full pipeline works end-to-end. Strict quality validation active. PPTX with charts opens in viewer. Baseline regression green.

---

## 14. Exit Criteria

| # | Criterion | How to Verify |
|---|-----------|---------------|
| 1 | Theme system provides 112+ available themes (16 bases + variants) | `test_18_theme_catalog_reaches_100_plus` |
| 2 | Existing Phase 2 theme IDs remain valid and resolve correctly | `tests/test_studio_slides_themes.py` (existing tests still pass) |
| 3 | Chart types bar/line/pie/funnel/scatter are accepted and normalized | `tests/test_studio_slides_charts.py` |
| 4 | Chart slides render native chart objects in PPTX | `test_19_chart_slide_renders_native_chart` + exporter tests |
| 5 | Invalid chart payloads fail gracefully (text fallback, no crash) | `test_export_chart_invalid_fallback` + `test_export_chart_string_fallback` |
| 6 | Speaker notes meet quality baseline after repair pass | `test_20_notes_quality_passes_baseline` |
| 7 | Layout-quality validator detects overflow/unreadable layouts | `tests/test_studio_slides_validator.py` |
| 8 | Layout violations block export under strict mode | `test_21_layout_quality_blocks_bad_export` |
| 9 | Export lifecycle records detailed validator results (10 keys) | `test_result_has_all_keys` + router tests |
| 10 | Artifact/revision state remains consistent on failed export | `test_17_quality_rejection_preserves_artifact_state` |
| 11 | Acceptance and integration gate files remain green | `pytest tests/acceptance/p04_forge/ tests/integration/test_forge_research_to_slides.py -v` |
| 12 | No regression in baseline suite | `scripts/test_all.sh quick` |

---

## 15. Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | Theme variant generation creates low-contrast outputs | Medium | High | WCAG AA contrast check (4.5:1 ratio) + deterministic text lightness adjustment (`_fix_contrast()`, up to 3 steps) |
| 2 | Funnel chart lacks native visual fidelity | Medium | Medium | Descending horizontal bar fallback with explicit "Funnel" label; document limitation |
| 3 | Strict layout validator introduces false positives on LLM output | Medium | High | Conservative thresholds (800/1600 chars from Phase 2); notes/chart quality advisory not blocking |
| 4 | Notes repair creates repetitive boilerplate | Medium | Medium | Template variation per slide type; lexical diversity check in `score_speaker_notes()` |
| 5 | Backward behavior shift (warning → blocking layout) surprises clients | Medium | Medium | `strict_layout` request parameter allows opt-out; clear error messages in response |
| 6 | Chart payload variability from LLM causes parse failures | High | Medium | `parse_chart_spec()` returns `None` for unparseable content; exporter always has text fallback |
| 7 | Additional validation increases export latency | Low | Low | O(n shapes) checks only; no heavyweight rendering analysis; typical 8-15 slide decks process in < 1 second |

---

## 16. Phase 4+ Extension Hooks

Phase 3 leaves clean extension points for later phases:

| Hook | Where | Future Use |
|------|-------|------------|
| `ChartSpec` / `ChartType` models | `core/schemas/studio_schema.py` | Reuse for Sheets visualization and HTML interactive charts (Phase 5) |
| `generate_theme_variant()` | `core/studio/slides/themes.py` | Reuse for document style packs and UI preview theming |
| `score_speaker_notes()` / `repair_speaker_notes()` | `core/studio/slides/notes.py` | Reuse in edit-loop quality checks (Phase 6) |
| `validate_pptx()` result contract | `core/studio/slides/validator.py` | Reuse for docs/sheets quality validators; feed telemetry dashboards |
| `strict_layout` export option | `routers/studio.py` | Foundation for per-format quality policy switches (PDF, DOCX) |
| `_add_chart()` helper | `core/studio/slides/exporter.py` | Extend to support stacked bar, area, combo charts |

---

## Appendix A: Key Existing Files Referenced

| File | What It Provides |
|------|-----------------|
| `core/schemas/studio_schema.py` | All Pydantic models: `Artifact`, `Revision`, `Outline`, content trees, `ExportJob`, `SlideTheme`, validation helpers |
| `core/studio/orchestrator.py` | `ForgeOrchestrator` with `generate_outline()`, `approve_and_generate_draft()`, `reject_outline()`, `export_artifact()` |
| `core/studio/storage.py` | `StudioStorage` with artifact + revision + export job CRUD methods |
| `core/studio/prompts.py` | `get_outline_prompt()`, `get_draft_prompt()`, `get_draft_prompt_with_sequence()`, type-specific guidance |
| `core/studio/slides/themes.py` | 8 curated themes, `get_theme()`, `list_themes()`, `get_theme_ids()` |
| `core/studio/slides/exporter.py` | 10 renderer functions + `export_to_pptx()`, layout constants, helper functions |
| `core/studio/slides/validator.py` | `validate_pptx()` with structural + layout heuristic checks |
| `core/studio/slides/generator.py` | `compute_seed()`, `clamp_slide_count()`, `plan_slide_sequence()`, `enforce_slide_count()` |
| `core/studio/slides/types.py` | `SLIDE_TYPES`, `ELEMENT_TYPES`, `SLIDE_TYPE_ELEMENTS`, `NARRATIVE_ARC` |
| `routers/studio.py` | 14 endpoints, `ExportArtifactRequest`, `_validate_artifact_id()`, route ordering |

## Appendix B: Example Chart Slide JSON (Phase 3)

```json
{
  "id": "s6",
  "slide_type": "chart",
  "title": "Revenue Momentum",
  "elements": [
    {
      "id": "e8",
      "type": "chart",
      "content": {
        "chart_type": "line",
        "title": "ARR Growth",
        "categories": ["Q1", "Q2", "Q3", "Q4"],
        "series": [
          {"name": "ARR", "values": [0.8, 1.4, 2.1, 3.0]}
        ],
        "x_label": "Quarter",
        "y_label": "USD (Millions)"
      }
    },
    {
      "id": "e9",
      "type": "body",
      "content": "ARR grew 3.75x over 12 months with improving quarter-over-quarter acceleration."
    }
  ],
  "speaker_notes": "Start by orienting the audience to the ARR axis. Emphasize acceleration from Q2 onward and connect it to pipeline quality, then transition to forecasting confidence."
}
```

## Appendix C: Example Validator Result (Strict Mode, All Checks Pass)

```json
{
  "valid": true,
  "slide_count": 10,
  "has_notes": true,
  "errors": [],
  "layout_valid": true,
  "layout_warnings": [],
  "layout_errors": [],
  "notes_quality_valid": true,
  "chart_quality_valid": true,
  "quality_score": 95,
  "strict_layout": true
}
```

## Appendix D: Example Validator Result (Export Blocked)

```json
{
  "valid": true,
  "slide_count": 10,
  "has_notes": true,
  "errors": [],
  "layout_valid": false,
  "layout_warnings": ["Slide 3: total text density exceeds 1600 chars (1820 chars)"],
  "layout_errors": ["Slide 5: text block exceeds 800 chars (1050 chars)"],
  "notes_quality_valid": true,
  "chart_quality_valid": false,
  "quality_score": 35,
  "strict_layout": true
}
```

In this example, the export would fail with `status=failed` because `layout_valid=false` and `strict_layout=true` (blocking). The `chart_quality_valid=false` is advisory and would not independently block the export. If `strict_layout` were `false`, the layout violation would be advisory and the export would complete.
