"""Story 4.4: all six agents work together in one conversation (D-16, Story 5.2).

The real router, workflow, agents and conversation state run; only the LLM, the
knowledge-base search, market prices and news are faked, so it needs no network.
The same conversation runs with the real model in tests/integration/test_six_agents_live.py.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.agents.base import LLMAnswer
from src.agents.finance_qa import FinanceQAAgent, GroundedAnswer
from src.agents.goal_planning import GoalExtraction, GoalPlanningAgent
from src.agents.market import MarketAgent
from src.agents.news import NewsAgent, NewsQuery, NewsSummary
from src.agents.portfolio import PortfolioAgent, PortfolioExplanation
from src.agents.tax import TaxAgent, TaxAnswer
from src.core.freshness import DataSource
from src.core.market_data import MarketResult, NotFound, PriceHistory, PricePoint, Quote
from src.core.models import AgentName
from src.core.news import NewsItem, NewsResult
from src.rag.chunking import Chunk
from src.rag.retriever import RetrievedChunk
from src.workflow.conversation import Conversation, plan_turn
from src.workflow.graph import FinnieWorkflow
from src.workflow.router import RouteDecision, Router

NOW = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
SAMPLES = Path(__file__).resolve().parents[2] / "src" / "data" / "samples"
DISCLAIMER = "Not personalized advice."
PRICES = {"VTI": 377.0, "VXUS": 72.5, "BND": 74.2, "VNQ": 92.8, "AAPL": 255.0}


class ScriptedLLM:
    """One fake LLM for the router and all six agents. The router follows a script; agents answer by schema."""

    def __init__(self, routes):
        self.routes, self.calls = list(routes), []

    async def structured(self, schema, system, user, history=None):
        name = schema.__name__
        self.calls.append(SimpleNamespace(schema=name, system=system, user=user, history=list(history or [])))
        if name == "RouteDecision":
            return RouteDecision(route=self.routes.pop(0), confidence=0.9)
        if name == "GroundedAnswer":
            return GroundedAnswer(answer="An ETF is a fund that trades like a stock.", response_type="education", answered_from_content=True)
        if name == "TaxAnswer":
            return TaxAnswer(answer="Taking money out early usually triggers a 10% additional tax, though Roth contributions can come out first.",
                             response_type="advice", answered_from_content=True)
        if name == "GoalExtraction":
            return GoalExtraction(target_amount=20000, years=4, current_savings=3000)
        if name == "NewsQuery":
            return NewsQuery(query="stock market")
        if name == "NewsSummary":
            return NewsSummary(answer="According to Reuters, stocks fell on inflation worries.", response_type="education", relevant=True, used=[1])
        if name == "PortfolioExplanation":
            return PortfolioExplanation(answer="Your portfolio is well spread out.", response_type="education", includes_recommendation=False)
        assert name == "LLMAnswer", name
        label = "goal" if "savings plan" in system else "market"
        return LLMAnswer(answer=f"{label} explanation", response_type="education")


class FakeRetriever:
    """Returns chunks for the requested categories and records each search."""

    def __init__(self):
        self.searches = []
        self.chunks = [
            RetrievedChunk(Chunk("etf#0", "ETFs\n\nAn ETF is a fund.", "article", "etf", "What Is an ETF?", "ETFs & Mutual Funds", "SEC", "https://x/etf"), 0.9),
            RetrievedChunk(Chunk("early#0", "Early\n\nA 10% additional tax usually applies before age 59½.", "article", "early",
                                 "Early Withdrawals from Retirement Accounts", "Retirement & Tax Accounts", "IRS", "https://x/early"), 0.9),
        ]

    async def retrieve(self, query, k=None, categories=None):
        self.searches.append({"query": query, "categories": categories})
        return [c for c in self.chunks if categories is None or c.chunk.category in categories]


class FakeMarket:
    async def get_quote(self, ticker):
        if ticker not in PRICES:
            return MarketResult(NotFound(ticker), NOW, DataSource.LIVE)
        price = PRICES[ticker]
        return MarketResult(Quote(ticker, price, -1.0, -0.3, 1000, price + 1, date(2026, 10, 14), NOW), NOW, DataSource.LIVE)

    async def get_daily_history(self, ticker):
        points = [PricePoint(date(2026, 10, 14) - timedelta(days=100 - i), 300.0 + i, 1) for i in range(100)]
        return MarketResult(PriceHistory(ticker, points, NOW), NOW, DataSource.LIVE)


class FakeNews:
    async def search(self, query):
        item = NewsItem("Stocks fall on inflation worries", "Reuters", "https://news.example/1", NOW)
        return NewsResult(query, [item], NOW, DataSource.LIVE)


def build(routes):
    llm, retriever = ScriptedLLM(routes), FakeRetriever()
    agents = {
        AgentName.FINANCE_QA: FinanceQAAgent(llm, DISCLAIMER, retriever),
        AgentName.PORTFOLIO: PortfolioAgent(llm, DISCLAIMER, FakeMarket()),
        AgentName.MARKET: MarketAgent(llm, DISCLAIMER, FakeMarket()),
        AgentName.GOAL_PLANNING: GoalPlanningAgent(llm, DISCLAIMER, today=lambda: date(2026, 10, 15)),
        AgentName.NEWS: NewsAgent(llm, DISCLAIMER, FakeNews()),
        AgentName.TAX: TaxAgent(llm, DISCLAIMER, retriever),
    }
    return FinnieWorkflow(Router(llm, 0.5), agents, DISCLAIMER), llm, retriever


SCRIPT = [
    ("What is an ETF?", "finance_qa", None),
    ("How is VTI doing?", "market", None),
    ("I want $20,000 in 4 years for a house. I have $3,000, and I keep it in a Roth IRA.", "goal_planning", None),  # asks for risk tolerance
    ("moderate", None, None),  # the answer: stored in the profile, then the goal question is answered
    ("Would I owe taxes if I take it out early?", "tax", None),
    ("What's in the financial news today?", "news", None),
    ("Is my portfolio diversified?", "portfolio", {"csv": (SAMPLES / "diversified.csv").read_bytes()}),
]


@pytest.fixture(scope="module")
def run():
    routes = [route for _, route, _ in SCRIPT if route]
    # "moderate" is answered through the workflow again with the original goal question, so it needs a route too.
    routes.insert(3, "goal_planning")
    workflow, llm, retriever = build(routes)
    conversation, turns, per_turn_calls = Conversation(), [], []
    for text, _, payload in SCRIPT:
        before = len(llm.calls)
        plan = plan_turn(conversation, text)
        response = plan.reply or asyncio.run(workflow.run(conversation.request(plan.message, 10, payload)))
        conversation.add(text, response, asked=plan.message)
        turns.append(response)
        per_turn_calls.append(llm.calls[before:])
    return SimpleNamespace(conversation=conversation, turns=turns, calls=per_turn_calls, llm=llm, retriever=retriever)


def test_all_six_agents_answer_in_one_session(run):
    assert {r.agent for r in run.turns} == set(AgentName)
    assert [r.agent for r in run.turns] == [
        AgentName.FINANCE_QA, AgentName.MARKET, AgentName.GOAL_PLANNING, AgentName.GOAL_PLANNING,
        AgentName.TAX, AgentName.NEWS, AgentName.PORTFOLIO,
    ]
    assert not any(r.error for r in run.turns)


def test_each_question_reaches_exactly_one_agent(run):
    """D-16: every turn is one router call plus the work of a single agent."""
    assert [[c.schema for c in calls] for calls in run.calls] == [
        ["RouteDecision", "GroundedAnswer"],  # finance_qa
        ["RouteDecision", "LLMAnswer"],  # market (explicit ticker, so no ticker lookup)
        ["RouteDecision"],  # goal planning asks for the risk tolerance first
        ["RouteDecision", "GoalExtraction", "LLMAnswer"],  # ... then plans
        ["RouteDecision", "TaxAnswer"],  # tax
        ["RouteDecision", "NewsQuery", "NewsSummary"],  # news
        ["RouteDecision", "PortfolioExplanation"],  # portfolio
    ]


def test_the_session_state_holds_the_whole_conversation(run):
    conversation = run.conversation
    assert len(conversation.exchanges) == 7 and conversation.last_agent is AgentName.PORTFOLIO
    assert conversation.profile.risk_tolerance == "moderate"  # stored from the chat answer
    assert conversation.pending is None


def test_every_agent_sees_the_turns_handled_by_other_agents(run):
    def history_of(turn):
        agent_calls = [c for c in run.calls[turn] if c.schema != "RouteDecision"]
        return [t.content for t in agent_calls[-1].history]

    assert history_of(1) == ["What is an ETF?", "An ETF is a fund that trades like a stock."]  # market sees Finance Q&A
    assert "How is VTI doing?" in history_of(4) and "market explanation" in history_of(4)  # tax sees market and goal turns
    # The portfolio agent, last to answer, sees the market, goal, tax and news turns. The history is limited to the
    # most recent 10 messages (chat.history_turns), so the very first exchange has dropped out by now.
    last = history_of(6)
    assert len(last) == 10 and "How is VTI doing?" in last and "According to Reuters, stocks fell on inflation worries." in last
    assert "What is an ETF?" not in last


def test_the_profile_set_during_goal_planning_reaches_the_later_agents(run):
    for turn in (4, 5, 6):  # tax, news, portfolio
        system = [c for c in run.calls[turn] if c.schema != "RouteDecision"][-1].system
        assert "risk tolerance is moderate" in system


def test_a_tax_question_that_relies_on_an_earlier_goal_planning_turn_is_answered(run):
    """AC 3: "it" means the Roth IRA mentioned while planning the goal."""
    tax = run.turns[4]
    assert tax.agent is AgentName.TAX and "Roth" in tax.answer and tax.disclaimer == DISCLAIMER
    assert [s.title for s in tax.sources] == ["Early Withdrawals from Retirement Accounts"]  # only the tax category
    tax_call = [c for c in run.calls[4] if c.schema == "TaxAnswer"][0]
    assert any("Roth IRA" in turn.content for turn in tax_call.history)  # the model can see the Roth IRA mention
    assert run.retriever.searches[-1]["categories"] == ["Retirement & Tax Accounts"]


def test_the_router_is_told_which_agent_answered_last(run):
    router_systems = [calls[0].system for calls in run.calls]
    assert "previous answer" not in router_systems[0]
    assert "(finance_qa)" in router_systems[1] and "(market)" in router_systems[2]
    assert "(goal_planning)" in router_systems[4] and "(tax)" in router_systems[5] and "(news)" in router_systems[6]


def test_no_coming_soon_replies_remain(run):
    assert all("coming soon" not in r.answer.lower() for r in run.turns)
