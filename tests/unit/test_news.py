"""Story 8.5: SerpApi news search with caching, a monthly budget and fallbacks."""

import logging
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from src.core.cache import DiskCache
from src.core.config import ConfigError, load_settings
from src.core.freshness import DataSource
from src.core.news import (
    SERPAPI_URL,
    NewsError,
    NewsItem,
    NewsLimitError,
    NewsResult,
    NewsService,
    SerpApiClient,
    normalize_query,
    parse_results,
)
from src.core.rate_limit import MonthlyBudget

T0 = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
KEYS = {"OPENAI_API_KEY": "sk-x-123456", "ALPHA_VANTAGE_API_KEY": "a", "SERPAPI_API_KEY": "serp-key"}


def article(n, iso="2026-10-15T01:56:00Z"):
    return {"title": f"Headline {n}", "source": {"name": f"Publisher {n}"}, "link": f"https://news.example/{n}", "iso_date": iso}


SAMPLE = {
    "news_results": [
        {"title": "News about Nasdaq", "stories": [article(1), article(2, "2026-10-14T20:43:00Z")]},
        article(3),
        article(1),  # duplicate link, dropped
        {"title": "No link here"},
        *[article(n) for n in range(4, 20)],
    ]
}


# --- parsing ---


def test_parse_flattens_clusters_drops_duplicates_and_caps_at_10():
    items = parse_results(SAMPLE)
    assert len(items) == 10
    assert [i.title for i in items[:3]] == ["Headline 1", "Headline 2", "Headline 3"]
    assert items[0] == NewsItem("Headline 1", "Publisher 1", "https://news.example/1", datetime(2026, 10, 15, 1, 56, tzinfo=timezone.utc))


def test_parse_handles_missing_dates_and_sources():
    items = parse_results({"news_results": [{"title": "T", "link": "https://x/1", "iso_date": "not a date"}]})
    assert items == [NewsItem("T", "Unknown source", "https://x/1", None)]
    assert parse_results({}) == []


def test_normalize_query():
    assert normalize_query("  Stock   MARKET\n") == "stock market"


# --- client ---


@pytest.fixture
async def client():
    c = SerpApiClient("serp-key")
    yield c
    await c.aclose()


@respx.mock
async def test_client_searches_us_google_news(client):
    call = respx.get(SERPAPI_URL).mock(return_value=httpx.Response(200, json=SAMPLE))
    items = await client.search("stock market")
    params = call.calls.last.request.url.params
    assert (params["engine"], params["gl"], params["hl"], params["q"]) == ("google_news", "us", "en", "stock market")
    assert len(items) == 10


@respx.mock
async def test_out_of_searches_raises_limit_error(client):
    respx.get(SERPAPI_URL).mock(return_value=httpx.Response(429, json={"error": "Your account has run out of searches."}))
    with pytest.raises(NewsLimitError):
        await client.search("x")


@respx.mock
async def test_no_results_is_an_empty_list(client):
    respx.get(SERPAPI_URL).mock(
        return_value=httpx.Response(200, json={"error": "Google News hasn't returned any results for this query."})
    )
    assert await client.search("zzzz qqqq") == []


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, json={"error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"}),
        httpx.Response(500, json={"news_results": []}),
        httpx.Response(200, text="<html>down</html>"),
        httpx.Response(200, json=["unexpected"]),
    ],
)
@respx.mock
async def test_other_problems_raise_news_error_without_the_key(client, response):
    respx.get(SERPAPI_URL).mock(return_value=response)
    with pytest.raises(NewsError) as error:
        await client.search("x")
    assert not isinstance(error.value, NewsLimitError) and "serp-key" not in str(error.value)


@respx.mock
async def test_network_error_raises_news_error(client):
    respx.get(SERPAPI_URL).mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(NewsError, match="ConnectError"):
        await client.search("x")


# --- service ---


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


class FakeClient:
    def __init__(self):
        self.calls, self.failures = [], []

    async def search(self, query):
        self.calls.append(query)
        if self.failures:
            raise self.failures.pop(0)
        return [NewsItem("Fed holds rates", "Reuters", "https://r/1", T0 - timedelta(hours=1))]


class FakeMock:
    def search(self, query):
        return [NewsItem("Sample headline", "Finnie sample data", "https://example.com/sample", None)]


@pytest.fixture
def env(tmp_path):
    clock, client = Clock(), FakeClient()

    def make(per_month=100, mock=FakeMock(), mock_mode=False):
        budget = MonthlyBudget(tmp_path / "serp.json", per_month, clock=clock)
        return NewsService(client, DiskCache(tmp_path, "news", clock), budget, 6 * 3600, mock=mock, mock_mode=mock_mode)

    return make, client, clock


