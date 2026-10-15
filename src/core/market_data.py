"""Alpha Vantage market data client (Story 8.1, architecture §9.1).

Free-tier freshness (checked 2026-10-15, Alpha Vantage support page): realtime
and 15-minute delayed US data are premium-only, so free quotes are end-of-day
data "as of" the latest trading day. Every Quote carries that date (D-42).

`AlphaVantageClient` talks to the API and parses responses. `MarketData` adds
the disk cache (Story 8.2), request budgets, retries and the fallback chain
(Story 8.3). Every result says where its data came from, for freshness labels
(Story 8.4).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol

import httpx

from src.core.cache import DEFAULT_CACHE_DIR, DiskCache, utc_now
from src.core.freshness import DataLabel, DataSource, make_label
from src.core.rate_limit import RequestBudget, Sleep
from src.utils.logging import get_logger, log_event

logger = get_logger(__name__)

BASE_URL = "https://www.alphavantage.co/query"
_TICKER = re.compile(r"^[A-Z][A-Z.\-]{0,9}$")


class MarketDataError(Exception):
    """The request failed (network, server error, or an unexpected response)."""


class RateLimitError(MarketDataError):
    """Alpha Vantage refused the request because a usage limit was reached.

    It answers with a normal 200 response containing a "Note" or "Information"
    message instead of data, so this must be detected from the body.
    """


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    change: float
    change_percent: float  # e.g. 1.25 means +1.25%
    volume: int
    previous_close: float
    as_of: date  # the latest trading day the quote describes
    fetched_at: datetime  # when Finnie received it


@dataclass(frozen=True)
class PricePoint:
    day: date
    close: float
    volume: int


@dataclass(frozen=True)
class PriceHistory:
    symbol: str
    points: list[PricePoint]  # oldest first
    fetched_at: datetime

    @property
    def as_of(self) -> date | None:
        return self.points[-1].day if self.points else None


@dataclass(frozen=True)
class NotFound:
    """The ticker doesn't exist or has no data. A normal result, not an error."""

    symbol: str
    message: str = "We couldn't find that ticker. Check the symbol and try again."


def normalize_ticker(ticker: str) -> str | None:
    """Upper-case a ticker and return None if it can't be a valid US symbol."""
    symbol = (ticker or "").strip().upper()
    return symbol if _TICKER.match(symbol) else None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _check_limits(data: dict) -> None:
    for key in ("Note", "Information"):
        if key in data and len(data) == 1:
            raise RateLimitError(str(data[key])[:200])


class AlphaVantageClient:
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None, timeout: float = 15.0):
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=timeout)

    @classmethod
    def from_settings(cls, settings) -> AlphaVantageClient:
        """Build a client with the API key from configuration (D-25)."""
        return cls(settings.secrets.alpha_vantage_api_key.get_secret_value())

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, **params: str) -> dict:
        try:
            response = await self._client.get(BASE_URL, params={**params, "apikey": self._api_key})
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise MarketDataError(f"Alpha Vantage returned HTTP {exc.response.status_code}") from None
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError(f"Alpha Vantage request failed: {type(exc).__name__}") from None
        if not isinstance(data, dict):
            raise MarketDataError("Alpha Vantage returned an unexpected response")
        _check_limits(data)
        return data

    async def get_quote(self, ticker: str) -> Quote | NotFound:
        symbol = normalize_ticker(ticker)
        if symbol is None:
            return NotFound(ticker.strip().upper() if ticker else "")
        data = await self._get(function="GLOBAL_QUOTE", symbol=symbol)
        quote = data.get("Global Quote") or {}
        if not quote or "05. price" not in quote:
            return NotFound(symbol)
        try:
            return Quote(
                symbol=quote["01. symbol"],
                price=float(quote["05. price"]),
                change=float(quote["09. change"]),
                change_percent=float(quote["10. change percent"].rstrip("%")),
                volume=int(quote["06. volume"]),
                previous_close=float(quote["08. previous close"]),
                as_of=date.fromisoformat(quote["07. latest trading day"]),
                fetched_at=_now(),
            )
        except (KeyError, ValueError) as exc:
            raise MarketDataError(f"Unexpected quote format for {symbol}") from exc

    async def get_daily_history(self, ticker: str) -> PriceHistory | NotFound:
        """About the last 100 trading days of closing prices (enough for 3-month trends)."""
        symbol = normalize_ticker(ticker)
        if symbol is None:
            return NotFound(ticker.strip().upper() if ticker else "")
        data = await self._get(function="TIME_SERIES_DAILY", symbol=symbol, outputsize="compact")
        if "Error Message" in data:
            return NotFound(symbol)
        series = data.get("Time Series (Daily)")
        if not series:
            return NotFound(symbol)
        try:
            points = [
                PricePoint(date.fromisoformat(day), float(bar["4. close"]), int(bar["5. volume"]))
                for day, bar in series.items()
            ]
        except (KeyError, ValueError) as exc:
            raise MarketDataError(f"Unexpected price history format for {symbol}") from exc
        return PriceHistory(symbol, sorted(points, key=lambda p: p.day), _now())


