"""Tests for core/studio/sheets/analysis.py — statistical analysis components."""

import pytest

from core.studio.sheets.analysis import analyze_dataset, build_analysis_tabs
from core.studio.sheets.types import TabularDataset


# === Summary Stats ===


def test_summary_stats_numeric_columns():
    ds = TabularDataset(
        columns=["Val"],
        rows=[[10], [20], [30], [40], [50]],
        source_format="csv",
        source_name="test.csv",
    )
    report = analyze_dataset(ds)
    assert len(report.summary_stats) == 1
    s = report.summary_stats[0]
    assert s.column == "Val"
    assert s.count == 5
    assert s.mean == 30.0
    assert s.median == 30.0
    assert s.min_val == 10.0
    assert s.max_val == 50.0


def test_summary_stats_null_handling():
    ds = TabularDataset(
        columns=["Val"],
        rows=[[10], [None], [30], [None], [50]],
        source_format="csv",
        source_name="test.csv",
    )
    report = analyze_dataset(ds)
    s = report.summary_stats[0]
    assert s.count == 3
    assert s.null_count == 2


def test_summary_stats_non_numeric_skipped():
    ds = TabularDataset(
        columns=["Name", "City"],
        rows=[["Alice", "NY"], ["Bob", "LA"]],
        source_format="csv",
        source_name="test.csv",
    )
    report = analyze_dataset(ds)
    assert len(report.summary_stats) == 0


# === Correlations ===


def test_correlations_positive():
    ds = TabularDataset(
        columns=["X", "Y"],
        rows=[[1, 2], [2, 4], [3, 6], [4, 8], [5, 10]],
        source_format="csv",
        source_name="test.csv",
    )
    report = analyze_dataset(ds)
    assert len(report.correlations) == 1
    assert report.correlations[0].pearson_r == pytest.approx(1.0, abs=0.01)


def test_correlations_negative():
    ds = TabularDataset(
        columns=["X", "Y"],
        rows=[[1, 10], [2, 8], [3, 6], [4, 4], [5, 2]],
        source_format="csv",
        source_name="test.csv",
    )
    report = analyze_dataset(ds)
    assert len(report.correlations) == 1
    assert report.correlations[0].pearson_r == pytest.approx(-1.0, abs=0.01)


def test_correlations_insufficient_data():
    ds = TabularDataset(
        columns=["X", "Y"],
        rows=[[1, 2], [3, 4]],  # Only 2 observations, need 5
        source_format="csv",
        source_name="test.csv",
    )
    report = analyze_dataset(ds)
    assert len(report.correlations) == 0


# === Trends ===


def test_trend_up():
    ds = TabularDataset(
        columns=["Val"],
        rows=[[1], [2], [3], [4], [5]],
        source_format="csv",
        source_name="test.csv",
    )
    report = analyze_dataset(ds)
    assert len(report.trends) == 1
    assert report.trends[0].direction == "up"
    assert report.trends[0].slope > 0


def test_trend_down():
    ds = TabularDataset(
        columns=["Val"],
        rows=[[5], [4], [3], [2], [1]],
        source_format="csv",
        source_name="test.csv",
    )
    report = analyze_dataset(ds)
    assert report.trends[0].direction == "down"
    assert report.trends[0].slope < 0


def test_trend_flat():
    ds = TabularDataset(
        columns=["Val"],
        rows=[[5], [5], [5], [5], [5]],
        source_format="csv",
        source_name="test.csv",
    )
    report = analyze_dataset(ds)
    assert report.trends[0].direction == "flat"


# === Anomalies ===


def test_anomalies_detected():
    # Normal values tightly clustered around 10, with one extreme outlier at 1000
    rows = [[10], [10], [10], [10], [10], [10], [10], [10], [10], [10],
            [10], [10], [10], [10], [10], [10], [10], [10], [10], [1000]]
    ds = TabularDataset(
        columns=["Val"], rows=rows, source_format="csv", source_name="test.csv"
    )
    report = analyze_dataset(ds)
    assert len(report.anomalies) >= 1
    assert any(a.value == 1000 for a in report.anomalies)


def test_anomalies_none_for_normal_data():
    rows = [[10], [11], [10], [9], [10], [11], [10], [9], [10], [11]]
    ds = TabularDataset(
        columns=["Val"], rows=rows, source_format="csv", source_name="test.csv"
    )
    report = analyze_dataset(ds)
    assert len(report.anomalies) == 0


# === Pivot Preview ===


def test_pivot_preview_generated():
    ds = TabularDataset(
        columns=["Category", "Revenue"],
        rows=[
            ["A", 100], ["B", 200], ["A", 150], ["B", 250], ["A", 120],
        ],
        source_format="csv",
        source_name="test.csv",
    )
    report = analyze_dataset(ds)
    assert report.pivot_preview is not None
    assert "table" in report.pivot_preview
    assert "A" in report.pivot_preview["table"]


def test_pivot_preview_none_when_no_categorical():
    ds = TabularDataset(
        columns=["X", "Y"],
        rows=[[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]],
        source_format="csv",
        source_name="test.csv",
    )
    report = analyze_dataset(ds)
    assert report.pivot_preview is None


# === Build Analysis Tabs ===


def test_build_analysis_tabs_structure():
    ds = TabularDataset(
        columns=["Category", "Revenue"],
        rows=[["A", 100], ["B", 200], ["A", 150]],
        source_format="csv",
        source_name="test.csv",
    )
    report = analyze_dataset(ds)
    tabs = build_analysis_tabs(ds, report)

    # Should always have Uploaded_Data tab
    assert any(t.name == "Uploaded_Data" for t in tabs)
    # Should have Summary_Stats if there's numeric data
    assert any(t.name == "Summary_Stats" for t in tabs)
    # Each tab should have headers
    for tab in tabs:
        assert len(tab.headers) > 0
