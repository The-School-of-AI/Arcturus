"""Chart spec parsing, normalization, and type inference for Forge slides."""

import json
from typing import Any, Optional

from core.schemas.studio_schema import ChartSpec, ChartSeries, ChartType, ScatterPoint


def parse_chart_spec(content: Any) -> Optional[ChartSpec]:
    """Parse a SlideElement.content value into a ChartSpec.

    Accepts dict with categories/series or points, or a JSON string.
    Returns None if the content is not structured chart data.
    """
    data = content
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return None
    if not isinstance(data, dict):
        return None

    # Must have either series or points to be a valid chart spec
    has_series = bool(data.get("series") or data.get("categories"))
    has_points = bool(data.get("points"))
    if not has_series and not has_points:
        return None

    # Parse series
    series = []
    for s in data.get("series", []):
        if isinstance(s, dict) and "name" in s and "values" in s:
            values = []
            for v in s["values"]:
                try:
                    values.append(float(v))
                except (TypeError, ValueError):
                    values.append(0.0)
            series.append(ChartSeries(name=s["name"], values=values))

    # Parse points
    points = []
    for p in data.get("points", []):
        if isinstance(p, dict) and "x" in p and "y" in p:
            try:
                points.append(ScatterPoint(x=float(p["x"]), y=float(p["y"])))
            except (TypeError, ValueError):
                continue

    # Parse chart type
    chart_type = None
    ct_str = data.get("chart_type")
    if ct_str:
        try:
            chart_type = ChartType(ct_str)
        except ValueError:
            pass

    # Validate: scatter needs points, categorical needs series
    if chart_type == ChartType.scatter and not points:
        return None
    if chart_type in (ChartType.bar, ChartType.line, ChartType.pie, ChartType.funnel) and not series:
        return None

    spec = ChartSpec(
        chart_type=chart_type,
        title=data.get("title"),
        categories=data.get("categories", []),
        series=series,
        points=points,
        x_label=data.get("x_label"),
        y_label=data.get("y_label"),
    )

    # Infer chart type if not specified
    if spec.chart_type is None:
        spec.chart_type = infer_chart_type(spec)
        # If inference still fails (no data), return None
        if spec.chart_type is None:
            return None

    return spec


def normalize_chart_spec(spec: ChartSpec) -> ChartSpec:
    """Normalize a parsed ChartSpec for rendering.

    - Truncate category labels to 30 chars
    - Ensure series.values length matches categories length
    - Sort scatter points by x value
    """
    categories = [c[:30] for c in spec.categories]
    cat_len = len(categories)

    series = []
    for s in spec.series:
        values = list(s.values)
        if cat_len > 0:
            if len(values) < cat_len:
                values.extend([0.0] * (cat_len - len(values)))
            elif len(values) > cat_len:
                values = values[:cat_len]
        series.append(ChartSeries(name=s.name, values=values))

    points = sorted(spec.points, key=lambda p: p.x)

    return ChartSpec(
        chart_type=spec.chart_type,
        title=spec.title,
        categories=categories,
        series=series,
        points=points,
        x_label=spec.x_label,
        y_label=spec.y_label,
    )


def infer_chart_type(spec: ChartSpec) -> Optional[ChartType]:
    """Infer the best chart type when chart_type is ambiguous.

    Heuristic rules:
    - Has points -> scatter
    - Single series, all positive -> pie candidate
    - Multiple series -> line or bar (prefer bar for <= 6 categories)
    """
    if spec.points:
        return ChartType.scatter
    if not spec.series:
        return None
    if len(spec.series) == 1:
        values = spec.series[0].values
        if values and all(v >= 0 for v in values) and len(spec.categories) <= 6:
            return ChartType.pie
        return ChartType.bar
    # Multiple series
    if len(spec.categories) <= 6:
        return ChartType.bar
    return ChartType.line
