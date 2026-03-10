"""Tests for core/studio/sheets/generator.py — sheet normalization rules."""

import pytest

from core.schemas.studio_schema import SheetContentTree, SheetTab
from core.studio.sheets.generator import normalize_sheet_content_tree


def _make_tree(**kwargs) -> SheetContentTree:
    """Helper to build a minimal valid SheetContentTree."""
    defaults = {
        "workbook_title": "Test",
        "tabs": [
            SheetTab(
                id="t1",
                name="Data",
                headers=["A", "B"],
                rows=[[1, 2]],
            )
        ],
    }
    defaults.update(kwargs)
    return SheetContentTree(**defaults)


# === Tab ID deduplication ===


def test_normalize_unique_tab_ids():
    tree = _make_tree(
        tabs=[
            SheetTab(id="t1", name="Tab A", headers=["X"], rows=[[1]]),
            SheetTab(id="t1", name="Tab B", headers=["Y"], rows=[[2]]),
        ]
    )
    result = normalize_sheet_content_tree(tree)
    ids = [t.id for t in result.tabs]
    assert len(ids) == len(set(ids)), "Tab IDs should be unique"


# === Tab name deduplication ===


def test_normalize_unique_tab_names():
    tree = _make_tree(
        tabs=[
            SheetTab(id="t1", name="Data", headers=["X"], rows=[[1]]),
            SheetTab(id="t2", name="Data", headers=["Y"], rows=[[2]]),
        ]
    )
    result = normalize_sheet_content_tree(tree)
    names = [t.name for t in result.tabs]
    assert len(names) == len(set(names)), "Tab names should be unique"
    assert "Data (2)" in names


# === Row width normalization ===


def test_normalize_row_width_padding():
    tree = _make_tree(
        tabs=[
            SheetTab(id="t1", name="Data", headers=["A", "B", "C"], rows=[[1]]),
        ]
    )
    result = normalize_sheet_content_tree(tree)
    assert len(result.tabs[0].rows[0]) == 3
    assert result.tabs[0].rows[0][1] is None
    assert result.tabs[0].rows[0][2] is None


def test_normalize_row_width_truncation():
    tree = _make_tree(
        tabs=[
            SheetTab(id="t1", name="Data", headers=["A"], rows=[[1, 2, 3]]),
        ]
    )
    result = normalize_sheet_content_tree(tree)
    assert len(result.tabs[0].rows[0]) == 1


# === Column widths ===


def test_normalize_column_widths_padding():
    tree = _make_tree(
        tabs=[
            SheetTab(
                id="t1", name="Data", headers=["A", "B", "C"],
                rows=[[1, 2, 3]], column_widths=[80],
            ),
        ]
    )
    result = normalize_sheet_content_tree(tree)
    assert len(result.tabs[0].column_widths) == 3
    assert result.tabs[0].column_widths[0] == 80
    assert result.tabs[0].column_widths[1] == 100  # default


# === Empty tabs rejection ===


def test_normalize_rejects_all_empty_tabs():
    tree = SheetContentTree(
        workbook_title="Empty",
        tabs=[SheetTab(id="t1", name="Empty")],
    )
    with pytest.raises(ValueError, match="non-empty"):
        normalize_sheet_content_tree(tree)


# === Placeholder sanitization ===


def test_normalize_sanitizes_placeholders():
    tree = _make_tree(
        tabs=[
            SheetTab(
                id="t1", name="Data", headers=["A", "B"],
                rows=[["TBD", "Lorem ipsum"]],
            ),
        ]
    )
    result = normalize_sheet_content_tree(tree)
    row = result.tabs[0].rows[0]
    assert row[0] == "—"
    assert row[1] == "—"


# === Formula validation integration ===


def test_normalize_runs_formula_validation():
    tree = _make_tree(
        tabs=[
            SheetTab(
                id="t1", name="Data", headers=["A", "B"],
                rows=[[1, 2], [3, 4]],
                formulas={"Z99": "=A1"},  # invalid key
            ),
        ]
    )
    result = normalize_sheet_content_tree(tree)
    assert "Z99" not in result.tabs[0].formulas
    assert result.analysis_report is not None
    assert len(result.analysis_report.warnings) > 0


# === Idempotency ===


def test_normalize_idempotent():
    tree = _make_tree(
        tabs=[
            SheetTab(
                id="t1", name="Data", headers=["A", "B"],
                rows=[[1, 2]], column_widths=[80],
            ),
        ]
    )
    result1 = normalize_sheet_content_tree(tree)
    # Create a new tree from the normalized one to test second pass
    result2 = normalize_sheet_content_tree(result1.model_copy(deep=True))
    assert result1.model_dump() == result2.model_dump()


# === Valid content preserved ===


def test_normalize_preserves_valid_content():
    tab = SheetTab(
        id="t1", name="Revenue", headers=["Month", "Value"],
        rows=[["Jan", 100], ["Feb", 200]],
        formulas={"C2": "=B2+B3"},
        column_widths=[100, 80],
    )
    tree = _make_tree(tabs=[tab])
    result = normalize_sheet_content_tree(tree)
    assert result.tabs[0].rows[0] == ["Jan", 100]
    assert result.tabs[0].rows[1] == ["Feb", 200]
    assert result.tabs[0].headers == ["Month", "Value"]
