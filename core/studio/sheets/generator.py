"""Sheet content tree normalization — deterministic post-generation quality pass."""

import re
from typing import Any, Dict, List, Set

from core.schemas.studio_schema import SheetAnalysisReport, SheetContentTree, SheetTab
from core.studio.sheets.formulas import validate_tab_formulas

# Patterns that indicate placeholder content
_PLACEHOLDER_PATTERNS = re.compile(
    r"^(TBD|TODO|Lorem ipsum|To be added|N/A|PLACEHOLDER|xxx|…)$",
    re.IGNORECASE,
)
_FALLBACK_TEXT = "—"
_DEFAULT_COLUMN_WIDTH = 100
_DEFAULT_VISUAL_PROFILE = "balanced"
_VALID_VISUAL_PROFILES = {"balanced", "conservative", "max"}
_VALID_CHART_TYPES = {"bar", "line", "pie", "scatter"}


def _deduplicate_ids(tabs: List[SheetTab]) -> None:
    """Ensure unique tab ids by appending _2, _3, etc. for duplicates."""
    seen: Set[str] = set()
    for tab in tabs:
        original = tab.id
        counter = 2
        while tab.id in seen:
            tab.id = f"{original}_{counter}"
            counter += 1
        seen.add(tab.id)


def _deduplicate_names(tabs: List[SheetTab]) -> None:
    """Ensure unique tab names by appending (2), (3), etc. for duplicates."""
    seen: Set[str] = set()
    for tab in tabs:
        original = tab.name
        counter = 2
        while tab.name in seen:
            tab.name = f"{original} ({counter})"
            counter += 1
        seen.add(tab.name)


def _align_row_widths(tab: SheetTab) -> None:
    """Pad short rows with None, truncate excess values to match header count."""
    num_cols = len(tab.headers)
    if num_cols == 0:
        return
    aligned = []
    for row in tab.rows:
        if len(row) < num_cols:
            aligned.append(list(row) + [None] * (num_cols - len(row)))
        elif len(row) > num_cols:
            aligned.append(list(row[:num_cols]))
        else:
            aligned.append(list(row))
    tab.rows = aligned


def _normalize_column_widths(tab: SheetTab) -> None:
    """Normalize column_widths to match header count."""
    num_cols = len(tab.headers)
    if num_cols == 0:
        tab.column_widths = []
        return
    if len(tab.column_widths) < num_cols:
        tab.column_widths = list(tab.column_widths) + [_DEFAULT_COLUMN_WIDTH] * (
            num_cols - len(tab.column_widths)
        )
    elif len(tab.column_widths) > num_cols:
        tab.column_widths = list(tab.column_widths[:num_cols])


def _sanitize_placeholders(tab: SheetTab) -> None:
    """Replace placeholder content with deterministic fallback text."""
    for row_idx, row in enumerate(tab.rows):
        for col_idx, val in enumerate(row):
            if isinstance(val, str) and _PLACEHOLDER_PATTERNS.match(val.strip()):
                tab.rows[row_idx][col_idx] = _FALLBACK_TEXT

    # Also sanitize headers
    for idx, header in enumerate(tab.headers):
        if _PLACEHOLDER_PATTERNS.match(header.strip()):
            tab.headers[idx] = f"Column_{idx + 1}"


def _is_tab_empty(tab: SheetTab) -> bool:
    """A tab is empty if it has no headers and no rows."""
    return not tab.headers and not tab.rows


