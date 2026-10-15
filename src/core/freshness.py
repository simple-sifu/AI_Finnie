"""Freshness labels for market and news data (Story 8.4, D-24, D-42).

Every figure Finnie shows from an external service carries one of three labels
so beginners never mistake old or sample numbers for current ones. Wording and
colors follow the front-end spec §3.1:

    Live · as of Oct 14 close
    Cached · updated 12 min ago · as of Oct 14 close
    Sample data · not real prices

Alpha Vantage's free tier is end-of-day data (architecture §9.1), so a quote's
"as of" is the close of its trading day, not the moment it was fetched.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum


class DataSource(str, Enum):
    """Where a result came from (set by the data services in Stories 8.3 and 8.5)."""

    LIVE = "live"  # fetched from the service just now
    CACHE = "cache"  # from the cache, still within its TTL
    STALE = "stale"  # from an expired cache entry, because live data was unavailable
    SAMPLE = "sample"  # mock data (Story 8.6)
    UNAVAILABLE = "unavailable"  # nothing available at all


class Freshness(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    SAMPLE = "sample"


_COLORS = {Freshness.LIVE: "green", Freshness.CACHED: "amber", Freshness.SAMPLE: "grey"}
_FRESHNESS = {
    DataSource.LIVE: Freshness.LIVE,
    DataSource.CACHE: Freshness.CACHED,
    DataSource.STALE: Freshness.CACHED,
    DataSource.SAMPLE: Freshness.SAMPLE,
}


@dataclass(frozen=True)
class DataLabel:
    freshness: Freshness
    fetched_at: datetime | None  # when Finnie got the data
    as_of: date | datetime | None  # the data's own date: a trading day's close, or a news date
    text: str

    @property
    def color(self) -> str:
        """Dot color for the UI. The word in `text` always carries the meaning too (Story 7.5)."""
        return _COLORS[self.freshness]


def describe_age(age: timedelta) -> str:
    """Plain-language age: "just now", "12 min ago", "3 hr ago", "2 days ago"."""
    minutes = int(age.total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hr ago"
    days = hours // 24
    return f"{days} day{'s' if days != 1 else ''} ago"


def describe_as_of(as_of: date | datetime, closing: bool = True) -> str:
    """"as of Oct 14 close" for a trading day; "as of Oct 14" for other dates."""
    day = as_of.date() if isinstance(as_of, datetime) else as_of
    text = f"as of {day:%b} {day.day}"
    return f"{text} close" if closing else text


def make_label(
    source: DataSource,
    fetched_at: datetime | None,
    as_of: date | datetime | None,
    now: datetime,
    closing: bool = True,
) -> DataLabel | None:
    """Label a result. Returns None for UNAVAILABLE, which has no data to label.

    `closing=True` describes `as_of` as a market close (quotes, price history);
    use False for news, whose date is a publication date.
    """
    freshness = _FRESHNESS.get(source)
    if freshness is None:
        return None
    if freshness is Freshness.SAMPLE:
        return DataLabel(freshness, None, None, "Sample data · not real prices")

    parts = ["Live" if freshness is Freshness.LIVE else "Cached"]
    if freshness is Freshness.CACHED and fetched_at is not None:
        parts.append(f"updated {describe_age(now - fetched_at)}")
    if as_of is not None:
        parts.append(describe_as_of(as_of, closing))
    return DataLabel(freshness, fetched_at, as_of, " · ".join(parts))
