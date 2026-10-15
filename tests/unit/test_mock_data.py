"""Story 8.6: sample market and news data."""

import csv
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
import respx

from src.core.config import load_settings
from src.core.freshness import DataSource
from src.core.market_data import BASE_URL, MarketData
from src.core.mock_data import SampleMarketData, SampleNews, sample_market_data, sample_news
from src.core.news import SERPAPI_URL, NewsService

ROOT = Path(__file__).resolve().parents[2]
KEYS = {"OPENAI_API_KEY": "sk-x-123456", "ALPHA_VANTAGE_API_KEY": "a", "SERPAPI_API_KEY": "s"}


def sample_portfolio_tickers():
    tickers = set()
    for name in ("diversified.csv", "concentrated.csv", "missing_expense_ratios.csv"):
        with open(ROOT / "src" / "data" / "samples" / name, newline="") as f:
            tickers |= {row["ticker"] for row in csv.DictReader(f)}
    return tickers


def test_covers_markets_tickers_and_every_sample_portfolio_ticker():
    configured = set(load_settings(environ=dict(KEYS)).market.tickers)
    assert configured | sample_portfolio_tickers() <= sample_market_data().tickers


@pytest.mark.parametrize("symbol", sorted(SampleMarketData().tickers))
def test_quote_and_history_are_consistent(symbol):
    data = sample_market_data()
    quote, history = data.quote(symbol), data.history(symbol)
    assert quote.change == pytest.approx(quote.price - quote.previous_close)
    assert quote.change_percent == pytest.approx(quote.change / quote.previous_close * 100, abs=1e-4)
    assert len(history.points) == 100
    days = [p.day for p in history.points]
    assert days == sorted(days) and all(d.weekday() < 5 for d in days)
    assert history.as_of == quote.as_of
    assert history.points[-1].close == quote.price and history.points[-2].close == quote.previous_close
    assert all(p.close > 0 for p in history.points)


def test_history_is_identical_on_every_run():
    assert SampleMarketData().history("SPY") == SampleMarketData().history("SPY")
    assert SampleMarketData().history("SPY") != SampleMarketData().history("QQQ")


def test_unknown_ticker_has_no_sample_data():
    assert sample_market_data().quote("ZZZZ") is None and sample_market_data().history("$$$") is None


def test_news_matches_keywords_or_returns_everything():
    news = sample_news()
    rates = news.search("Federal Reserve interest rates")
    assert rates and all("rate" in i.title.lower() or "central bank" in i.title.lower() for i in rates)
    assert len(news.search("something unrelated")) == len(SampleNews()._items)


def test_news_items_are_clearly_samples_with_real_links():
    for item in sample_news().search("anything"):
        assert item.title.startswith("Sample:") and item.source == "Finnie sample data"
        assert item.link.startswith("https://") and item.published_at is None


def test_services_use_sample_data_by_default(tmp_path):
    settings = load_settings(config_path=tmp_path / "none.yaml", environ=dict(KEYS))
    assert isinstance(MarketData.from_settings(settings, cache_dir=tmp_path).mock, SampleMarketData)
    assert isinstance(NewsService.from_settings(settings, cache_dir=tmp_path).mock, SampleNews)


@respx.mock
async def test_mock_mode_serves_labeled_samples_without_any_api_call(tmp_path):
    av = respx.get(BASE_URL).mock(return_value=httpx.Response(500))
    serp = respx.get(SERPAPI_URL).mock(return_value=httpx.Response(500))
    settings = load_settings(config_path=tmp_path / "none.yaml", environ={**KEYS, "MARKET_DATA_MODE": "mock"})
    market = MarketData.from_settings(settings, cache_dir=tmp_path)
    news = NewsService.from_settings(settings, cache_dir=tmp_path)

    quote = await market.get_quote("VTI")
    history = await market.get_daily_history("AAPL")
    headlines = await news.search("stock market")

    assert quote.source is history.source is headlines.source is DataSource.SAMPLE
    assert quote.label().text == history.label().text == "Sample data · not real prices"
    assert headlines.label().text == "Sample data · not real prices"
    assert not av.called and not serp.called
    await market.client.aclose()
    await news.client.aclose()


@respx.mock
async def test_failing_api_with_nothing_cached_falls_back_to_the_sample(tmp_path):
    """End to end with the real sample data. (Stale cache beating the sample is tested in test_market_cache.)"""
    respx.get(BASE_URL).mock(return_value=httpx.Response(503))
    settings = load_settings(config_path=tmp_path / "none.yaml", environ={**KEYS, "FINNIE_MARKET__MAX_RETRIES": "0"})
    market = MarketData.from_settings(settings, cache_dir=tmp_path)
    market.budget.min_interval = timedelta(0)
    result = await market.get_quote("VTI")
    assert result.source is DataSource.SAMPLE  # nothing cached yet, so the sample is used
    await market.client.aclose()
