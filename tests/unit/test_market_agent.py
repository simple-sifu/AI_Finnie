"""Story 3.4: Market Analysis Agent with mocked market data and a fake LLM."""

import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest

from src.agents.base import LLMAnswer
from src.agents.market import ASK_FOR_TICKER, MARKET_PROXY, MarketAgent, TickerRequest, explicit_tickers
from src.core.freshness import DataSource
from src.core.market_data import MarketResult, NotFound, PriceHistory, PricePoint, Quote, Unavailable
from src.core.models import AgentName, AgentRequest

NOW = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
DAY = date(2026, 10, 14)


def history(symbol, closes):
    points = [PricePoint(DAY - timedelta(days=len(closes) - 1 - i), c, 1) for i, c in enumerate(closes)]
    return PriceHistory(symbol, points, NOW)


class FakeMarket:
    def __init__(self, source=DataSource.LIVE, unavailable=()):
        self.source, self.unavailable, self.calls = source, set(unavailable), []
        self.data = {"VTI": (376.88, 381.32), "SPY": (769.6, 778.0), "AAPL": (255.0, 258.9)}

    async def get_quote(self, ticker):
        self.calls.append(("quote", ticker))
        if ticker in self.unavailable:
            return MarketResult(Unavailable(ticker), None, DataSource.UNAVAILABLE)
        if ticker not in self.data:
            return MarketResult(NotFound(ticker), NOW, DataSource.LIVE)
        price, prev = self.data[ticker]
        q = Quote(ticker, price, round(price - prev, 2), round((price - prev) / prev * 100, 4), 1, prev, DAY, NOW)
        # Labels use the real clock, so a cached entry is timestamped 12 minutes before the real now.
        fetched = datetime.now(timezone.utc) - timedelta(minutes=12) if self.source is DataSource.CACHE else NOW
        return MarketResult(q, fetched, self.source)

    async def get_daily_history(self, ticker):
        self.calls.append(("history", ticker))
        closes = [300.0] * 30 + [350.0] * 34 + [376.88]
        return MarketResult(history(ticker, closes), NOW, self.source)


class FakeLLM:
    def __init__(self, kind="education", extracted=None):
        self.kind, self.extracted, self.calls = kind, extracted, []

    async def structured(self, schema, system, user, history=None):
        self.calls.append((schema, system))
        if schema is TickerRequest:
            return self.extracted or TickerRequest(tickers=[], overall_market=False)
        return LLMAnswer(answer="VTI fell a little yesterday.", response_type=self.kind)


def ask(message, market=None, llm=None, payload=None):
    market, llm = market or FakeMarket(), llm or FakeLLM()
    response = asyncio.run(MarketAgent(llm, "Not personalized advice.", market).run(AgentRequest(message=message, payload=payload)))
    return response, market, llm


def test_explicit_ticker_skips_the_extraction_call():
    response, market, llm = ask("How is VTI doing?")
    assert market.calls == [("quote", "VTI"), ("history", "VTI")]
    assert [schema for schema, _ in llm.calls] == [LLMAnswer]
    assert response.agent is AgentName.MARKET and response.answer == "VTI fell a little yesterday."


def test_numbers_and_trends_are_calculated_in_code_and_sent_to_the_llm():
    response, _, llm = ask("How is VTI doing?")
    system = llm.calls[-1][1]
    assert "VTI: price $376.88, change -4.44 (-1.16%) from the previous close of $381.32" in system
    assert "1 week +7.68%" in system and "3 months +25.63%" in system
    assert "Use ONLY the numbers given" in system and "Don't predict future prices" in system
    changes = response.data["tickers"][0]["changes"]
    assert changes == {"1 week": 7.68, "1 month": 7.68, "3 months": 25.63}


def test_every_figure_carries_a_freshness_label():
    response, _, llm = ask("How is VTI doing?", market=FakeMarket(DataSource.CACHE))
    texts = [label.text for label in response.labels]
    assert "Cached · updated 12 min ago · as of Oct 14 close" in texts
    assert "[Cached · updated 12 min ago · as of Oct 14 close]" in llm.calls[-1][1]
    assert response.data["tickers"][0]["label"].startswith("Cached")


def test_names_are_mapped_to_tickers_by_the_llm():
    llm = FakeLLM(extracted=TickerRequest(tickers=["aapl"], overall_market=False))
    _, market, _ = ask("How is Apple stock doing?", llm=llm)
    assert ("quote", "AAPL") in market.calls


def test_general_market_questions_use_the_s_and_p_500():
    llm = FakeLLM(extracted=TickerRequest(tickers=[], overall_market=True))
    _, market, _ = ask("How's the stock market today?", llm=llm)
    assert market.calls[0] == ("quote", MARKET_PROXY)


def test_no_ticker_asks_which_one():
    response, market, _ = ask("Tell me about that thing")
    assert response.answer == ASK_FOR_TICKER and response.needs_input == "ticker" and market.calls == []


def test_markets_tab_can_pass_the_ticker_directly():
    _, market, llm = ask("Explain this", payload={"ticker": "spy"})
    assert market.calls[0] == ("quote", "SPY") and [s for s, _ in llm.calls] == [LLMAnswer]


def test_unknown_ticker_gets_the_friendly_not_found_message():
    response, _, llm = ask("How is ZZZZ doing?")
    assert response.answer == "We couldn't find that ticker. Check the symbol and try again."
    assert llm.calls == []


def test_one_unknown_among_several_is_mentioned_to_the_llm():
    response, _, llm = ask("Compare VTI and ZZZZ")
    assert response.data["not_found"] == ["ZZZZ"] and "Not found" in llm.calls[-1][1]


def test_unavailable_price_is_described_honestly():
    _, _, llm = ask("How is VTI doing?", market=FakeMarket(unavailable={"VTI"}))
    assert "VTI: no price available right now." in llm.calls[-1][1]


@pytest.mark.parametrize("kind, has_disclaimer", [("advice", True), ("uncertain", True), ("education", False)])
def test_advice_answers_get_the_disclaimer(kind, has_disclaimer):
    response, _, _ = ask("Should I buy VTI?", llm=FakeLLM(kind=kind))
    assert (response.disclaimer is not None) is has_disclaimer


def test_at_most_three_tickers_are_looked_up():
    assert len(explicit_tickers("VTI VOO SPY QQQ DIA")) == 3


class MixedMarket(FakeMarket):
    """Live quote, but the history request fell back to sample data."""

    async def get_daily_history(self, ticker):
        result = await super().get_daily_history(ticker)
        return MarketResult(result.value, None, DataSource.SAMPLE)


def test_sample_trend_is_never_paired_with_a_real_price():
    response, _, llm = ask("How is VTI doing?", market=MixedMarket())
    system = llm.calls[-1][1]
    assert "Trend: not available right now." in system and "1 week" not in system
    assert response.data["tickers"][0]["changes"] == {}
    assert [l.text for l in response.labels] == ["Live · as of Oct 14 close"]


def test_all_sample_data_is_marked_in_plain_words_for_the_llm():
    response, _, llm = ask("How is VTI doing?", market=FakeMarket(DataSource.SAMPLE))
    system = llm.calls[-1][1]
    assert system.count("SAMPLE DATA, NOT REAL PRICES") == 2  # price line and trend line
    assert response.data["tickers"][0]["changes"]["1 week"] == 7.68


def test_trend_values_are_plain_floats():
    response, _, _ = ask("How is VTI doing?")
    assert all(type(v) is float for v in response.data["tickers"][0]["changes"].values())