async def test_live_search_then_cached_for_6_hours(env):
    make, client, clock = env
    news = make()
    first = await news.search("Fed Rates")
    assert first.source is DataSource.LIVE and first.items[0].title == "Fed holds rates"
    clock.now += timedelta(hours=5, minutes=59)
    cached = await news.search("  fed   rates ")
    assert cached.source is DataSource.CACHE and cached.items == first.items
    clock.now += timedelta(minutes=1)
    assert (await news.search("fed rates")).source is DataSource.LIVE
    assert client.calls == ["fed rates", "fed rates"]


async def test_monthly_budget_used_up_falls_back_to_stale_then_sample(env):
    make, client, clock = env
    news = make(per_month=1)
    await news.search("fed rates")
    clock.now += timedelta(hours=7)
    stale = await news.search("fed rates")
    assert stale.source is DataSource.STALE and stale.items[0].title == "Fed holds rates"
    sample = await news.search("earnings season")
    assert sample.source is DataSource.SAMPLE and sample.items[0].source == "Finnie sample data"
    assert len(client.calls) == 1


async def test_out_of_searches_blocks_the_rest_of_the_month(env):
    make, client, _ = env
    news = make()
    client.failures = [NewsLimitError("no searches left")]
    assert (await news.search("a")).source is DataSource.SAMPLE
    await news.search("b")
    assert client.calls == ["a"] and news.budget.remaining() == 0


async def test_errors_fall_back_and_never_raise(env):
    make, client, _ = env
    client.failures = [NewsError("SerpApi returned HTTP 500")]
    assert (await make(mock=None).search("a")).source is DataSource.UNAVAILABLE


async def test_mock_mode_never_calls_serpapi(env):
    make, client, _ = env
    assert (await make(mock_mode=True).search("fed")).source is DataSource.SAMPLE and client.calls == []


async def test_empty_query_does_nothing(env):
    make, client, _ = env
    result = await make().search("   ")
    assert result.items == [] and client.calls == []


async def test_fallbacks_are_logged(env, caplog):
    make, client, _ = env
    client.failures = [NewsError("SerpApi returned HTTP 500")]
    with caplog.at_level(logging.INFO, logger="src.core.news"):
        await make().search("fed")
    assert "api_call service=serpapi" in caplog.text and "fallback to=sample" in caplog.text


# --- labels ---


def test_news_labels_use_the_newest_publication_date():
    items = [NewsItem("a", "s", "l1", datetime(2026, 10, 14, 20, tzinfo=timezone.utc)), NewsItem("b", "s", "l2", datetime(2026, 10, 15, 2, tzinfo=timezone.utc))]
    assert NewsResult("q", items, T0, DataSource.LIVE).label(T0).text == "Live · as of Oct 15"
    cached = NewsResult("q", items, T0 - timedelta(hours=2), DataSource.CACHE)
    assert cached.label(T0).text == "Cached · updated 2 hr ago · as of Oct 15"
    assert NewsResult("q", [], None, DataSource.UNAVAILABLE).label(T0) is None


# --- configuration ---


def test_from_settings(tmp_path):
    settings = load_settings(config_path=tmp_path / "none.yaml", environ=dict(KEYS))
    news = NewsService.from_settings(settings, cache_dir=tmp_path)
    assert news.ttl_seconds == 21600 and news.budget.per_month == 100
    assert news.budget.state_file == tmp_path / "limits" / "serpapi.json"


def test_tavily_provider_is_not_available_in_v1(tmp_path):
    settings = load_settings(
        config_path=tmp_path / "none.yaml",
        environ={**KEYS, "FINNIE_NEWS__PROVIDER": "tavily", "TAVILY_API_KEY": "tv-123456"},
    )
    with pytest.raises(ConfigError, match="Tavily"):
        NewsService.from_settings(settings, cache_dir=tmp_path)


def test_an_article_without_a_date_is_kept_with_no_date():
    items = parse_results({"news_results": [{"title": "T", "link": "https://x/1"}]})
    assert [i.published_at for i in items] == [None]


def test_from_settings_accepts_a_custom_sample_provider(tmp_path):
    settings = load_settings(config_path=tmp_path / "none.yaml", environ=dict(KEYS))
    provider = FakeMock()
    assert NewsService.from_settings(settings, cache_dir=tmp_path, mock=provider).mock is provider


@respx.mock
async def test_an_out_of_searches_message_in_an_ordinary_response_is_a_limit_too(client):
    respx.get(SERPAPI_URL).mock(return_value=httpx.Response(200, json={"error": "Your account has run out of searches."}))
    with pytest.raises(NewsLimitError):
        await client.search("x")


@respx.mock
async def test_a_failure_while_reading_a_response_is_a_news_error_not_a_crash(client, monkeypatch):
    from src.core import news as news_module

    def broken(data, limit=10):
        raise TypeError("unexpected structure")

    monkeypatch.setattr(news_module, "parse_results", broken)
    respx.get(SERPAPI_URL).mock(return_value=httpx.Response(200, json={"news_results": []}))
    with pytest.raises(NewsError, match="unexpected response"):
        await client.search("x")
