"""Sheet content tree normalization — deterministic post-generation quality pass."""

import re
from typing import List, Set

from core.schemas.studio_schema import SheetAnalysisReport, SheetContentTree, SheetTab
from core.studio.sheets.formulas import validate_tab_formulas

# Patterns that indicate placeholder content
_PLACEHOLDER_PATTERNS = re.compile(
    r"^(TBD|TODO|Lorem ipsum|To be added|N/A|PLACEHOLDER|xxx|…)$",
    re.IGNORECASE,
)
_FALLBACK_TEXT = "—"
_DEFAULT_COLUMN_WIDTH = 100


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

    return content_tree
