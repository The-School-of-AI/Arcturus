# Design: XLSX Visual Polish v2 — Corporate Palettes & Bug Fixes

**Date:** 2026-03-02
**Branch:** `feature/p04-days11-15-forge`
**Status:** Approved

## Goal

Replace the 6 saturated hardcoded XLSX palettes with 3 modern corporate palettes (muted, desaturated, consultant-grade), add contrast control, and fix the top 3 visual bugs.

## Scope

- 3 new palettes with `header_contrast` field (Approach B)
- Fix: column width truncation
- Fix: pie chart duplicate legend labels
- Fix: decimal precision for financial keywords (MRR, ARR, etc.)
- Deferred: KPI mixed-unit totals, data bars on mixed columns, chart type semantic awareness

---

## 1. Palette Architecture

### Updated `SheetPalette` dataclass

Add one field to the existing frozen dataclass:

```python
header_contrast: str  # "light-on-dark" or "dark-on-light"
```

This controls:
- Header text color (white vs dark)
- Conditional formatting fill intensity
- KPI tile styling adjustments

### The 3 Palettes

| Field | Slate Executive | Iron Neutral | Sand Warm |
|-------|----------------|--------------|-----------|
| `id` | `slate-executive` | `iron-neutral` | `sand-warm` |
| `name` | `Slate Executive` | `Iron Neutral` | `Sand Warm` |
| `primary` | `2D3748` | `1F2937` | `44403C` |
| `secondary` | `4A5568` | `374151` | `57534E` |
| `accent` | `4A7AB5` | `6B7280` | `B08D57` |
| `background` | `F7FAFC` | `F9FAFB` | `FAF9F6` |
| `text` | `1A202C` | `111827` | `292524` |
| `header_text` | `FFFFFF` | `FFFFFF` | `FFFFFF` |
| `zebra` | `EDF2F7` | `F3F4F6` | `F5F5F4` |
| `subtotal` | `E2E8F0` | `E5E7EB` | `E7E5E4` |
| `trend_up` | `C6DAF0` | `D1D5DB` | `E8DCCC` |
| `trend_down` | `FED7D7` | `FEE2E2` | `FECACA` |
| `trend_flat` | `E2E8F0` | `E5E7EB` | `E7E5E4` |
| `header_contrast` | `light-on-dark` | `light-on-dark` | `light-on-dark` |

Design rationale:
- All use white-on-dark headers (most professional for financial spreadsheets)
- Zebra stripes are extremely subtle (~2% contrast from background)
- Trend colors are desaturated pastels, not saturated red/green
- `dark-on-light` exists as a future extension point

### Contrast usage in formatting code

When `header_contrast == "light-on-dark"`:
- Conditional formatting uses lighter fills (current behavior, appropriate for dark headers)
- KPI tile labels use `header_text` on `secondary` fill

When `header_contrast == "dark-on-light"` (future):
- Conditional formatting uses slightly stronger fills
- KPI tile labels use `text` on lighter fill

---

## 2. Column Width Fix

**Problem:** `max(width / 7, 8)` at line 714 ignores header text length. Headers like "Starting Customers" get truncated.

**Fix:** Combine pixel-based width with header text length and data content width:

```python
# When column_widths provided:
header_len = len(str(tab.headers[col_idx - 1])) + 4
max_data_len = max(
    (len(str(row[col_idx - 1]))
     for row in tab.rows
     if col_idx - 1 < len(row) and row[col_idx - 1] is not None),
    default=0,
)
data_width = min(max_data_len + 2, 50)  # cap at 50 to prevent absurd widths
ws.column_dimensions[col_letter].width = max(width / 7, header_len, data_width, 10)
```

The fallback path (no `column_widths`) remains unchanged: `max(len(str(header)) + 4, 12)`.

---

## 3. Pie Chart Duplicate Label Fix

**Problem:** `_infer_chart_spec` picks `pie` when `unique_categories <= 8`, but doesn't check for duplicate category labels. When Column A has "General & Growth" repeated 6 times, the legend shows the same label for each slice.

**Fix:** Add a uniqueness ratio check in `_infer_chart_spec`:

```python
if len(unique_categories) <= 8:
    # Pie only if categories are mostly unique (avoids duplicate legend labels)
    if len(unique_categories) >= len(cat_values) * 0.7:
        chart_type = "pie"
    else:
        chart_type = "bar"
else:
    chart_type = "bar"
```

Threshold: 70% unique. If a 16-row tab has only 3 unique categories, it gets a bar chart instead.

---

## 4. Decimal Precision Keywords

**Problem:** `_CURRENCY_KEYWORDS` misses common financial terms. Headers like "Total MRR" get no number format, showing values like `17433.81559`.

**Fix:** Expand both keyword sets:

```python
_CURRENCY_KEYWORDS = {
    "amount", "revenue", "cost", "price", "budget", "profit", "expense",
    "sales", "mrr", "arr", "arpu", "cltv", "ltv", "income", "balance",
    "salary", "spend", "fee", "total",
}
_PERCENT_KEYWORDS = {"pct", "percent", "%", "growth", "rate", "ratio", "margin", "churn"}
```

---

## 5. Prompt Updates

Update palette hint options in 2 locations in `core/studio/prompts.py`:
- Line 270 (draft prompt): `"palette_hint": "slate-executive|iron-neutral|sand-warm"`
- Line 350 (visual repair prompt): same

---

## 6. Test Updates

- Update `test_xlsx_palette_hint_overrides_hash` to use a new palette ID
- Update `test_xlsx_conditional_formatting_uses_palette_colors` to use a new palette ID
- Update `test_xlsx_palette_selection_is_deterministic` (no change needed, works with any palette count)
- Add `test_xlsx_palette_has_header_contrast_field` verifying all palettes have the field
- Add `test_xlsx_column_width_respects_header_length` verifying headers aren't truncated
- Add `test_xlsx_pie_chart_skipped_for_duplicate_categories` verifying bar fallback

---

## Files Changed

| File | Changes |
|------|---------|
| `core/studio/sheets/exporter_xlsx.py` | Replace 6 palettes with 3, add `header_contrast` field, fix column widths, fix pie chart heuristic, expand keywords |
| `core/studio/prompts.py` | Update palette hint options (2 locations) |
| `tests/test_studio_sheets_exporter_xlsx.py` | Update 2 palette-specific tests, add 3 new tests |

---

## Verification

```bash
# 1. Run affected tests
PYTHONPATH=. uv run python -m pytest -q tests/test_studio_sheets_exporter_xlsx.py tests/test_studio_sheets_validator.py -v

# 2. Run full backend suite
PYTHONPATH=. uv run python -m pytest -q tests -m "not integration and not external"

# 3. Visual smoke test — generate one XLSX per palette
PYTHONPATH=. uv run python -c "
from core.schemas.studio_schema import SheetContentTree, SheetTab
from core.studio.sheets.exporter_xlsx import export_to_xlsx, _PALETTES
from pathlib import Path
for p in _PALETTES:
    tree = SheetContentTree(
        workbook_title=f'Test {p.name}',
        tabs=[SheetTab(id='t1', name='Data',
            headers=['Month','Revenue','Cost','Growth Rate'],
            rows=[['Jan',100,80,0.05],['Feb',200,150,0.08],['Mar',300,220,0.12],['','Total',450,'']],
            formulas={}, column_widths=[100,80,80,100])],
        metadata={'palette_hint': p.id, 'visual_profile': 'balanced'})
    export_to_xlsx(tree, Path(f'/tmp/test_{p.id}.xlsx'))
    print(f'Exported: {p.id}')
"
```
