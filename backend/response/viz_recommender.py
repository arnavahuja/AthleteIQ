"""
Deterministic visualization recommendation based on intent + data shape.
No LLM calls - pure rules.
"""

TIME_COLUMNS = {"date", "session_date", "week", "month", "year", "day", "time", "period"}
CATEGORICAL_COLUMNS = {"name", "athlete", "position", "team", "session_type", "kpi_name"}


def recommend_viz(intent: dict, columns: list[str], row_count: int) -> dict | None:
    """
    Recommend a visualization type based on intent and data shape.

    Returns:
        {
            "chart_type": "bar" | "line" | "grouped_bar" | None,
            "x_axis": "column_name",
            "y_axis": "column_name" | ["col1", "col2"],
            "title": "Chart Title",
        }
        or None if no visualization is appropriate.
    """
    if row_count == 0 or not columns:
        return None

    intent_type = intent.get("intent_type", "metric")
    viz_hint = intent.get("visualization_hint", "table")
    cols_lower = [c.lower() for c in columns]

    # Identify column types
    time_cols = [c for c in columns if c.lower() in TIME_COLUMNS]
    cat_cols = [c for c in columns if c.lower() in CATEGORICAL_COLUMNS]
    num_cols = [c for c in columns if c not in time_cols and c not in cat_cols]

    # Single value - no chart needed
    if row_count == 1 and len(columns) <= 2:
        return None

    # Too many rows for a meaningful chart
    if row_count > 20:
        return None

    # Trend: line chart if there's a time column
    if intent_type == "trend" and time_cols:
        x = time_cols[0]
        y = num_cols[0] if num_cols else columns[-1]
        return _build_config("line", x, y, f"{_humanize(y)} Over Time")

    # Comparison with multiple numeric columns -> grouped bar
    if intent_type == "comparison" and cat_cols and len(num_cols) >= 2:
        y_cols = num_cols[:3]
        return _build_config(
            "grouped_bar", cat_cols[0], y_cols,
            f"Comparison by {_humanize(cat_cols[0])}",
        )

    # Comparison or ranking with one numeric column -> bar chart
    if intent_type in ("comparison", "ranking") and cat_cols and num_cols:
        return _build_config(
            "bar", cat_cols[0], num_cols[0],
            f"{_humanize(num_cols[0])} by {_humanize(cat_cols[0])}",
        )

    # Fallback: if we have categorical + numeric, do bar chart
    if cat_cols and num_cols and row_count <= 15:
        chart_type = "line" if time_cols else "bar"
        x = cat_cols[0] if not time_cols else time_cols[0]
        return _build_config(
            chart_type, x, num_cols[0],
            f"{_humanize(num_cols[0])} by {_humanize(x)}",
        )

    # If viz_hint suggests something specific and we have the data
    if viz_hint == "line_chart" and len(columns) >= 2:
        return _build_config("line", columns[0], columns[1], f"{_humanize(columns[1])} Trend")

    if viz_hint == "bar_chart" and len(columns) >= 2:
        return _build_config("bar", columns[0], columns[1], f"{_humanize(columns[1])} by {_humanize(columns[0])}")

    return None


def _build_config(chart_type: str, x_axis, y_axis, title: str) -> dict:
    """Build a chart config with humanized axis labels."""
    config = {
        "chart_type": chart_type,
        "x_axis": x_axis,
        "y_axis": y_axis,
        "title": title,
        "x_label": _humanize(x_axis) if isinstance(x_axis, str) else "",
    }
    if isinstance(y_axis, list):
        config["y_label"] = " / ".join(_humanize(y) for y in y_axis)
    else:
        config["y_label"] = _humanize(y_axis) if isinstance(y_axis, str) else ""
    return config


def _humanize(col_name: str) -> str:
    """Convert column_name to Human Name."""
    return col_name.replace("_", " ").title()
