"""CSV/XLSX/JSON upload ingestion with guardrails."""

import csv
import io
import json
from typing import Any, List

from core.studio.sheets.types import (
    MAX_UPLOAD_COLUMNS,
    MAX_UPLOAD_ROWS,
    MAX_UPLOAD_SIZE_BYTES,
    TabularDataset,
)

# MIME type to format mapping
_MIME_MAP = {
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/json": "json",
}

# Extension fallback mapping
_EXT_MAP = {
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".json": "json",
}


def _detect_format(filename: str, content_type: str) -> str:
    """Detect file format from MIME type or filename extension."""
    fmt = _MIME_MAP.get(content_type)
    if fmt:
        return fmt
    # Fallback to extension
    lower = filename.lower()
    for ext, fmt_name in _EXT_MAP.items():
        if lower.endswith(ext):
            return fmt_name
    raise ValueError(
        f"Unsupported file type: {content_type or 'unknown'} "
        f"(filename: {filename}). Supported: CSV, XLSX, JSON"
    )


def _ingest_csv(content_bytes: bytes, filename: str) -> TabularDataset:
    """Parse CSV content using csv.Sniffer for delimiter detection."""
    text = content_bytes.decode("utf-8", errors="replace")
    # Try to detect delimiter
    try:
        sample = text[:8192]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel  # default to comma

    reader = csv.reader(io.StringIO(text), dialect)
    all_rows = list(reader)
    if not all_rows:
        raise ValueError("CSV file contains no data")

    columns = all_rows[0]
    rows: list[list[Any]] = []
    for row in all_rows[1:]:
        # Coerce numeric values
        coerced = []
        for val in row:
            if val == "" or val is None:
                coerced.append(None)
            else:
                try:
                    coerced.append(int(val))
                except ValueError:
                    try:
                        coerced.append(float(val))
                    except ValueError:
                        coerced.append(val)
        rows.append(coerced)

    if not rows:
        raise ValueError("CSV file contains no data rows")

    return TabularDataset(
        columns=columns, rows=rows, source_format="csv", source_name=filename
    )


def _ingest_xlsx(content_bytes: bytes, filename: str) -> TabularDataset:
    """Parse XLSX first sheet using openpyxl."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content_bytes), data_only=True)
    ws = wb.active
    if ws is None:
        raise ValueError("XLSX file has no active worksheet")

    all_rows = list(ws.iter_rows(values_only=True))
    if not all_rows:
        raise ValueError("XLSX file contains no data")

    columns = [str(c) if c is not None else f"Column_{i+1}" for i, c in enumerate(all_rows[0])]
    rows: list[list[Any]] = []
    for row in all_rows[1:]:
        rows.append(list(row))

    if not rows:
        raise ValueError("XLSX file contains no data rows")

    return TabularDataset(
        columns=columns, rows=rows, source_format="xlsx", source_name=filename
    )


def _ingest_json(content_bytes: bytes, filename: str) -> TabularDataset:
    """Parse JSON as list-of-objects or {rows, columns} shape."""
    text = content_bytes.decode("utf-8", errors="replace")
    data = json.loads(text)

    if isinstance(data, list):
        # List of objects: [{"col": "val"}, ...]
        if not data:
            raise ValueError("JSON file contains no data")
        if not isinstance(data[0], dict):
            raise ValueError("JSON list items must be objects with key-value pairs")
        columns = list(data[0].keys())
        rows = [[obj.get(c) for c in columns] for obj in data]
    elif isinstance(data, dict):
        # {columns: [...], rows: [[...]]}
        if "columns" not in data or "rows" not in data:
            raise ValueError(
                'JSON object must have "columns" and "rows" keys'
            )
        columns = data["columns"]
        rows = data["rows"]
    else:
        raise ValueError("JSON must be a list of objects or {columns, rows} object")

    if not rows:
        raise ValueError("JSON file contains no data rows")

    return TabularDataset(
        columns=columns, rows=rows, source_format="json", source_name=filename
    )


_INGEST_DISPATCH = {
    "csv": _ingest_csv,
    "xlsx": _ingest_xlsx,
    "json": _ingest_json,
}


def ingest_upload(
    filename: str,
    content_bytes: bytes,
    content_type: str,
) -> TabularDataset:
    """Ingest an uploaded file into a normalized TabularDataset.

    Applies guardrails for file size, row count, and column count.
    """
    # Size guard
    if len(content_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(
            f"File size ({len(content_bytes):,} bytes) exceeds "
            f"maximum of {MAX_UPLOAD_SIZE_BYTES:,} bytes (10 MB)"
        )

    fmt = _detect_format(filename, content_type)
    ingest_fn = _INGEST_DISPATCH[fmt]
    dataset = ingest_fn(content_bytes, filename)

    # Row guard
    if len(dataset.rows) > MAX_UPLOAD_ROWS:
        raise ValueError(
            f"Row count ({len(dataset.rows):,}) exceeds "
            f"maximum of {MAX_UPLOAD_ROWS:,} rows"
        )

    # Column guard
    if len(dataset.columns) > MAX_UPLOAD_COLUMNS:
        raise ValueError(
            f"Column count ({len(dataset.columns)}) exceeds "
            f"maximum of {MAX_UPLOAD_COLUMNS} columns"
        )

    return dataset