def _has_numeric_value(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def has_chartable_numeric_data(content_tree: SheetContentTree) -> bool:
    """Return True if at least one tab has chartable numeric data."""
    for tab in content_tree.tabs:
        if not tab.headers or not tab.rows:
            continue
        numeric_cols = 0
        for col_idx in range(len(tab.headers)):
            has_numeric = any(
                col_idx < len(row) and _has_numeric_value(row[col_idx])
                for row in tab.rows
            )
            if has_numeric:
                numeric_cols += 1
        if numeric_cols >= 1 and len(tab.rows) >= 2:
            return True
    return False


def _sanitize_chart_plan(chart_plan: Any) -> List[Dict[str, Any]]:
    if not isinstance(chart_plan, list):
        return []

    sanitized: List[Dict[str, Any]] = []
    for entry in chart_plan:
        if not isinstance(entry, dict):
            continue
        chart_type = entry.get("chart_type")
        if not isinstance(chart_type, str):
            continue
        chart_type = chart_type.strip().lower()
        if chart_type not in _VALID_CHART_TYPES:
            continue

        cleaned: Dict[str, Any] = {"chart_type": chart_type}
        if isinstance(entry.get("tab_name"), str) and entry["tab_name"].strip():
            cleaned["tab_name"] = entry["tab_name"].strip()
        if isinstance(entry.get("title"), str) and entry["title"].strip():
            cleaned["title"] = entry["title"].strip()
        if isinstance(entry.get("category_column"), str) and entry["category_column"].strip():
            cleaned["category_column"] = entry["category_column"].strip()
        if isinstance(entry.get("x_column"), str) and entry["x_column"].strip():
            cleaned["x_column"] = entry["x_column"].strip()
        if isinstance(entry.get("y_column"), str) and entry["y_column"].strip():
            cleaned["y_column"] = entry["y_column"].strip()

        value_columns = entry.get("value_columns")
        if isinstance(value_columns, list):
            cleaned["value_columns"] = [
                str(v).strip() for v in value_columns
                if isinstance(v, str) and str(v).strip()
            ][:4]

        sanitized.append(cleaned)
    return sanitized


def _normalize_visual_metadata(content_tree: SheetContentTree) -> None:
    metadata = dict(content_tree.metadata or {})

    visual_profile = metadata.get("visual_profile")
    if not isinstance(visual_profile, str):
        metadata["visual_profile"] = _DEFAULT_VISUAL_PROFILE
    else:
        visual_profile = visual_profile.strip().lower()
        metadata["visual_profile"] = (
            visual_profile if visual_profile in _VALID_VISUAL_PROFILES else _DEFAULT_VISUAL_PROFILE
        )

    palette_hint = metadata.get("palette_hint")
    if isinstance(palette_hint, str):
        palette_hint = palette_hint.strip().lower()
        if palette_hint:
            metadata["palette_hint"] = palette_hint
        else:
            metadata.pop("palette_hint", None)
    else:
        metadata.pop("palette_hint", None)

    metadata["chart_plan"] = _sanitize_chart_plan(metadata.get("chart_plan"))
    content_tree.metadata = metadata


def needs_sheet_visual_repair(content_tree: SheetContentTree) -> bool:
    """Determine if a second-pass visual metadata repair should run."""
    if not has_chartable_numeric_data(content_tree):
        return False
    metadata = content_tree.metadata or {}
    visual_profile = metadata.get("visual_profile")
    if visual_profile not in _VALID_VISUAL_PROFILES:
        return True
    if not isinstance(metadata.get("palette_hint"), str):
        return True
    chart_plan = metadata.get("chart_plan")
    return not isinstance(chart_plan, list) or len(chart_plan) == 0


def merge_sheet_visual_metadata(
    content_tree: SheetContentTree,
    incoming_metadata: Any,
) -> bool:
    """Merge visual metadata from a repair pass into the content tree.

    Returns True when at least one visual metadata field was accepted.
    """
    if not isinstance(incoming_metadata, dict):
        return False

    metadata = dict(content_tree.metadata or {})
    changed = False

    visual_profile = incoming_metadata.get("visual_profile")
    if isinstance(visual_profile, str):
        vp = visual_profile.strip().lower()
        if vp in _VALID_VISUAL_PROFILES and metadata.get("visual_profile") != vp:
            metadata["visual_profile"] = vp
            changed = True

    palette_hint = incoming_metadata.get("palette_hint")
    if isinstance(palette_hint, str):
        palette = palette_hint.strip().lower()
        if palette and metadata.get("palette_hint") != palette:
            metadata["palette_hint"] = palette
            changed = True

    chart_plan = _sanitize_chart_plan(incoming_metadata.get("chart_plan"))
    if chart_plan:
        metadata["chart_plan"] = chart_plan
        changed = True

    if changed:
        content_tree.metadata = metadata
    return changed


def normalize_sheet_content_tree(
    content_tree: SheetContentTree,
) -> SheetContentTree:
    """Normalize a sheet content tree for structural integrity.

    This is idempotent — running it twice yields the same result.
    Raises ValueError if all tabs are empty.
    """
    if not content_tree.tabs:
        raise ValueError("Sheet must contain at least one tab")

    # Check that at least one tab has content
    if all(_is_tab_empty(tab) for tab in content_tree.tabs):
        raise ValueError("Sheet must contain at least one non-empty tab")

    # Structural normalization
    _deduplicate_ids(content_tree.tabs)
    _deduplicate_names(content_tree.tabs)

    all_warnings: List[str] = []

    for tab in content_tree.tabs:
        _align_row_widths(tab)
        _normalize_column_widths(tab)
        _sanitize_placeholders(tab)

        # Formula validation
        warnings = validate_tab_formulas(tab)
        all_warnings.extend(warnings)

    # Record formula warnings in analysis report
    if all_warnings:
        if content_tree.analysis_report is None:
            content_tree.analysis_report = SheetAnalysisReport()
        content_tree.analysis_report.warnings.extend(all_warnings)

    _normalize_visual_metadata(content_tree)

    return content_tree