# --- Cache, limits and fallbacks (Stories 8.2 and 8.3) -----------------------


@dataclass(frozen=True)
class Unavailable:
    """No live, cached or sample data. Shown as "price unavailable" (D-41)."""

    symbol: str
    message: str = "Price unavailable right now. Try again later."


@dataclass(frozen=True)
class MarketResult:
    """A market data answer plus where it came from, for freshness labels (Story 8.4)."""

    value: Quote | PriceHistory | NotFound | Unavailable
    fetched_at: datetime | None  # when the data was originally fetched; None if never
    source: DataSource

    @property
    def from_cache(self) -> bool:
        return self.source in (DataSource.CACHE, DataSource.STALE)

    def label(self, now: datetime | None = None) -> DataLabel | None:
        """The freshness label to show with this result (Story 8.4).

        None when there are no figures to label: an unknown ticker or no data at all.
        """
        if isinstance(self.value, (NotFound, Unavailable)):
            return None
        as_of = getattr(self.value, "as_of", None)
        return make_label(self.source, self.fetched_at, as_of, now or utc_now())


class MockProvider(Protocol):
    """Sample data for when nothing else is available (implemented in Story 8.6)."""

    def quote(self, symbol: str) -> Quote | None: ...

    def history(self, symbol: str) -> PriceHistory | None: ...


def _quote_to_dict(q: Quote) -> dict:
    return {**asdict(q), "as_of": q.as_of.isoformat(), "fetched_at": q.fetched_at.isoformat()}


def _quote_from_dict(d: dict) -> Quote:
    return Quote(**{**d, "as_of": date.fromisoformat(d["as_of"]), "fetched_at": datetime.fromisoformat(d["fetched_at"])})


def _history_to_dict(h: PriceHistory) -> dict:
    return {
        "symbol": h.symbol,
        "points": [[p.day.isoformat(), p.close, p.volume] for p in h.points],
        "fetched_at": h.fetched_at.isoformat(),
    }


def _history_from_dict(d: dict) -> PriceHistory:
    points = [PricePoint(date.fromisoformat(day), close, volume) for day, close, volume in d["points"]]
    return PriceHistory(d["symbol"], points, datetime.fromisoformat(d["fetched_at"]))


def _encode(value: Quote | PriceHistory | NotFound) -> dict:
    if isinstance(value, Quote):
        return {"type": "quote", "data": _quote_to_dict(value)}
    if isinstance(value, PriceHistory):
        return {"type": "history", "data": _history_to_dict(value)}
    return {"type": "not_found", "data": {"symbol": value.symbol}}


def _decode(record: dict) -> Quote | PriceHistory | NotFound:
    kind, data = record["type"], record["data"]
    if kind == "quote":
        return _quote_from_dict(data)
    if kind == "history":
        return _history_from_dict(data)
    return NotFound(data["symbol"])


