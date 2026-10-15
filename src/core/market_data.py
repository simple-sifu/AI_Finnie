"""Alpha Vantage market data client (Story 8.1, architecture §9.1).

Free-tier freshness (checked 2026-10-15, Alpha Vantage support page): realtime
and 15-minute delayed US data are premium-only, so free quotes are end-of-day
data "as of" the latest trading day. Every Quote carries that date (D-42).

This module only talks to the API and parses responses. Caching (Story 8.2),
request limits and fallbacks (Story 8.3) and freshness labels (Story 8.4) are
layered on top.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx

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
