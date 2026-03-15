"""Shared data structures and constants for sheet ingestion and analysis."""

from dataclasses import dataclass
from typing import Any, List


@dataclass
class TabularDataset:
    """Normalized representation of any uploaded file after ingestion."""

    columns: list[str]
    rows: list[list[Any]]
    source_format: str  # "csv", "xlsx", "json"
    source_name: str  # original filename


# Analysis threshold constants
ANOMALY_Z_THRESHOLD = 3.0
TREND_EPSILON = 1e-6
MIN_OBSERVATIONS_FOR_CORRELATION = 5
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_UPLOAD_ROWS = 20_000
MAX_UPLOAD_COLUMNS = 200
