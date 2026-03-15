"""Tests for core/studio/sheets/formulas.py — formula syntax and reference validation."""

import pytest

from core.schemas.studio_schema import SheetTab
from core.studio.sheets.formulas import (
    detect_circular_refs,
    extract_cell_refs,
    validate_formula_refs,
    validate_formula_syntax,
    validate_tab_formulas,
)

# === validate_formula_syntax ===


def test_formula_syntax_valid():
    assert validate_formula_syntax("=SUM(A1:A10)") is True


def test_formula_syntax_missing_equals():
    assert validate_formula_syntax("SUM(A1:A10)") is False


def test_formula_syntax_balanced_parens():
    assert validate_formula_syntax("=SUM(A1:A10") is False
    assert validate_formula_syntax("=SUM(A1:A10))") is False
    assert validate_formula_syntax("=IF(A1>0,SUM(B1:B10),0)") is True


def test_formula_syntax_empty():
    assert validate_formula_syntax("") is False


# === extract_cell_refs ===


def test_extract_cell_refs_single():
    refs = extract_cell_refs("=A1*2")
    assert refs == ["A1"]


def test_extract_cell_refs_range():
    refs = extract_cell_refs("=SUM(A1:B10)")
    assert refs == ["A1", "B10"]


def test_extract_cell_refs_multiple():
    refs = extract_cell_refs("=A1+B2+C3")
    assert refs == ["A1", "B2", "C3"]


# === validate_formula_refs ===


def test_validate_refs_in_bounds():
    # 10 data rows + 1 header = max_row 11, 5 columns = max_col 5
    assert validate_formula_refs("=SUM(A1:A11)", max_row=11, max_col=5) is True
    assert validate_formula_refs("=E1*2", max_row=11, max_col=5) is True


def test_validate_refs_out_of_bounds():
    # Column Z (index 26) out of bounds for 5 columns
    assert validate_formula_refs("=Z1*2", max_row=11, max_col=5) is False
    # Row 9999 out of bounds
    assert validate_formula_refs("=A9999", max_row=11, max_col=5) is False


# === validate_tab_formulas ===


def test_validate_tab_formulas_removes_invalid():
    tab = SheetTab(
        id="t1",
        name="Test",
        headers=["A", "B", "C"],
        rows=[["x", 1, 2], ["y", 3, 4]],
        formulas={
            "C3": "=B2+B3",  # valid: key within bounds+1, refs within bounds
            "Z99": "=A1",    # invalid: key out of bounds
        },
    )
    warnings = validate_tab_formulas(tab)
    assert len(warnings) == 1
    assert "Z99" in warnings[0]
    assert "C3" in tab.formulas
    assert "Z99" not in tab.formulas


def test_validate_tab_formulas_preserves_valid():
    tab = SheetTab(
        id="t1",
        name="Test",
        headers=["A", "B", "C"],
        rows=[["x", 1, 2], ["y", 3, 4]],
        formulas={
            "C3": "=B2+B3",
            "D3": "=SUM(B2:B3)",  # key one col beyond = allowed
        },
    )
    warnings = validate_tab_formulas(tab)
    assert len(warnings) == 0
    assert len(tab.formulas) == 2


def test_validate_formula_key_out_of_bounds():
    tab = SheetTab(
        id="t1",
        name="Test",
        headers=["A", "B"],
        rows=[[1, 2]],
        formulas={"Z50": "=A1"},  # key way out of bounds
    )
    warnings = validate_tab_formulas(tab)
    assert len(warnings) == 1
    assert "out of bounds" in warnings[0].lower()


# === detect_circular_refs ===


def test_circular_refs_empty():
    """Empty formulas dict → no cycles."""
    assert detect_circular_refs({}) == []


def test_circular_refs_no_cycles():
    """Formulas referencing only data cells → no cycles."""
    formulas = {
        "C2": "=A2+B2",
        "C3": "=A3+B3",
    }
    assert detect_circular_refs(formulas) == []


def test_circular_refs_self_reference():
    """Direct self-reference detected."""
    formulas = {"C2": "=C2*1.1"}
    assert detect_circular_refs(formulas) == ["C2"]


