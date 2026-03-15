"""Deterministic statistical analysis for uploaded tabular data."""

import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from core.schemas.studio_schema import (
    SheetAnalysisReport,
    SheetAnomaly,
    SheetCorrelation,
    SheetNumericSummary,
    SheetTab,
    SheetTrend,
)
from core.studio.sheets.types import (
    ANOMALY_Z_THRESHOLD,
    MIN_OBSERVATIONS_FOR_CORRELATION,
    TREND_EPSILON,
    TabularDataset,
)


def _is_numeric(value: Any) -> bool:
    """Check if a value is numeric (int or float, not bool)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _get_numeric_values(
    rows: list[list[Any]], col_idx: int
) -> tuple[list[float], int]:
    """Extract numeric values from a column. Returns (values, null_count)."""
    values = []
    null_count = 0
    for row in rows:
        if col_idx < len(row):
            val = row[col_idx]
            if val is None or val == "":
                null_count += 1
            elif _is_numeric(val):
                values.append(float(val))
            # Non-numeric strings are skipped (not counted as null)
        else:
            null_count += 1
    return values, null_count


def _compute_summary_stats(
    dataset: TabularDataset,
) -> list[SheetNumericSummary]:
    """Compute summary statistics for each numeric column."""
    summaries = []
    for col_idx, col_name in enumerate(dataset.columns):
        values, null_count = _get_numeric_values(dataset.rows, col_idx)
        if not values:
            continue  # Skip non-numeric columns

        count = len(values)
        mean_val = statistics.mean(values)
        median_val = statistics.median(values)
        std_val = statistics.stdev(values) if count >= 2 else 0.0
        min_val = min(values)
        max_val = max(values)

        summaries.append(
            SheetNumericSummary(
                column=col_name,
                count=count,
                null_count=null_count,
                mean=round(mean_val, 2),
                median=round(median_val, 2),
                std=round(std_val, 2),
                min_val=round(min_val, 2),
                max_val=round(max_val, 2),
            )
        )
    return summaries


def _compute_correlations(
    dataset: TabularDataset,
) -> list[SheetCorrelation]:
    """Compute Pearson correlation pairs for numeric columns."""
    # Find numeric columns with sufficient data
    numeric_cols: list[tuple[int, str, list[float]]] = []
    for col_idx, col_name in enumerate(dataset.columns):
        values, _ = _get_numeric_values(dataset.rows, col_idx)
        if len(values) >= MIN_OBSERVATIONS_FOR_CORRELATION:
            numeric_cols.append((col_idx, col_name, values))

    if len(numeric_cols) < 2:
        return []

    correlations = []
    for i in range(len(numeric_cols)):
        for j in range(i + 1, len(numeric_cols)):
            idx_a, name_a, _ = numeric_cols[i]
            idx_b, name_b, _ = numeric_cols[j]

            # Build paired observations (both non-null in same row)
            pairs_a, pairs_b = [], []
            for row in dataset.rows:
                val_a = row[idx_a] if idx_a < len(row) else None
                val_b = row[idx_b] if idx_b < len(row) else None
                if _is_numeric(val_a) and _is_numeric(val_b):
                    pairs_a.append(float(val_a))
                    pairs_b.append(float(val_b))

            if len(pairs_a) < MIN_OBSERVATIONS_FOR_CORRELATION:
                continue

            try:
                r = statistics.correlation(pairs_a, pairs_b)
                correlations.append(
                    SheetCorrelation(
                        column_a=name_a,
                        column_b=name_b,
                        pearson_r=round(r, 4),
                    )
                )
            except (statistics.StatisticsError, ZeroDivisionError):
                continue

    return correlations


def _compute_trends(dataset: TabularDataset) -> list[SheetTrend]:
    """Compute slope-based trend classification for numeric columns."""
    trends = []
    for col_idx, col_name in enumerate(dataset.columns):
        values, _ = _get_numeric_values(dataset.rows, col_idx)
        if len(values) < 2:
            continue

        # Simple linear regression: slope = Σ((x-x̄)(y-ȳ)) / Σ((x-x̄)²)
        n = len(values)
        x_mean = (n - 1) / 2.0
        y_mean = statistics.mean(values)

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator

        if slope > TREND_EPSILON:
            direction = "up"
        elif slope < -TREND_EPSILON:
            direction = "down"
        else:
            direction = "flat"

        trends.append(
            SheetTrend(column=col_name, direction=direction, slope=round(slope, 6))
        )
    return trends


def _detect_anomalies(dataset: TabularDataset) -> list[SheetAnomaly]:
    """Detect z-score based anomalies for numeric columns."""
    anomalies = []
    for col_idx, col_name in enumerate(dataset.columns):
        values, _ = _get_numeric_values(dataset.rows, col_idx)
        if len(values) < 3:
            continue

        mean_val = statistics.mean(values)
        std_val = statistics.stdev(values)
        if std_val == 0:
            continue

        # Check each row for anomalies
        for row_idx, row in enumerate(dataset.rows):
            if col_idx >= len(row):
                continue
            val = row[col_idx]
            if not _is_numeric(val):
                continue
            z = (float(val) - mean_val) / std_val
            if abs(z) >= ANOMALY_Z_THRESHOLD:
                anomalies.append(
                    SheetAnomaly(
                        column=col_name,
                        row_index=row_idx,
                        value=float(val),
                        z_score=round(z, 4),
                    )
                )
    return anomalies


def _build_pivot_preview(
    dataset: TabularDataset,
) -> dict[str, Any] | None:
    """Build a single pivot/crosstab from first suitable categorical + numeric pair."""
    categorical_cols = []
    numeric_cols = []

    for col_idx, col_name in enumerate(dataset.columns):
        values, _ = _get_numeric_values(dataset.rows, col_idx)
        if values and len(values) >= len(dataset.rows) * 0.5:
            numeric_cols.append((col_idx, col_name))
        else:
            # Check if it's categorical (has string values)
            string_count = sum(
                1
                for row in dataset.rows
                if col_idx < len(row)
                and isinstance(row[col_idx], str)
                and row[col_idx]
            )
            if string_count >= len(dataset.rows) * 0.5:
                categorical_cols.append((col_idx, col_name))

    if not categorical_cols or not numeric_cols:
        return None

    cat_idx, cat_name = categorical_cols[0]
    num_idx, num_name = numeric_cols[0]

    # Build pivot: group by categorical, aggregate numeric
    pivot: dict[str, list[float]] = defaultdict(list)
    for row in dataset.rows:
        if cat_idx < len(row) and num_idx < len(row):
            cat_val = row[cat_idx]
            num_val = row[num_idx]
            if isinstance(cat_val, str) and cat_val and _is_numeric(num_val):
                pivot[cat_val].append(float(num_val))

    if not pivot:
        return None

    table = {k: round(statistics.mean(v), 2) for k, v in pivot.items()}
    return {
        "index_column": cat_name,
        "value_column": num_name,
        "table": table,
    }


def analyze_dataset(dataset: TabularDataset) -> SheetAnalysisReport:
    """Run deterministic analysis on a TabularDataset. Returns a SheetAnalysisReport."""
    return SheetAnalysisReport(
        summary_stats=_compute_summary_stats(dataset),
        correlations=_compute_correlations(dataset),
        trends=_compute_trends(dataset),
        anomalies=_detect_anomalies(dataset),
        pivot_preview=_build_pivot_preview(dataset),
    )


def build_analysis_tabs(
    dataset: TabularDataset,
    report: SheetAnalysisReport,
) -> list[SheetTab]:
    """Generate SheetTab instances from analysis results for embedding in the content tree."""
    tabs = []

    # Tab 1: Uploaded_Data — raw data
    tabs.append(
        SheetTab(
            id="uploaded_data",
            name="Uploaded_Data",
            headers=dataset.columns,
            rows=dataset.rows,
            formulas={},
            column_widths=[max(len(str(c)) * 10, 80) for c in dataset.columns],
        )
    )

    # Tab 2: Summary_Stats
    if report.summary_stats:
        headers = ["Column", "Count", "Null Count", "Mean", "Median", "Std", "Min", "Max"]
        rows = [
            [s.column, s.count, s.null_count, s.mean, s.median, s.std, s.min_val, s.max_val]
            for s in report.summary_stats
        ]
        tabs.append(
            SheetTab(
                id="summary_stats",
                name="Summary_Stats",
                headers=headers,
                rows=rows,
                formulas={},
                column_widths=[100, 60, 80, 80, 80, 80, 80, 80],
            )
        )

    # Tab 3: Correlations (skip if empty)
    if report.correlations:
        headers = ["Column A", "Column B", "Pearson R"]
        rows = [[c.column_a, c.column_b, c.pearson_r] for c in report.correlations]
        tabs.append(
            SheetTab(
                id="correlations",
                name="Correlations",
                headers=headers,
                rows=rows,
                formulas={},
                column_widths=[120, 120, 100],
            )
        )

    # Tab 4: Anomalies (skip if empty)
    if report.anomalies:
        headers = ["Column", "Row Index", "Value", "Z-Score"]
        rows = [[a.column, a.row_index, a.value, a.z_score] for a in report.anomalies]
        tabs.append(
            SheetTab(
                id="anomalies",
                name="Anomalies",
                headers=headers,
                rows=rows,
                formulas={},
                column_widths=[120, 80, 100, 100],
            )
        )

    # Tab 5: Pivot (skip if no suitable pair)
    if report.pivot_preview:
        idx_col = report.pivot_preview["index_column"]
        val_col = report.pivot_preview["value_column"]
        table = report.pivot_preview["table"]
        headers = [idx_col, f"Avg {val_col}"]
        rows = [[k, v] for k, v in table.items()]
        tabs.append(
            SheetTab(
                id="pivot",
                name="Pivot",
                headers=headers,
                rows=rows,
                formulas={},
                column_widths=[120, 100],
            )
        )

    return tabs
