"""Story 3.3: Portfolio Analysis Agent with fixed prices and a fake LLM."""

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.agents.portfolio import UPLOAD_PROMPT, PortfolioAgent, PortfolioExplanation
from src.core.freshness import DataSource
from src.core.market_data import MarketResult, NotFound, Quote, Unavailable
from src.core.models import AgentName, AgentRequest, SessionProfile

SAMPLES = Path(__file__).resolve().parents[2] / "src" / "data" / "samples"
NOW = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
PRICES = {"VTI": 300.0, "VXUS": 60.0, "BND": 70.0, "VNQ": 90.0, "AAPL": 200.0, "TSLA": 400.0,
          "VOO": 500.0, "QQQ": 450.0, "SCHB": 25.0, "MSFT": 400.0}


class FixedMarket:
    def __init__(self, prices=PRICES, unavailable=()):
        self.prices, self.unavailable, self.calls = prices, set(unavailable), []

    async def get_quote(self, ticker):
        self.calls.append(ticker)
        if ticker in self.unavailable:
            return MarketResult(Unavailable(ticker), None, DataSource.UNAVAILABLE)
        if ticker not in self.prices:
            return MarketResult(NotFound(ticker), NOW, DataSource.LIVE)
        quote = Quote(ticker, self.prices[ticker], 0, 0, 1, self.prices[ticker], date(2026, 10, 14), NOW)
        return MarketResult(quote, NOW, DataSource.LIVE)


class FakeLLM:
    def __init__(self, recommends=True, kind="education"):
        self.reply = PortfolioExplanation(answer="Here's your portfolio.", response_type=kind, includes_recommendation=recommends)
        self.calls = []

    async def structured(self, schema, system, user, history=None):
        self.calls.append(system)
        return self.reply


def analyze(sample=None, csv=None, market=None, llm=None, profile=None):
    llm = llm or FakeLLM()
    agent = PortfolioAgent(llm, "Not personalized advice.", market or FixedMarket())
    payload = None
    if sample:
        payload = {"csv": (SAMPLES / sample).read_bytes()}
    elif csv is not None:
        payload = {"csv": csv}
    request = AgentRequest(message="Analyze my portfolio", payload=payload, profile=profile or SessionProfile())
    return asyncio.run(agent.run(request)), llm


def test_without_an_upload_it_asks_for_one():
    response, llm = analyze()
    assert response.answer == UPLOAD_PROMPT and response.needs_input == "holdings" and llm.calls == []


def test_malformed_file_lists_each_problem_and_nothing_crashes():
    response, llm = analyze("malformed_bad_values.csv")
    assert "Row 2: shares is not a number ('forty')." in response.answer
    assert len(response.data["problems"]) == 4 and llm.calls == [] and not response.error


def test_diversified_sample_metrics():
    response, llm = analyze("diversified.csv")
    m = response.data["metrics"]
    # 40*300 + 60*60 + 50*70 + 15*90 + 5*200 = 12000 + 3600 + 3500 + 1350 + 1000
    assert m.total_value == 21450
    assert m.weights["VTI"] == pytest.approx(12000 / 21450)
    expected_er = (12000 * 0.03 + 3600 * 0.05 + 3500 * 0.03 + 1350 * 0.13 + 1000 * 0) / 21450
    assert m.weighted_expense_ratio == pytest.approx(expected_er) and m.expense_ratio_coverage == pytest.approx(1.0)
    assert m.diversification_label == "High" and m.concentrated == []
    assert response.agent is AgentName.PORTFOLIO


def test_numbers_go_to_the_llm_which_only_explains():
    response, llm = analyze("diversified.csv")
    system = llm.calls[0]
    assert "Total value: $21,450.00" in system and "Use ONLY the numbers given" in system
    assert "Diversification score:" in system and "Risk level:" in system


def test_recommendations_are_advice_with_a_disclaimer():
    response, _ = analyze("diversified.csv", llm=FakeLLM(recommends=True))
    assert response.response_type == "advice" and response.disclaimer
    response, _ = analyze("diversified.csv", llm=FakeLLM(recommends=False))
    assert response.response_type == "education" and response.disclaimer is None


def test_prices_carry_freshness_labels():
    response, _ = analyze("diversified.csv")
    assert [label.text for label in response.labels] == ["Live · as of Oct 14 close"]
    assert all(row["label"] == "Live · as of Oct 14 close" for row in response.data["holdings"])


def test_concentrated_sample_flags_two_stocks_and_high_risk():
    response, _ = analyze("concentrated.csv")
    m = response.data["metrics"]
    # AAPL 16000, TSLA 16000, VOO 1000 -> both stocks about 48%
    assert m.concentrated == ["AAPL", "TSLA"] and m.risk_level == "High"
    # Two stocks at ~48% each -> 1/N_eff ~ 0.47 -> score 53, labeled Low (below 60).
    assert m.diversification_score == 53 and m.diversification_label == "Low"


def test_missing_expense_ratios_are_filled_from_the_table():
    response, _ = analyze("missing_expense_ratios.csv")
    rows = {row["ticker"]: row for row in response.data["holdings"]}
    assert rows["QQQ"]["expense_ratio_source"] == "table" and rows["QQQ"]["expense_ratio"] == 0.18
    assert rows["VOO"]["expense_ratio_source"] == "file"
    assert rows["MSFT"]["assumed_stock"] and rows["MSFT"]["asset_type"] == "individual_stock"
    assert any("MSFT is treated as an individual stock" in note for note in response.data["notes"])


def test_unpriced_holdings_are_noted_and_left_out():
    response, _ = analyze("diversified.csv", market=FixedMarket(unavailable={"VNQ"}))
    m = response.data["metrics"]
    assert m.unpriced == ["VNQ"] and m.total_value == 21450 - 1350
    assert "VNQ: price unavailable, so it's left out of the totals." in response.data["notes"]


def test_no_prices_at_all_gives_a_friendly_message_without_the_llm():
    response, llm = analyze("diversified.csv", market=FixedMarket(prices={}))
    assert "couldn't get prices" in response.answer and llm.calls == []


def test_risk_mismatch_with_the_session_profile_is_noted():
    response, llm = analyze("concentrated.csv", profile=SessionProfile(risk_tolerance="conservative"))
    assert any("risk level is High" in note for note in response.data["notes"])
    assert "risk tolerance is conservative" in llm.calls[0]


def test_unknown_mutual_fund_is_reported():
    response, _ = analyze(csv="ticker,shares\nVTSAX,10\n", market=FixedMarket(prices={"VTSAX": 140.0}))
    assert any("VTSAX's expense ratio is unknown" in note for note in response.data["notes"])
