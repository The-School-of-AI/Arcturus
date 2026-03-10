"""Tests for core/studio/sheets/ingest.py — upload ingestion and normalization."""

import json

import pytest

from core.studio.sheets.ingest import ingest_upload
from core.studio.sheets.types import MAX_UPLOAD_COLUMNS, MAX_UPLOAD_ROWS, MAX_UPLOAD_SIZE_BYTES


# === CSV ingestion ===


def test_ingest_csv_basic():
    content = b"Name,Age,Score\nAlice,30,95\nBob,25,88\n"
    ds = ingest_upload("data.csv", content, "text/csv")
    assert ds.columns == ["Name", "Age", "Score"]
    assert len(ds.rows) == 2
    assert ds.rows[0] == ["Alice", 30, 95]
    assert ds.source_format == "csv"


def test_ingest_csv_delimiter_detection():
    content = b"Name;Age;Score\nAlice;30;95\nBob;25;88\n"
    ds = ingest_upload("data.csv", content, "text/csv")
    assert ds.columns == ["Name", "Age", "Score"]
    assert len(ds.rows) == 2


# === XLSX ingestion ===


def test_ingest_xlsx_basic():
    import openpyxl
    import io

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Product", "Price", "Qty"])
    ws.append(["Widget", 10.5, 100])
    ws.append(["Gadget", 25.0, 50])
    buf = io.BytesIO()
    wb.save(buf)
    content = buf.getvalue()

    ds = ingest_upload("data.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert ds.columns == ["Product", "Price", "Qty"]
    assert len(ds.rows) == 2
    assert ds.source_format == "xlsx"


# === JSON ingestion ===


def test_ingest_json_list_of_objects():
    data = [{"col": "a", "val": 1}, {"col": "b", "val": 2}]
    content = json.dumps(data).encode()
    ds = ingest_upload("data.json", content, "application/json")
    assert ds.columns == ["col", "val"]
    assert len(ds.rows) == 2
    assert ds.source_format == "json"


def test_ingest_json_rows_columns():
    data = {"columns": ["X", "Y"], "rows": [[1, 2], [3, 4]]}
    content = json.dumps(data).encode()
    ds = ingest_upload("data.json", content, "application/json")
    assert ds.columns == ["X", "Y"]
    assert ds.rows == [[1, 2], [3, 4]]


# === Guardrails ===


def test_ingest_rejects_empty_dataset():
    content = b"Name,Age\n"
    with pytest.raises(ValueError, match="no data rows"):
        ingest_upload("data.csv", content, "text/csv")


def test_ingest_rejects_oversized_file():
    content = b"x" * (MAX_UPLOAD_SIZE_BYTES + 1)
    with pytest.raises(ValueError, match="exceeds maximum"):
        ingest_upload("big.csv", content, "text/csv")


def test_ingest_rejects_too_many_rows():
    header = "A,B\n"
    rows = "1,2\n" * (MAX_UPLOAD_ROWS + 1)
    content = (header + rows).encode()
    with pytest.raises(ValueError, match="Row count"):
        ingest_upload("big.csv", content, "text/csv")


def test_ingest_rejects_too_many_columns():
    cols = ",".join([f"C{i}" for i in range(MAX_UPLOAD_COLUMNS + 1)])
    vals = ",".join(["1"] * (MAX_UPLOAD_COLUMNS + 1))
    content = f"{cols}\n{vals}\n".encode()
    with pytest.raises(ValueError, match="Column count"):
        ingest_upload("wide.csv", content, "text/csv")


def test_ingest_rejects_unsupported_format():
    with pytest.raises(ValueError, match="Unsupported file type"):
        ingest_upload("data.pdf", b"fake", "application/pdf")


def test_ingest_normalizes_column_types():
    content = b"A,B\n1,hello\n2.5,world\n"
    ds = ingest_upload("data.csv", content, "text/csv")
    assert ds.rows[0][0] == 1
    assert ds.rows[1][0] == 2.5
    assert ds.rows[0][1] == "hello"


def test_ingest_handles_null_values():
    content = b"A,B\n1,\n,3\n"
    ds = ingest_upload("data.csv", content, "text/csv")
    assert ds.rows[0][1] is None
    assert ds.rows[1][0] is None