class MarketData:
    """Market data with caching, request budgets, retries and fallbacks.

    Order for each request:
    1. a fresh cache entry (no API call),
    2. mock mode, if configured, goes straight to sample data,
    3. a live call, if the budget allows, with retries for temporary failures,
    4. otherwise a stale cache entry, then sample data, then "unavailable".

    The user never sees a raw error; every failure and fallback is logged.
    """

    def __init__(
        self,
        client: AlphaVantageClient,
        cache: DiskCache,
        budget: RequestBudget,
        quote_ttl_seconds: int,
        history_ttl_seconds: int,
        max_retries: int = 3,
        retry_base_seconds: float = 1.0,
        mock: MockProvider | None = None,
        mock_mode: bool = False,
        sleep: Sleep = asyncio.sleep,
    ):
        self.client = client
        self.cache = cache
        self.budget = budget
        self.ttl = {"quote": quote_ttl_seconds, "history": history_ttl_seconds}
        self.max_retries = max_retries
        self.retry_base_seconds = retry_base_seconds
        self.mock = mock
        self.mock_mode = mock_mode
        self.sleep = sleep

    @classmethod
    def from_settings(cls, settings, cache_dir: Path | None = None, mock: MockProvider | None = None) -> MarketData:
        directory = cache_dir or DEFAULT_CACHE_DIR
        market = settings.market
        budget = RequestBudget(
            directory / "limits" / "alpha_vantage.json",
            per_day=market.daily_limit,
            per_minute=market.per_minute_limit,
            min_interval_seconds=market.min_interval_seconds,
        )
        if mock is None:
            from src.core.mock_data import sample_market_data  # imported here to avoid a cycle

            mock = sample_market_data()
        return cls(
            AlphaVantageClient.from_settings(settings),
            DiskCache(directory, namespace="market"),
            budget,
            market.quote_ttl_seconds,
            market.history_ttl_seconds,
            max_retries=market.max_retries,
            mock=mock,
            mock_mode=market.mode == "mock",
        )

    async def get_quote(self, ticker: str) -> MarketResult:
        return await self._get("quote", ticker, self.client.get_quote)

    async def get_daily_history(self, ticker: str) -> MarketResult:
        return await self._get("history", ticker, self.client.get_daily_history)

    async def _get(self, kind: str, ticker: str, fetch) -> MarketResult:
        symbol = normalize_ticker(ticker)
        if symbol is None:
            return MarketResult(NotFound((ticker or "").strip().upper()), None, DataSource.LIVE)
        key = f"{kind}:{symbol}"

        entry = self.cache.get_fresh(key)
        if entry is not None:
            log_event(logger, "cache", result="hit", key=key)
            return MarketResult(_decode(entry.value), entry.fetched_at, DataSource.CACHE)
        if self.mock_mode:
            return self._fallback(kind, symbol, key, reason="mock_mode")

        log_event(logger, "cache", result="miss", key=key)
        try:
            value = await self._fetch_with_retries(fetch, symbol)
        except _BudgetExhausted:
            return self._fallback(kind, symbol, key, reason="budget")
        except RateLimitError as exc:
            self.budget.note_rejection(str(exc))
            return self._fallback(kind, symbol, key, reason="rate_limited")
        except MarketDataError as exc:
            return self._fallback(kind, symbol, key, reason="error", detail=str(exc))

        stored = self.cache.set(key, _encode(value), self.ttl[kind])
        return MarketResult(value, stored.fetched_at, DataSource.LIVE)

    async def _fetch_with_retries(self, fetch, symbol: str):
        for attempt in range(self.max_retries + 1):
            if not await self.budget.acquire():
                raise _BudgetExhausted
            try:
                log_event(logger, "api_call", service="alpha_vantage", symbol=symbol, attempt=attempt + 1)
                return await fetch(symbol)
            except RateLimitError:
                raise  # retrying a limit refusal only wastes requests
            except MarketDataError as exc:
                if attempt == self.max_retries:
                    raise
                delay = self.retry_base_seconds * 2**attempt
                log_event(logger, "retry", level=logging.WARNING, symbol=symbol, delay_s=delay, detail=str(exc))
                await self.sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover

    def _fallback(self, kind: str, symbol: str, key: str, reason: str, detail: str = "") -> MarketResult:
        stale = None if reason == "mock_mode" else self.cache.get(key)
        if stale is not None:
            log_event(logger, "fallback", level=logging.WARNING, to="stale_cache", key=key, reason=reason, detail=detail)
            return MarketResult(_decode(stale.value), stale.fetched_at, DataSource.STALE)
        sample = None
        if self.mock is not None:
            sample = self.mock.quote(symbol) if kind == "quote" else self.mock.history(symbol)
        if sample is not None:
            log_event(logger, "fallback", level=logging.WARNING, to="sample", key=key, reason=reason, detail=detail)
            return MarketResult(sample, None, DataSource.SAMPLE)
        log_event(logger, "fallback", level=logging.WARNING, to="unavailable", key=key, reason=reason, detail=detail)
        return MarketResult(Unavailable(symbol), None, DataSource.UNAVAILABLE)


class _BudgetExhausted(Exception):
    """Internal: the request budget is used up, so skip straight to fallbacks."""
