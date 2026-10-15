"""Chart builders (front-end spec §5). Pure functions that return Plotly figures, so they can be tested.

Every chart has a title, labeled axes or a legend, and plain-language labels. Colors come from a
colorblind-safe palette; values are always printed on the chart, so color is never the only signal.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.colors import qualitative

MAX_PIE_SLICES = 8  # the rest are grouped as "Other" (front-end spec §5)
OTHER_COLOR = "#9aa0a6"
PALETTE = qualitative.Safe


def _layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(title={"text": title, "x": 0}, margin={"l": 10, "r": 10, "t": 50, "b": 10}, height=380)
    return fig


def pie_slices(rows: list[dict], max_slices: int = MAX_PIE_SLICES) -> list[tuple[str, float, str]]:
    """(label, value, color) for each slice, largest first. More than `max_slices`: the smallest become "Other".

    The pie and its "Show as table" table both come from this, so they always show the same data.
    """
    priced = sorted((r for r in rows if r.get("value")), key=lambda r: r["value"], reverse=True)
    if len(priced) > max_slices:
        keep, rest = priced[: max_slices - 1], priced[max_slices - 1 :]
        slices = [(r["ticker"], r["value"], PALETTE[i % len(PALETTE)]) for i, r in enumerate(keep)]
        return [*slices, (f"Other ({len(rest)} holdings)", sum(r["value"] for r in rest), OTHER_COLOR)]
    return [(r["ticker"], r["value"], PALETTE[i % len(PALETTE)]) for i, r in enumerate(priced)]


def holdings_pie(rows: list[dict], max_slices: int = MAX_PIE_SLICES) -> go.Figure | None:
    """What the portfolio holds, by value. More than `max_slices` holdings: the smallest become "Other"."""
    slices = pie_slices(rows, max_slices)
    if not slices:
        return None
    labels, values, colors = [list(column) for column in zip(*slices)]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.35, sort=False, marker={"colors": colors},
        textinfo="label+percent", hovertemplate="%{label}: $%{value:,.2f} (%{percent})<extra></extra>",
    ))
    fig.update_layout(legend={"title": {"text": "Holding"}})
    return _layout(fig, "What you own")


def allocation_bar(allocation: dict[str, float]) -> go.Figure | None:
    """Share of the portfolio by type of investment, largest first, with the percentage on each bar."""
    if not allocation:
        return None
    items = sorted(allocation.items(), key=lambda kv: kv[1], reverse=True)
    names = [name for name, _ in items]
    percents = [round(share * 100, 1) for _, share in items]
    fig = go.Figure(go.Bar(
        x=percents, y=names, orientation="h", text=[f"{p:g}%" for p in percents], textposition="outside",
        marker={"color": [PALETTE[i % len(PALETTE)] for i in range(len(items))]},
        hovertemplate="%{y}: %{x}%<extra></extra>",
    ))
    fig.update_xaxes(title_text="Share of your portfolio (%)", range=[0, max(percents) * 1.2 + 5])
    fig.update_yaxes(title_text="Type of investment", autorange="reversed")  # largest at the top
    return _layout(fig, "Your mix of investments")


TREND_DAYS = 63  # about 3 months of trading days
TREND_COLOR = PALETTE[1]


def price_trend(symbol: str, points: list[tuple[str, float]], days: int = TREND_DAYS) -> go.Figure | None:
    """A line chart of a ticker's recent closing prices. `points` are (ISO date, close), oldest first."""
    recent = points[-days:]
    if len(recent) < 2:
        return None
    dates, closes = [d for d, _ in recent], [c for _, c in recent]
    fig = go.Figure(go.Scatter(
        x=dates, y=closes, mode="lines", line={"color": TREND_COLOR, "width": 2},
        hovertemplate="%{x|%b %d, %Y}: $%{y:,.2f}<extra></extra>",
    ))
    fig.update_xaxes(title_text="Date")
    fig.update_yaxes(title_text="Closing price ($)", tickprefix="$")
    return _layout(fig, f"{symbol}: last 3 months")


def goal_projection(plan) -> go.Figure | None:
    """The projected balance year by year, with the goal as a dashed horizontal line (Story 7.4)."""
    if len(plan.schedule) < 2:
        return None
    years = [months / 12 for months, _ in plan.schedule]
    balances = [balance for _, balance in plan.schedule]
    fig = go.Figure(go.Scatter(
        x=years, y=balances, mode="lines+markers", line={"color": TREND_COLOR, "width": 2}, name="Projected balance",
        hovertemplate="Year %{x:.1f}: $%{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(
        y=plan.target_amount, line_dash="dash", line_color="#d62728",
        annotation_text=f"Goal: ${plan.target_amount:,.0f}", annotation_position="top left",
    )
    fig.update_xaxes(title_text="Years from now", rangemode="tozero")
    fig.update_yaxes(title_text="Balance ($)", tickprefix="$", rangemode="tozero")
    fig.update_layout(showlegend=False)
    return _layout(fig, f"Your path to ${plan.target_amount:,.0f}")


# --- the same data as tables ("Show as table", front-end spec §5 and Story 7.5) ----------------------------


def holdings_pie_table(rows: list[dict], max_slices: int = MAX_PIE_SLICES) -> pd.DataFrame:
    slices = pie_slices(rows, max_slices)
    total = sum(value for _, value, _ in slices) or 1
    return pd.DataFrame({
        "Holding": [label for label, _, _ in slices],
        "Value": [f"${value:,.2f}" for _, value, _ in slices],
        "Share of portfolio": [f"{value / total * 100:.1f}%" for _, value, _ in slices],
    })


def allocation_table(allocation: dict[str, float]) -> pd.DataFrame:
    items = sorted(allocation.items(), key=lambda kv: kv[1], reverse=True)
    return pd.DataFrame({
        "Type of investment": [name for name, _ in items],
        "Share of portfolio": [f"{round(share * 100, 1):g}%" for _, share in items],
    })


def price_trend_table(points: list[tuple[str, float]], days: int = TREND_DAYS) -> pd.DataFrame:
    recent = points[-days:]
    return pd.DataFrame({"Date": [d for d, _ in recent], "Closing price": [f"${c:,.2f}" for _, c in recent]})


def goal_projection_table(plan) -> pd.DataFrame:
    return pd.DataFrame({
        "Years from now": [f"{months / 12:g}" for months, _ in plan.schedule],
        "Projected balance": [f"${balance:,.2f}" for _, balance in plan.schedule],
        "Goal": [f"${plan.target_amount:,.2f}"] * len(plan.schedule),
    })
