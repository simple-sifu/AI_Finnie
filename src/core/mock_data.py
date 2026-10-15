"""Sample market and news data (Story 8.6).

Used only as the last fallback (Stories 8.3 and 8.5) or when mock mode is on
(MARKET_DATA_MODE=mock). Results are always labeled "Sample data" (Story 8.4).

Price history is generated from a fixed seed per ticker: a gentle random walk
of about 100 trading days that ends at the sample price. That gives realistic
looking trend charts with no large files, and the same numbers on every run.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np

from src.core.market_data import PriceHistory, PricePoint, Quote, normalize_ticker
from src.core.news import NewsItem, normalize_query

MOCK_DIR = Path(__file__).resolve().parents[1] / "data" / "mock"
HISTORY_DAYS = 100
SAMPLE_SOURCE = "Finnie sample data"


def _trading_days_ending(end: date, count: int) -> list[date]:
    """The last `count` weekdays up to and including `end` (holidays aren't modeled)."""
    days, day = [], end
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return sorted(days)


class SampleMarketData:
    """Implements market_data.MockProvider."""

    def __init__(self, path: Path = MOCK_DIR / "quotes.json"):
        data = json.loads(path.read_text())
        self.as_of = date.fromisoformat(data["as_of"])
        self._quotes: dict[str, dict] = data["quotes"]
        self._fetched_at = datetime.combine(self.as_of, time(21, 0), tzinfo=timezone.utc)

    @property
    def tickers(self) -> set[str]:
        return set(self._quotes)

    def quote(self, symbol: str) -> Quote | None:
        symbol = normalize_ticker(symbol) or ""
        q = self._quotes.get(symbol)
        if q is None:
            return None
        change = round(q["price"] - q["previous_close"], 4)
        return Quote(
            symbol=symbol,
            price=q["price"],
            change=change,
            change_percent=round(change / q["previous_close"] * 100, 4),
            volume=q["volume"],
            previous_close=q["previous_close"],
            as_of=self.as_of,
            fetched_at=self._fetched_at,
        )

    def history(self, symbol: str) -> PriceHistory | None:
        symbol = normalize_ticker(symbol) or ""
        q = self._quotes.get(symbol)
        if q is None:
            return None
        seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
        steps = np.random.default_rng(seed).normal(0.0004, 0.011, HISTORY_DAYS - 2)
        # Walk backwards from the previous close so the last two days match the quote.
        closes = [q["previous_close"]]
        for step in steps[::-1]:
            closes.append(closes[-1] / (1 + step))
        closes = [*closes[::-1], q["price"]]
        days = _trading_days_ending(self.as_of, HISTORY_DAYS)
        points = [PricePoint(day, round(close, 2), q["volume"]) for day, close in zip(days, closes)]
        return PriceHistory(symbol, points, self._fetched_at)


class SampleNews:
    """Implements news.MockNews: headlines matching the query's keywords, else all of them."""

    def __init__(self, path: Path = MOCK_DIR / "news.json"):
        self._items = json.loads(path.read_text())["items"]

    def search(self, query: str) -> list[NewsItem]:
        words = normalize_query(query)
        matching = [i for i in self._items if any(k in words for k in i["keywords"])]
        return [NewsItem(i["title"], SAMPLE_SOURCE, i["link"], None) for i in (matching or self._items)]


@lru_cache(maxsize=1)
def sample_market_data() -> SampleMarketData:
    return SampleMarketData()


@lru_cache(maxsize=1)
def sample_news() -> SampleNews:
    return SampleNews()