def test_circular_refs_two_cell_cycle():
    """Two-cell indirect cycle: A2 → B2 → A2."""
    formulas = {
        "A2": "=B2+1",
        "B2": "=A2+1",
    }
    result = detect_circular_refs(formulas)
    assert sorted(result) == ["A2", "B2"]


def test_circular_refs_three_cell_cycle():
    """Three-cell cycle: A2 → B2 → C2 → A2."""
    formulas = {
        "A2": "=C2+1",
        "B2": "=A2+1",
        "C2": "=B2+1",
    }
    result = detect_circular_refs(formulas)
    assert sorted(result) == ["A2", "B2", "C2"]


def test_circular_refs_mixed_valid_and_cyclic():
    """Only cyclic cells flagged; valid formulas untouched."""
    formulas = {
        "A2": "=B2+1",  # cycle member
        "B2": "=A2+1",  # cycle member
        "C2": "=A1+B1",  # valid: refs data cells only
        "D2": "=SUM(A1:B1)",  # valid
    }
    result = detect_circular_refs(formulas)
    assert sorted(result) == ["A2", "B2"]


def test_circular_refs_chain_into_cycle():
    """Cell leading into a cycle is NOT flagged — only cycle members."""
    formulas = {
        "A2": "=B2+1",  # cycle
        "B2": "=A2+1",  # cycle
        "D2": "=A2*2",  # leads into cycle but NOT on cycle
    }
    result = detect_circular_refs(formulas)
    assert sorted(result) == ["A2", "B2"]
    assert "D2" not in result


# === validate_tab_formulas — circular ref integration ===


def test_validate_removes_direct_circular_ref():
    """Direct circular ref removed, valid formula preserved."""
    tab = SheetTab(
        id="t1",
        name="Test",
        headers=["A", "B", "C"],
        rows=[["x", 1, 2], ["y", 3, 4]],
        formulas={
            "C2": "=C2*1.1",  # self-ref → should be removed
            "C3": "=B2+B3",   # valid → should remain
        },
    )
    warnings = validate_tab_formulas(tab)
    assert "C2" not in tab.formulas
    assert "C3" in tab.formulas
    assert any("circular" in w.lower() and "C2" in w for w in warnings)


def test_validate_removes_indirect_circular_refs():
    """Indirect circular refs removed with correct warnings."""
    tab = SheetTab(
        id="t1",
        name="Test",
        headers=["A", "B", "C"],
        rows=[["x", 1, 2], ["y", 3, 4]],
        formulas={
            "A2": "=B2+1",  # cycle
            "B2": "=A2+1",  # cycle
            "C3": "=A1+B1",  # valid
        },
    )
    warnings = validate_tab_formulas(tab)
    assert "A2" not in tab.formulas
    assert "B2" not in tab.formulas
    assert "C3" in tab.formulas
    circular_warnings = [w for w in warnings if "circular" in w.lower()]
    assert len(circular_warnings) == 2


def test_validate_no_circular_warning_for_acyclic():
    """No circular-ref warnings for perfectly valid formulas."""
    tab = SheetTab(
        id="t1",
        name="Test",
        headers=["A", "B", "C"],
        rows=[["x", 1, 2], ["y", 3, 4]],
        formulas={
            "C2": "=A2+B2",
            "C3": "=A3+B3",
        },
    )
    warnings = validate_tab_formulas(tab)
    assert len(warnings) == 0
    assert len(tab.formulas) == 2


def test_validate_circular_ref_idempotent():
    """Second validation run produces no changes (idempotency)."""
    tab = SheetTab(
        id="t1",
        name="Test",
        headers=["A", "B", "C"],
        rows=[["x", 1, 2], ["y", 3, 4]],
        formulas={
            "A2": "=B2+1",  # cycle — removed on first pass
            "B2": "=A2+1",  # cycle — removed on first pass
            "C3": "=A1+B1",  # valid
        },
    )
    warnings1 = validate_tab_formulas(tab)
    assert len(warnings1) == 2  # two circular refs removed

    warnings2 = validate_tab_formulas(tab)
    assert len(warnings2) == 0  # nothing left to remove
    assert "C3" in tab.formulas
