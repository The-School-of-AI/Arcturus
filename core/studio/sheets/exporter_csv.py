"""CSV export for sheet artifacts — single tab or all tabs as ZIP."""

import csv
import io
import re
import zipfile
from pathlib import Path
from typing import IO, List

from core.schemas.studio_schema import SheetContentTree, SheetTab


def _col_index_to_letter(idx: int) -> str:
    """Convert 0-based column index to Excel column letters. 0=A, 25=Z, 26=AA, 27=AB, ..."""
    result = ""
    n = idx + 1  # convert to 1-based
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _write_tab_to_csv(tab: SheetTab, file_obj: IO[str]) -> None:
    """Write a single tab's headers and rows to a file-like text object.

    Formula cells are blanked (data-only export).
    """
    writer = csv.writer(file_obj)
    writer.writerow(tab.headers or [])

    formula_cells = set(tab.formulas) if tab.formulas else set()

    for row_idx, row in enumerate(tab.rows or [], start=2):
        out_row = []
        for col_idx, val in enumerate(row):
            col_letter = _col_index_to_letter(col_idx)
            cell_addr = f"{col_letter}{row_idx}"
            if cell_addr in formula_cells:
                out_row.append("")
            else:
                out_row.append(val if val is not None else "")
        # Pad to header width
        out_row.extend([""] * max(0, len(tab.headers or []) - len(out_row)))
        writer.writerow(out_row)


_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize_csv_filename(name: str) -> str:
    """Sanitize a tab name for use as a filename inside a ZIP archive."""
    cleaned = _UNSAFE_CHARS.sub("", name).strip()
    cleaned = cleaned[:100]
    return cleaned or "Sheet"


def export_to_csv(content_tree: SheetContentTree, output_path: Path) -> str:
    """Export primary tab to CSV. Returns the exported tab name.

    Tab selection: first tab with both headers and at least one row.
    Falls back to first tab if no qualifying tab found.
    Formulas are not written to CSV (data-only); formula cells become empty.
    """
    if not content_tree.tabs:
        raise ValueError("Cannot export empty sheet (no tabs)")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Select primary tab
    selected = None
    for tab in content_tree.tabs:
        if tab.headers and tab.rows:
            selected = tab
            break
    if selected is None:
        selected = content_tree.tabs[0]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        _write_tab_to_csv(selected, f)

    return selected.name


def export_to_csv_zip(content_tree: SheetContentTree, output_path: Path) -> List[str]:
    """Export all tabs as individual CSVs inside a ZIP archive.

    Returns the list of exported tab names (in order).
    Raises ValueError if no tabs.
    """
    if not content_tree.tabs:
        raise ValueError("Cannot export empty sheet (no tabs)")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    used_names: dict[str, int] = {}
    exported_tab_names: List[str] = []

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for tab in content_tree.tabs:
            base_name = _sanitize_csv_filename(tab.name)

            # Handle duplicate names
            if base_name in used_names:
                used_names[base_name] += 1
                csv_filename = f"{base_name} ({used_names[base_name]}).csv"
            else:
                used_names[base_name] = 1
                csv_filename = f"{base_name}.csv"

            buf = io.StringIO()
            _write_tab_to_csv(tab, buf)
            zf.writestr(csv_filename, buf.getvalue().encode("utf-8"))

            exported_tab_names.append(tab.name)

    return exported_tab_names
