from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _corrupt_path(path: Path) -> Path:
    stamp = int(time.time() * 1000)
    suffix = f"{path.suffix}.corrupt.{stamp}" if path.suffix else f".corrupt.{stamp}"
    return path.with_suffix(suffix)


def preserve_corrupt_file(path: Path) -> Path | None:
    if not path.exists():
        return None

    corrupt = _corrupt_path(path)
    try:
        path.replace(corrupt)
        return corrupt
    except OSError:
        return None


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        preserve_corrupt_file(path)
        return default


def read_jsonl_file(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    has_corruption = False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        preserve_corrupt_file(path)
        return []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            has_corruption = True
            continue
        if isinstance(payload, dict):
            rows.append(payload)
        else:
            has_corruption = True

    if has_corruption:
        # Keep only valid entries in-place and preserve invalid source file separately.
        corrupt = preserve_corrupt_file(path)
        if corrupt is not None:
            append_jsonl_rows(path, rows)

    return rows


def write_json_atomic(path: Path, payload: Any) -> None:
    ensure_parent(path)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(path)


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def append_jsonl_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    ensure_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
