"""Chart builders (front-end spec §5). Pure functions that return Plotly figures, so they can be tested.

Every chart has a title, labeled axes or a legend, and plain-language labels. Colors come from a
colorblind-safe palette; values are always printed on the chart, so color is never the only signal.
"""

from __future__ import annotations

import plotly.graph_objects as go
from plotly.colors import qualitative

MAX_PIE_SLICES = 8  # the rest are grouped as "Other" (front-end spec §5)
OTHER_COLOR = "#9aa0a6"
PALETTE = qualitative.Safe


def _layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(title={"text": title, "x": 0}, margin={"l": 10, "r": 10, "t": 50, "b": 10}, height=380)
    return fig


def holdings_pie(rows: list[dict], max_slices: int = MAX_PIE_SLICES) -> go.Figure | None:
    """What the portfolio holds, by value. More than `max_slices` holdings: the smallest become "Other"."""
    priced = sorted((r for r in rows if r.get("value")), key=lambda r: r["value"], reverse=True)
    if not priced:
        return None
    if len(priced) > max_slices:
        keep, rest = priced[: max_slices - 1], priced[max_slices - 1 :]
        labels = [r["ticker"] for r in keep] + [f"Other ({len(rest)} holdings)"]
        values = [r["value"] for r in keep] + [sum(r["value"] for r in rest)]
        colors = [PALETTE[i % len(PALETTE)] for i in range(len(keep))] + [OTHER_COLOR]
    else:
        labels = [r["ticker"] for r in priced]
        values = [r["value"] for r in priced]
        colors = [PALETTE[i % len(PALETTE)] for i in range(len(priced))]
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
