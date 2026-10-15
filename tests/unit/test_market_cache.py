"""Stories 8.2 and 8.3: caching, budgets, retries and fallbacks in MarketData."""

import logging
from datetime import date, datetime, timedelta, timezone

import pytest

from src.core.cache import DiskCache
from src.core.config import load_settings
from src.core.market_data import (
    DataSource,
    MarketData,
    MarketDataError,
    NotFound,
    PriceHistory,
    PricePoint,
    Quote,
    RateLimitError,
    Unavailable,
)
from src.core.rate_limit import RequestBudget

T0 = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
KEYS = {"OPENAI_API_KEY": "sk-x-123456", "ALPHA_VANTAGE_API_KEY": "a", "SERPAPI_API_KEY": "s"}


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


def quote(symbol="VTI", price=376.88):
    return Quote(symbol, price, -4.44, -1.16, 3262690, 381.32, date(2026, 10, 14), T0)


class FakeClient:
    """Counts API calls; `failures` holds exceptions to raise on the next calls."""

    def __init__(self):
        self.calls = []
        self.failures = []

    async def get_quote(self, symbol):
        self.calls.append(("quote", symbol))
        if self.failures:
            raise self.failures.pop(0)
        return NotFound(symbol) if symbol == "ZZZZ" else quote(symbol)

    async def get_daily_history(self, symbol):
        self.calls.append(("history", symbol))
        if self.failures:
            raise self.failures.pop(0)
        return PriceHistory(symbol, [PricePoint(date(2026, 10, 14), 376.88, 100)], T0)


class FakeMock:
    def quote(self, symbol):
        return quote(symbol, price=100.0) if symbol in {"VTI", "SPY"} else None

    def history(self, symbol):
        return None


@pytest.fixture
def env(tmp_path):
    clock, client, sleeps = Clock(), FakeClient(), []

    async def sleep(seconds):
        sleeps.append(seconds)
        clock.now += timedelta(seconds=seconds)

    def make(per_day=25, per_minute=5, mock=FakeMock(), mock_mode=False):
        budget = RequestBudget(tmp_path / "limits.json", per_day, per_minute, 0, clock=clock, sleep=sleep)
        return MarketData(
            client, DiskCache(tmp_path, "market", clock), budget, 1800, 86400,
            max_retries=3, retry_base_seconds=1.0, mock=mock, mock_mode=mock_mode, sleep=sleep,
        )

    return make, client, clock, sleeps


# --- Story 8.2: caching ---


async def test_first_request_is_live_then_cached(env):
    make, client, clock, _ = env
    market = make()
    first = await market.get_quote("vti")
    assert first.source is DataSource.LIVE and not first.from_cache
    clock.now += timedelta(minutes=29)
    second = await market.get_quote("VTI")
    assert second.source is DataSource.CACHE and second.from_cache and second.fetched_at == T0
    assert client.calls == [("quote", "VTI")]


async def test_quote_refetches_after_30_minutes_history_after_24_hours(env):
    make, client, clock, _ = env
    market = make()
    await market.get_quote("VTI")
    await market.get_daily_history("VTI")
    clock.now += timedelta(minutes=30)
    assert (await market.get_quote("VTI")).source is DataSource.LIVE
    assert (await market.get_daily_history("VTI")).source is DataSource.CACHE
    clock.now += timedelta(hours=24)
    assert (await market.get_daily_history("VTI")).source is DataSource.LIVE


async def test_cache_survives_restart_and_round_trips(env):
    make, client, _, _ = env
    live = (await make().get_quote("VTI")).value
    cached = await make().get_quote("VTI")  # a new instance, like an app restart
    assert cached.source is DataSource.CACHE and cached.value == live
    assert len(client.calls) == 1


async def test_not_found_is_cached_and_invalid_ticker_never_calls(env):
    make, client, _, _ = env
    market = make()
    assert isinstance((await market.get_quote("ZZZZ")).value, NotFound)
    assert isinstance((await market.get_quote("zzzz")).value, NotFound)
    assert isinstance((await market.get_quote("$$$")).value, NotFound)
    assert client.calls == [("quote", "ZZZZ")]


