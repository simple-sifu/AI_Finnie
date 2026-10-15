"""Story 8.2: caching in front of the Alpha Vantage client."""

from datetime import date, datetime, timedelta, timezone

import pytest

from src.core.cache import DiskCache
from src.core.config import load_settings
from src.core.market_data import CachedMarketData, NotFound, PriceHistory, PricePoint, Quote

T0 = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


class FakeClient:
    """Counts API calls so tests can prove a cache hit made none."""

    def __init__(self):
        self.calls = []

    async def get_quote(self, symbol):
        self.calls.append(("quote", symbol))
        if symbol == "ZZZZ":
            return NotFound(symbol)
        return Quote(symbol, 376.88, -4.44, -1.16, 3262690, 381.32, date(2026, 10, 14), T0)

    async def get_daily_history(self, symbol):
        self.calls.append(("history", symbol))
        return PriceHistory(symbol, [PricePoint(date(2026, 10, 14), 376.88, 100)], T0)


@pytest.fixture
def setup(tmp_path):
    clock, client = Clock(), FakeClient()
    market = CachedMarketData(client, DiskCache(tmp_path, "market", clock), 1800, 86400)
    return market, client, clock, tmp_path


async def test_first_request_calls_the_api(setup):
    market, client, _, _ = setup
    result = await market.get_quote("vti")
    assert isinstance(result.value, Quote) and not result.from_cache
    assert client.calls == [("quote", "VTI")]


async def test_cache_hit_within_ttl_makes_no_api_call(setup):
    market, client, clock, _ = setup
    await market.get_quote("VTI")
    clock.now += timedelta(minutes=29)
    result = await market.get_quote("VTI")
    assert result.from_cache and result.value.price == 376.88
    assert result.fetched_at == T0  # the original fetch time, for "updated 29 min ago"
    assert client.calls == [("quote", "VTI")]


async def test_quote_refetches_after_30_minutes(setup):
    market, client, clock, _ = setup
    await market.get_quote("VTI")
    clock.now += timedelta(minutes=30)
    assert not (await market.get_quote("VTI")).from_cache
    assert len(client.calls) == 2


async def test_history_stays_cached_for_24_hours(setup):
    market, client, clock, _ = setup
    await market.get_daily_history("VTI")
    clock.now += timedelta(hours=23, minutes=59)
    assert (await market.get_daily_history("VTI")).from_cache
    clock.now += timedelta(minutes=1)
    assert not (await market.get_daily_history("VTI")).from_cache
    assert client.calls == [("history", "VTI"), ("history", "VTI")]


async def test_quote_and_history_are_cached_separately(setup):
    market, client, _, _ = setup
    await market.get_quote("VTI")
    await market.get_daily_history("VTI")
    assert client.calls == [("quote", "VTI"), ("history", "VTI")]


async def test_cache_survives_an_app_restart(setup):
    market, client, clock, directory = setup
    await market.get_quote("VTI")
    restarted = CachedMarketData(client, DiskCache(directory, "market", clock), 1800, 86400)
    result = await restarted.get_quote("VTI")
    assert result.from_cache and result.value == (await market.get_quote("VTI")).value
    assert len(client.calls) == 1


async def test_cached_values_round_trip_exactly(setup):
    market, _, _, _ = setup
    live_quote = (await market.get_quote("VTI")).value
    live_history = (await market.get_daily_history("VTI")).value
    assert (await market.get_quote("VTI")).value == live_quote
    assert (await market.get_daily_history("VTI")).value == live_history


async def test_not_found_is_cached_so_typos_cost_one_request(setup):
    market, client, _, _ = setup
    assert isinstance((await market.get_quote("ZZZZ")).value, NotFound)
    assert isinstance((await market.get_quote("zzzz")).value, NotFound)
    assert client.calls == [("quote", "ZZZZ")]


async def test_invalid_ticker_never_reaches_cache_or_api(setup):
    market, client, _, directory = setup
    result = await market.get_quote("$$$")
    assert isinstance(result.value, NotFound) and client.calls == []
    assert not (directory / "market").exists()


def test_from_settings_uses_configured_ttls(tmp_path):
    settings = load_settings(
        config_path=tmp_path / "none.yaml",
        environ={
            "OPENAI_API_KEY": "sk-x-123456", "ALPHA_VANTAGE_API_KEY": "a", "SERPAPI_API_KEY": "s",
            "QUOTE_CACHE_TTL_SECONDS": "600",
        },
    )
    market = CachedMarketData.from_settings(settings, cache_dir=tmp_path)
    assert market.ttl == {"quote": 600, "history": 86400}
    assert market.cache.directory == tmp_path / "market"
