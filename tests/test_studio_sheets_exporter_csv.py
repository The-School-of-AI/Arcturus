"""Tests for core/studio/sheets/exporter_csv.py — CSV primary-tab + ZIP export."""

import csv
import zipfile

import pytest

from core.schemas.studio_schema import SheetContentTree, SheetTab
from core.studio.sheets.exporter_csv import export_to_csv, export_to_csv_zip


def _make_tree(**kwargs) -> SheetContentTree:
    defaults = {
        "workbook_title": "Test",
        "tabs": [
            SheetTab(
                id="t1",
                name="Revenue",
                headers=["Month", "Amount"],
                rows=[["Jan", 100], ["Feb", 200]],
            )
        ],
    }
    defaults.update(kwargs)
    return SheetContentTree(**defaults)


def test_csv_creates_file(tmp_path):
    path = tmp_path / "output.csv"
    export_to_csv(_make_tree(), path)
    assert path.exists()


def test_csv_returns_tab_name(tmp_path):
    path = tmp_path / "output.csv"
    name = export_to_csv(_make_tree(), path)
    assert name == "Revenue"


def test_csv_selects_first_nonempty_tab(tmp_path):
    tree = _make_tree(
        tabs=[
            SheetTab(id="t1", name="Empty", headers=["A"]),
            SheetTab(id="t2", name="Data", headers=["B"], rows=[[1]]),
        ]
    )
    path = tmp_path / "output.csv"
    name = export_to_csv(tree, path)
    assert name == "Data"


def test_csv_headers_first_row(tmp_path):
    path = tmp_path / "output.csv"
    export_to_csv(_make_tree(), path)
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
    assert headers == ["Month", "Amount"]


def test_csv_data_rows_present(tmp_path):
    path = tmp_path / "output.csv"
    export_to_csv(_make_tree(), path)
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        rows = list(reader)
    assert len(rows) == 2
    assert rows[0][0] == "Jan"


def test_csv_utf8_encoding(tmp_path):
    tree = _make_tree(
        tabs=[
            SheetTab(
                id="t1",
                name="Intl",
                headers=["Name"],
                rows=[["Ñoño"], ["日本語"]],
            )
        ]
    )
    path = tmp_path / "output.csv"
    export_to_csv(tree, path)
    content = path.read_text(encoding="utf-8")
    assert "Ñoño" in content
    assert "日本語" in content


def test_csv_handles_empty_first_tab(tmp_path):
    tree = _make_tree(
        tabs=[
            SheetTab(id="t1", name="Empty"),
            SheetTab(id="t2", name="Data", headers=["X"], rows=[[1]]),
        ]
    )
    path = tmp_path / "output.csv"
    name = export_to_csv(tree, path)
    assert name == "Data"


def test_csv_formulas_not_written(tmp_path):
    tree = _make_tree(
        tabs=[
            SheetTab(
                id="t1",
                name="Data",
                headers=["A", "B"],
                rows=[[1, 2]],
                formulas={"B2": "=A2*2"},
            )
        ]
    )
    path = tmp_path / "output.csv"
    export_to_csv(tree, path)
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        rows = list(reader)
    # Formula cell should be empty
    assert rows[0][1] == ""


# === ZIP export (all tabs) ===


class TestExportToCsvZip:
    def test_creates_zip_file(self, tmp_path):
        path = tmp_path / "output.zip"
        export_to_csv_zip(_make_tree(), path)
        assert path.exists()
        assert zipfile.is_zipfile(path)

    def test_returns_tab_names(self, tmp_path):
        tree = _make_tree(
            tabs=[
                SheetTab(id="t1", name="Revenue", headers=["A"], rows=[[1]]),
                SheetTab(id="t2", name="Costs", headers=["B"], rows=[[2]]),
            ]
        )
        path = tmp_path / "output.zip"
        names = export_to_csv_zip(tree, path)
        assert names == ["Revenue", "Costs"]

    def test_all_tabs_included(self, tmp_path):
        tree = _make_tree(
            tabs=[
                SheetTab(id="t1", name="Tab1", headers=["A"], rows=[[1]]),
                SheetTab(id="t2", name="Tab2", headers=["B"], rows=[[2]]),
                SheetTab(id="t3", name="Tab3", headers=["C"], rows=[[3]]),
            ]
        )
        path = tmp_path / "output.zip"
        export_to_csv_zip(tree, path)
        with zipfile.ZipFile(path, "r") as zf:
            assert len(zf.namelist()) == 3
            assert "Tab1.csv" in zf.namelist()
            assert "Tab2.csv" in zf.namelist()
            assert "Tab3.csv" in zf.namelist()

    def test_csv_content_correct(self, tmp_path):
        path = tmp_path / "output.zip"
        export_to_csv_zip(_make_tree(), path)
        with zipfile.ZipFile(path, "r") as zf:
            content = zf.read("Revenue.csv").decode("utf-8")
        assert "Month,Amount" in content
        assert "Jan" in content

    def test_formulas_blanked_in_zip(self, tmp_path):
        tree = _make_tree(
            tabs=[
                SheetTab(
                    id="t1", name="Data",
                    headers=["A", "B"],
                    rows=[[1, 2]],
                    formulas={"B2": "=A2*2"},
                )
            ]
        )
        path = tmp_path / "output.zip"
        export_to_csv_zip(tree, path)
        with zipfile.ZipFile(path, "r") as zf:
            content = zf.read("Data.csv").decode("utf-8")
        reader = csv.reader(content.splitlines())
        next(reader)  # skip header
        rows = list(reader)
        assert rows[0][1] == ""

    def test_duplicate_tab_names_suffixed(self, tmp_path):
        tree = _make_tree(
            tabs=[
                SheetTab(id="t1", name="Sales", headers=["A"], rows=[[1]]),
                SheetTab(id="t2", name="Sales", headers=["B"], rows=[[2]]),
                SheetTab(id="t3", name="Sales", headers=["C"], rows=[[3]]),
            ]
        )
        path = tmp_path / "output.zip"
        export_to_csv_zip(tree, path)
        with zipfile.ZipFile(path, "r") as zf:
            names = sorted(zf.namelist())
        assert names == ["Sales (2).csv", "Sales (3).csv", "Sales.csv"]

    def test_empty_tab_gets_header_only_csv(self, tmp_path):
        tree = _make_tree(
            tabs=[
                SheetTab(id="t1", name="Empty", headers=["X", "Y"]),
            ]
        )
        path = tmp_path / "output.zip"
        export_to_csv_zip(tree, path)
        with zipfile.ZipFile(path, "r") as zf:
            content = zf.read("Empty.csv").decode("utf-8")
        reader = csv.reader(content.splitlines())
        rows = list(reader)
        assert rows[0] == ["X", "Y"]
        assert len(rows) == 1  # header only

    def test_utf8_content_preserved(self, tmp_path):
        tree = _make_tree(
            tabs=[
                SheetTab(id="t1", name="Intl", headers=["Name"], rows=[["Ñoño"], ["日本語"]]),
            ]
        )
        path = tmp_path / "output.zip"
        export_to_csv_zip(tree, path)
        with zipfile.ZipFile(path, "r") as zf:
            content = zf.read("Intl.csv").decode("utf-8")
        assert "Ñoño" in content
        assert "日本語" in content

    def test_parent_dir_created(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "output.zip"
        export_to_csv_zip(_make_tree(), path)
        assert path.exists()

    def test_empty_tabs_raises(self, tmp_path):
        tree = _make_tree(tabs=[])
        path = tmp_path / "output.zip"
        with pytest.raises(ValueError, match="no tabs"):
            export_to_csv_zip(tree, path)