# --- Story 8.3: budgets ---


async def test_budget_used_up_falls_back_without_calling(env):
    make, client, _, _ = env
    market = make(per_day=1)
    await market.get_quote("VTI")
    result = await market.get_quote("SPY")
    assert result.source is DataSource.SAMPLE and result.value.price == 100.0
    assert client.calls == [("quote", "VTI")]


async def test_budget_used_up_prefers_stale_cache(env):
    make, client, clock, _ = env
    market = make(per_day=1)
    await market.get_quote("VTI")
    clock.now += timedelta(hours=2)  # expired, but kept
    result = await market.get_quote("VTI")
    assert result.source is DataSource.STALE and result.fetched_at == T0 and result.value.price == 376.88
    assert len(client.calls) == 1


async def test_nothing_anywhere_is_unavailable(env):
    make, _, _, _ = env
    result = await make(per_day=0).get_quote("MSFT")
    assert result.source is DataSource.UNAVAILABLE and isinstance(result.value, Unavailable)
    assert "unavailable" in result.value.message.lower() and result.fetched_at is None


async def test_no_mock_provider_still_never_errors(env):
    make, _, _, _ = env
    result = await make(per_day=0, mock=None).get_quote("VTI")
    assert result.source is DataSource.UNAVAILABLE


# --- Story 8.3: limit refusals and retries ---


async def test_limit_refusal_is_not_retried_and_blocks_further_calls(env):
    make, client, _, sleeps = env
    market = make()
    client.failures = [RateLimitError("1 request per second")]
    result = await market.get_quote("VTI")
    assert result.source is DataSource.SAMPLE
    assert len(client.calls) == 1 and sleeps == []
    await market.get_quote("SPY")  # blocked for a minute: no new call
    assert len(client.calls) == 1


async def test_temporary_failures_are_retried_with_exponential_backoff(env):
    make, client, _, sleeps = env
    client.failures = [MarketDataError("HTTP 503"), MarketDataError("timeout")]
    result = await make().get_quote("VTI")
    assert result.source is DataSource.LIVE
    assert len(client.calls) == 3 and sleeps == [1.0, 2.0]


async def test_retries_stop_after_the_configured_attempts(env):
    make, client, _, sleeps = env
    client.failures = [MarketDataError("HTTP 503")] * 10
    result = await make().get_quote("VTI")
    assert result.source is DataSource.SAMPLE
    assert len(client.calls) == 4 and sleeps == [1.0, 2.0, 4.0]


async def test_retries_count_against_the_budget(env):
    make, client, _, _ = env
    client.failures = [MarketDataError("HTTP 503")] * 10
    await make(per_day=2).get_quote("VTI")
    assert len(client.calls) == 2


# --- Story 8.3: mock mode and logging ---


async def test_mock_mode_never_calls_the_api(env):
    make, client, _, _ = env
    result = await make(mock_mode=True).get_quote("VTI")
    assert result.source is DataSource.SAMPLE and client.calls == []


async def test_every_failure_and_fallback_is_logged(env, caplog):
    make, client, _, _ = env
    client.failures = [MarketDataError("HTTP 503")] * 10
    with caplog.at_level(logging.INFO, logger="src.core.market_data"):
        await make().get_quote("VTI")
    text = caplog.text
    assert "cache result=miss" in text and "api_call service=alpha_vantage" in text
    assert text.count("retry ") == 3 and "fallback to=sample" in text and "reason=error" in text


def test_from_settings_wires_config(tmp_path):
    settings = load_settings(config_path=tmp_path / "none.yaml", environ={**KEYS, "MARKET_DATA_MODE": "mock"})
    market = MarketData.from_settings(settings, cache_dir=tmp_path)
    assert market.mock_mode and market.ttl == {"quote": 1800, "history": 86400}
    assert market.budget.per_day == 25 and market.budget.per_minute == 5
    assert market.budget.min_interval == timedelta(seconds=1)
    assert market.budget.state_file == tmp_path / "limits" / "alpha_vantage.json"
