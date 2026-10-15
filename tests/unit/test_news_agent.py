"""Story 4.2: News Synthesizer Agent with mocked news and a fake LLM."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.agents.news import (
    DEFAULT_QUERY,
    FALLBACK_CITATIONS,
    NEWS_UNAVAILABLE,
    NO_NEWS,
    QUERY_PROMPT,
    NewsAgent,
    NewsQuery,
    NewsSummary,
    cited_items,
    format_headlines,
)
from src.core.cache import DiskCache
from src.core.config import load_settings
from src.core.freshness import DataSource
from src.core.models import AgentName, AgentRequest, ChatTurn, format_sources
from src.core.news import NewsError, NewsItem, NewsResult, NewsService
from src.core.rate_limit import MonthlyBudget

NOW = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)


def item(n, source=None, when=NOW - timedelta(hours=3)):
    return NewsItem(f"Headline {n}", source or f"Publisher {n}", f"https://news.example/{n}", when)


ITEMS = [item(n) for n in range(1, 6)]


class FakeNews:
    def __init__(self, result):
        self.result, self.queries = result, []

    async def search(self, query):
        self.queries.append(query)
        return self.result


class FakeLLM:
    def __init__(self, summary=None, query="stock market"):
        self.summary = summary or NewsSummary(answer="Stocks fell today.", response_type="education", relevant=True, used=[1, 3])
        self.query, self.calls = query, []

    async def structured(self, schema, system, user, history=None):
        self.calls.append({"schema": schema, "system": system, "user": user, "history": history})
        return NewsQuery(query=self.query) if schema is NewsQuery else self.summary


def live(items=ITEMS):
    return NewsResult("stock market", list(items), NOW, DataSource.LIVE)


def ask(message="What's in the financial news today?", result=None, llm=None, history=None):
    news = FakeNews(result if result is not None else live())
    llm = llm or FakeLLM()
    agent = NewsAgent(llm, "Not personalized advice.", news)
    response = asyncio.run(agent.run(AgentRequest(message=message, history=history or [])))
    return response, news, llm


# --- AC 1: through the news client ---


def test_a_news_search_query_is_made_from_the_message_and_conversation():
    history = [ChatTurn(role="user", content="How is Apple doing?")]
    _, news, llm = ask("Any news on that company?", history=history, llm=FakeLLM(query="Apple stock"))
    assert news.queries == ["Apple stock"]
    query_call = llm.calls[0]
    assert query_call["schema"] is NewsQuery and query_call["user"] == "Any news on that company?" and query_call["history"] == history


def test_queries_for_common_topics_are_canonical_so_the_cache_and_monthly_budget_are_reused():
    for exact in ('"stock market"', '"Federal Reserve interest rates"', '"inflation"'):
        assert exact in QUERY_PROMPT


def test_a_blank_query_falls_back_to_the_default():
    _, news, _ = ask(llm=FakeLLM(query="   "))
    assert news.queries == [DEFAULT_QUERY]


def test_cache_and_budget_apply_because_it_goes_through_the_news_service(tmp_path):
    class CountingClient:
        calls = 0

        async def search(self, query):
            CountingClient.calls += 1
            if CountingClient.calls > 1:
                raise NewsError("down")
            return ITEMS

    service = NewsService(CountingClient(), DiskCache(tmp_path, "news"), MonthlyBudget(tmp_path / "b.json", 100), 6 * 3600)
    agent = NewsAgent(FakeLLM(), "d", service)
    first = asyncio.run(agent.run(AgentRequest(message="news?")))
    second = asyncio.run(agent.run(AgentRequest(message="any news today?")))  # same canonical query
    assert CountingClient.calls == 1
    assert first.labels[0].text.startswith("Live") and second.labels[0].text.startswith("Cached")


# --- AC 2: plain-language summary that explains why it matters ---


def test_headlines_and_the_beginner_rules_go_to_the_llm():
    _, _, llm = ask()
    system = llm.calls[-1]["system"]
    assert "1. Headline 1 (Publisher 1, Oct 15)" in system and "5. Headline 5 (Publisher 5, Oct 15)" in system
    for rule in ("using ONLY the numbered headlines", "why this kind of news matters", "Don't add facts", "Never tell the user what to buy or sell"):
        assert rule in system
    assert "plain, everyday language" in system  # the shared beginner style


def test_the_llm_only_sees_the_configured_number_of_headlines():
    many = [item(n) for n in range(1, 20)]
    _, _, llm = ask(result=live(many))
    assert "8. Headline 8" in llm.calls[-1]["system"] and "9. Headline 9" not in llm.calls[-1]["system"]


# --- AC 3: every item cites its source and link ---


def test_only_the_headlines_the_llm_used_are_cited_with_publisher_date_and_link():
    response, _, _ = ask(llm=FakeLLM(NewsSummary(answer="x", response_type="education", relevant=True, used=[3, 1])))
    assert [s.title for s in response.sources] == ["Headline 3", "Headline 1"]  # in the order used
    first = response.sources[0]
    assert (first.url, first.source_name, first.category) == ("https://news.example/3", "Publisher 3", "News")
    assert first.published == NOW.date()
    assert format_sources(response.sources).splitlines()[1] == "- [Headline 3](https://news.example/3) (Oct 15), Publisher 3"


def test_bad_or_repeated_numbers_are_ignored_and_none_falls_back_to_the_first_few():
    assert [i.title for i in cited_items(ITEMS, [2, 2, 99, 0, -1])] == ["Headline 2"]
    assert len(cited_items(ITEMS, [])) == FALLBACK_CITATIONS and cited_items(ITEMS, [99])[0].title == "Headline 1"


def test_headlines_without_a_date_are_still_cited():
    response, _, _ = ask(result=live([item(1, when=None)]), llm=FakeLLM(NewsSummary(answer="x", response_type="education", relevant=True, used=[1])))
    assert response.sources[0].published is None and "(Oct" not in format_sources(response.sources)
    assert "1. Headline 1 (Publisher 1)" in format_headlines("q", [item(1, when=None)])


# --- AC 4: freshness labels, mock news labeled as sample data ---


def test_live_and_cached_labels_carry_the_newest_publication_date():
    response, _, _ = ask()
    assert [label.text for label in response.labels] == ["Live · as of Oct 15"]
    cached = NewsResult("q", ITEMS, datetime.now(timezone.utc) - timedelta(hours=2), DataSource.CACHE)
    response, _, _ = ask(result=cached)
    assert response.labels[0].text.startswith("Cached · updated 2 hr ago")


def test_sample_news_is_labeled_and_flagged_to_the_llm():
    sample = NewsResult("q", [NewsItem("Sample: Stocks slip", "Finnie sample data", "https://x/1", None)], None, DataSource.SAMPLE)
    response, _, llm = ask(result=sample, llm=FakeLLM(NewsSummary(answer="x", response_type="education", relevant=True, used=[1])))
    assert [label.text for label in response.labels] == ["Sample data · not real headlines"]
    assert "sample data, say they are examples" in llm.calls[-1]["system"]


# --- AC 5: no relevant news ---


def test_no_results_says_so_without_calling_the_summarizer():
    empty = NewsResult("zzz", [], NOW, DataSource.LIVE)
    response, _, llm = ask(result=empty)
    assert response.answer == NO_NEWS and response.sources == [] and [c["schema"] for c in llm.calls] == [NewsQuery]


def test_headlines_that_do_not_address_the_question_count_as_no_news():
    irrelevant = FakeLLM(NewsSummary(answer="ignored", response_type="education", relevant=False, used=[]))
    response, _, _ = ask("News about my neighbour's dog", llm=irrelevant)
    assert response.answer == NO_NEWS and response.sources == [] and response.labels == []


def test_news_that_cannot_be_fetched_is_not_guessed():
    unavailable = NewsResult("stock market", [], None, DataSource.UNAVAILABLE)
    response, _, llm = ask(result=unavailable)
    assert response.answer == NEWS_UNAVAILABLE and not response.error and [c["schema"] for c in llm.calls] == [NewsQuery]


# --- disclaimer, naming, wiring ---


@pytest.mark.parametrize("kind, shown", [("education", False), ("advice", True), ("uncertain", True)])
def test_advice_style_answers_get_the_disclaimer(kind, shown):
    summary = NewsSummary(answer="x", response_type=kind, relevant=True, used=[1])
    assert (ask(llm=FakeLLM(summary))[0].disclaimer is not None) is shown


def test_response_identifies_the_news_agent():
    response, _, _ = ask()
    assert response.agent is AgentName.NEWS and AgentName.NEWS.display_name == "News"


def test_it_is_registered_in_the_workflow(tmp_path, monkeypatch):
    from src.workflow import factory

    monkeypatch.setattr(factory, "create_retriever", lambda settings: None)
    keys = {"OPENAI_API_KEY": "sk-x-123456", "ALPHA_VANTAGE_API_KEY": "a", "SERPAPI_API_KEY": "s"}
    services = factory.build_services(load_settings(config_path=tmp_path / "none.yaml", environ=keys), cache_dir=tmp_path)
    assert isinstance(services.agents[AgentName.NEWS], NewsAgent) and services.agents[AgentName.NEWS].news is services.news
