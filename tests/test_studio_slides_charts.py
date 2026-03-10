"""Tests for core/studio/slides/charts.py — chart spec parsing."""

from core.schemas.studio_schema import ChartType
from core.studio.slides.charts import infer_chart_type, normalize_chart_spec, parse_chart_spec


def test_parse_bar_chart_spec():
    spec = parse_chart_spec({
        "chart_type": "bar",
        "title": "Revenue",
        "categories": ["Q1", "Q2", "Q3"],
        "series": [{"name": "Rev", "values": [1.0, 2.0, 3.0]}],
    })
    assert spec is not None
    assert spec.chart_type == ChartType.bar
    assert len(spec.categories) == 3
    assert len(spec.series) == 1


def test_parse_line_chart_spec():
    spec = parse_chart_spec({
        "chart_type": "line",
        "categories": ["Jan", "Feb"],
        "series": [{"name": "Growth", "values": [10.0, 20.0]}],
    })
    assert spec is not None
    assert spec.chart_type == ChartType.line


def test_parse_pie_chart_spec():
    spec = parse_chart_spec({
        "chart_type": "pie",
        "categories": ["A", "B", "C"],
        "series": [{"name": "Share", "values": [40.0, 35.0, 25.0]}],
    })
    assert spec is not None
    assert spec.chart_type == ChartType.pie


def test_parse_scatter_chart_spec():
    spec = parse_chart_spec({
        "chart_type": "scatter",
        "points": [{"x": 1.0, "y": 2.0}, {"x": 3.0, "y": 4.0}],
    })
    assert spec is not None
    assert spec.chart_type == ChartType.scatter
    assert len(spec.points) == 2


def test_parse_funnel_chart_spec():
    spec = parse_chart_spec({
        "chart_type": "funnel",
        "categories": ["Top", "Middle", "Bottom"],
        "series": [{"name": "Funnel", "values": [100.0, 60.0, 20.0]}],
    })
    assert spec is not None
    assert spec.chart_type == ChartType.funnel


def test_parse_string_returns_none():
    assert parse_chart_spec("Revenue growth chart") is None


def test_parse_empty_dict_returns_none():
    assert parse_chart_spec({}) is None


def test_parse_missing_chart_type_infers():
    spec = parse_chart_spec({
        "categories": ["A", "B", "C"],
        "series": [{"name": "Data", "values": [10.0, 20.0, 30.0]}],
    })
    assert spec is not None
    assert spec.chart_type is not None  # Should be inferred


def test_normalize_truncates_categories():
    spec = parse_chart_spec({
        "chart_type": "bar",
        "categories": ["A" * 50, "B"],
        "series": [{"name": "S", "values": [1.0, 2.0]}],
    })
    normalized = normalize_chart_spec(spec)
    assert len(normalized.categories[0]) == 30


def test_normalize_pads_values():
    spec = parse_chart_spec({
        "chart_type": "bar",
        "categories": ["A", "B", "C"],
        "series": [{"name": "S", "values": [1.0]}],
    })
    normalized = normalize_chart_spec(spec)
    assert len(normalized.series[0].values) == 3
    assert normalized.series[0].values[1] == 0.0


def test_normalize_trims_values():
    spec = parse_chart_spec({
        "chart_type": "bar",
        "categories": ["A"],
        "series": [{"name": "S", "values": [1.0, 2.0, 3.0]}],
    })
    normalized = normalize_chart_spec(spec)
    assert len(normalized.series[0].values) == 1


def test_normalize_sorts_scatter_points():
    spec = parse_chart_spec({
        "chart_type": "scatter",
        "points": [{"x": 5.0, "y": 1.0}, {"x": 1.0, "y": 2.0}, {"x": 3.0, "y": 3.0}],
    })
    normalized = normalize_chart_spec(spec)
    assert normalized.points[0].x == 1.0
    assert normalized.points[-1].x == 5.0


def test_infer_chart_type_scatter():
    from core.schemas.studio_schema import ChartSpec, ScatterPoint
    spec = ChartSpec(points=[ScatterPoint(x=1.0, y=2.0)])
    assert infer_chart_type(spec) == ChartType.scatter


def test_infer_chart_type_pie():
    from core.schemas.studio_schema import ChartSeries, ChartSpec
    spec = ChartSpec(
        categories=["A", "B", "C"],
        series=[ChartSeries(name="S", values=[10.0, 20.0, 30.0])],
    )
    assert infer_chart_type(spec) == ChartType.pie
