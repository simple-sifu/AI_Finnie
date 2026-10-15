"""Story 9.2 AC 1 and AC 2: questions through the whole path, with outside services mocked.

Everything runs for real from the workflow down to the HTTP calls (see support.py): the router, the
agents, the knowledge-base search with the real embedding model, the data clients, caches and budgets,
and the real OpenAI client library. Only the responses of OpenAI, Alpha Vantage and SerpApi are faked.
"""

from pathlib import Path

import pytest

from src.agents.base import AGENT_FAILED, LLM_UNAVAILABLE, RISK_QUESTION
from src.core.models import AgentName
from src.workflow.graph import OFF_TOPIC_REPLY

SAMPLES = Path(__file__).resolve().parents[2] / "src" / "data" / "samples"
DIVERSIFIED = (SAMPLES / "diversified.csv").read_bytes()
CONCENTRATED = (SAMPLES / "concentrated.csv").read_bytes()
LIVE_LABEL = "Live · as of Oct 14 close"


# --- AC 1: each agent, from the question to the answer with its sources, labels and disclaimer --------------------


def test_finance_qa_searches_the_knowledge_base_and_cites_what_it_used(stack):
    response = stack.ask("What is compound interest?")
    assert response.agent is AgentName.FINANCE_QA
    # The best match is the glossary definition of the term, which cites the article it relates to.
    assert response.answer.startswith("From How Compound Interest Grows Your Money: Compound interest: Earning returns on both")
    top = response.sources[0]
    assert top.title == "How Compound Interest Grows Your Money" and top.url.startswith("https://www.investor.gov/") and top.category == "Investing Basics"
    assert response.disclaimer is None and response.labels == []
    assert stack.openai.schemas == ["RouteDecision", "GroundedAnswer"]  # one router call, then one agent
    grounded = stack.openai.calls[1]
    assert "Verified content" in grounded.system and "Earning returns on both your original money" in grounded.system  # the passage reached the model
    assert grounded.user == "What is compound interest?"


def test_market_gets_prices_through_the_data_client_with_a_freshness_label(stack):
    response = stack.ask("How is VTI doing?")
    assert response.agent is AgentName.MARKET and response.answer == "VTI closed at $376.88."
    assert [label.text for label in response.labels] == [LIVE_LABEL]
    assert stack.alpha.requests_for("GLOBAL_QUOTE") == ["VTI"] and stack.alpha.requests_for("TIME_SERIES_DAILY") == ["VTI"]
    assert stack.openai.schemas == ["RouteDecision", "LLMAnswer"]  # the symbol was in the question, so no ticker lookup
    facts = stack.openai.calls[1].system
    assert "VTI: price $376.88, change -4.44 (-1.16%)" in facts and "Trend:" in facts  # the real calculations reached the model


def test_the_second_market_question_comes_from_the_cache_and_says_so(stack):
    stack.ask("How is VTI doing?")
    requests_before = len(stack.alpha.calls)
    second = stack.ask("How is VTI doing right now?")
    assert len(stack.alpha.calls) == requests_before  # nothing new was requested from Alpha Vantage
    assert second.labels and second.labels[0].text.startswith("Cached · updated") and second.labels[0].text.endswith("as of Oct 14 close")


def test_portfolio_upload_is_priced_analyzed_and_labeled(stack):
    response = stack.ask("Is my portfolio diversified?", payload={"csv": DIVERSIFIED})
    assert response.agent is AgentName.PORTFOLIO
    # 40 VTI @376.88 + 60 VXUS @72.50 + 50 BND @74.20 + 15 VNQ @92.80 + 5 AAPL @255.00
    assert response.answer == "Your portfolio is worth $25,802.20." and response.data["metrics"].total_value == pytest.approx(25802.20)
    assert sorted(stack.alpha.requests_for("GLOBAL_QUOTE")) == ["AAPL", "BND", "VNQ", "VTI", "VXUS"]
    assert [label.text for label in response.labels] == [LIVE_LABEL] and response.disclaimer is None
    assert stack.openai.schemas == ["RouteDecision", "PortfolioExplanation"]


def test_a_concentrated_portfolio_gets_a_recommendation_and_so_a_disclaimer(stack):
    response = stack.ask("Analyze my portfolio", payload={"csv": CONCENTRATED})
    assert response.data["metrics"].concentrated == ["AAPL", "TSLA"] and response.response_type == "advice"
    assert response.disclaimer == stack.settings.disclaimer.text


def test_goal_planning_asks_for_the_risk_tolerance_then_plans_with_a_disclaimer(stack):
    asked = stack.say("I want $20,000 in 4 years for a house. I have $3,000 saved.")
    assert asked.agent is AgentName.GOAL_PLANNING and asked.answer == RISK_QUESTION and asked.needs_input == "risk_tolerance"
    assert stack.openai.schemas == ["RouteDecision"]  # asked before spending any more AI calls
    plan = stack.say("moderate")
    assert plan.answer.startswith("To reach your goal, save about $309.17 a month.") and plan.data["plan"].required_monthly == 309.17
    assert "Assumed return: 5% a year (Moderate)" in plan.answer and plan.disclaimer == stack.settings.disclaimer.text
    assert stack.openai.schemas == ["RouteDecision", "RouteDecision", "GoalExtraction", "LLMAnswer"]
    assert stack.conversation.profile.risk_tolerance == "moderate"


def test_news_comes_through_the_search_client_with_citations_and_a_label(stack):
    response = stack.ask("What's in the financial news today?")
    assert response.agent is AgentName.NEWS
    assert response.answer.startswith("According to Reuters, Stock Market: stocks slip as investors weigh new inflation data")
    assert stack.serp.queries == ["stock market"] and stack.openai.schemas == ["RouteDecision", "NewsQuery", "NewsSummary"]
    cited = response.sources[0]
    assert (cited.source_name, cited.url) == ("Reuters", "https://news.example/reuters/1") and cited.published.isoformat() == "2026-10-14"
    assert [label.text for label in response.labels] == ["Live · as of Oct 14"]


def test_tax_advice_is_grounded_in_the_tax_category_and_carries_the_disclaimer(stack):
    response = stack.ask("Should I choose a Roth IRA or a traditional IRA?")
    assert response.agent is AgentName.TAX and response.response_type == "advice" and response.disclaimer == stack.settings.disclaimer.text
    assert response.answer.startswith("From Traditional vs. Roth:") and "Traditional vs. Roth" in [s.title for s in response.sources]
    assert {s.category for s in response.sources} == {"Retirement & Tax Accounts"}
    assert stack.openai.schemas == ["RouteDecision", "TaxAnswer"]


def test_an_off_topic_question_stops_at_the_router(stack):
    response = stack.ask("What's the best pizza in Chicago?")
    assert response.agent is None and response.answer == OFF_TOPIC_REPLY
    assert stack.openai.schemas == ["RouteDecision"] and stack.alpha.calls == [] and stack.serp.queries == []


def test_an_unknown_ticker_gets_the_friendly_message(stack):
    response = stack.ask("How is ZZZZ doing?")
    assert response.agent is AgentName.MARKET and response.answer == "We couldn't find that ticker. Check the symbol and try again."
    assert stack.openai.schemas == ["RouteDecision"]


def test_a_bad_upload_is_explained_without_any_pricing_or_explanation_call(stack):
    bad = (SAMPLES / "malformed_bad_values.csv").read_bytes()
    response = stack.ask("Analyze my portfolio", payload={"csv": bad})
    assert "Row 2: shares is not a number ('forty')." in response.answer and len(response.data["problems"]) == 4
    assert stack.alpha.calls == [] and stack.openai.schemas == ["RouteDecision"]


# --- AC 2: the six-agent conversation, with real search, clients, caches and shared state ---------------------------

SCRIPT = [
    ("What is an ETF?", None),
    ("How is VTI doing?", None),
    ("I want $20,000 in 4 years for a house. I have $3,000, and I keep it in a Roth IRA.", None),  # asks for the risk tolerance
    ("moderate", None),
    ("Would I owe taxes if I take it out early?", None),
    ("What's in the financial news today?", None),
    ("Is my portfolio diversified?", {"csv": DIVERSIFIED}),
]


@pytest.fixture
def conversation(stack):
    turns = []
    for text, payload in SCRIPT:
        before = len(stack.openai.calls)
        response = stack.say(text, payload)
        turns.append((response, [call.schema for call in stack.openai.calls[before:]], stack.openai.calls[before:]))
    return stack, turns


def test_all_six_agents_answer_in_one_session_with_one_agent_per_question(conversation):
    stack, turns = conversation
    assert [r.agent for r, _, _ in turns] == [
        AgentName.FINANCE_QA, AgentName.MARKET, AgentName.GOAL_PLANNING, AgentName.GOAL_PLANNING,
        AgentName.TAX, AgentName.NEWS, AgentName.PORTFOLIO,
    ]
    assert {r.agent for r, _, _ in turns} == set(AgentName) and not any(r.error for r, _, _ in turns)
    assert [schemas for _, schemas, _ in turns] == [
        ["RouteDecision", "GroundedAnswer"], ["RouteDecision", "LLMAnswer"], ["RouteDecision"],
        ["RouteDecision", "GoalExtraction", "LLMAnswer"], ["RouteDecision", "TaxAnswer"],
        ["RouteDecision", "NewsQuery", "NewsSummary"], ["RouteDecision", "PortfolioExplanation"],
    ]


def test_each_agent_sees_what_the_others_said_and_the_profile_set_along_the_way(conversation):
    stack, turns = conversation
    tax_call = turns[4][2][1]  # the agent's own call in the tax turn
    earlier = " ".join(text for _, text in tax_call.history)
    assert "How is VTI doing?" in earlier and "Roth IRA" in earlier and "save about $309.17 a month" in earlier
    for turn in (4, 5, 6):  # tax, news, portfolio: the risk tolerance given during goal planning reached them
        assert "risk tolerance is moderate" in turns[turn][2][-1].system
    assert stack.conversation.profile.risk_tolerance == "moderate" and len(stack.conversation.exchanges) == 7


def test_the_tax_follow_up_that_relies_on_an_earlier_turn_is_answered_from_the_tax_category(conversation):
    _, turns = conversation
    tax = turns[4][0]
    assert tax.agent is AgentName.TAX and tax.answer.startswith("From ") and tax.sources
    assert {s.category for s in tax.sources} == {"Retirement & Tax Accounts"}


def test_the_cache_is_shared_across_the_conversation(conversation):
    stack, _ = conversation
    assert stack.alpha.requests_for("GLOBAL_QUOTE").count("VTI") == 1  # asked about in turn 2 and held in turn 7
    assert stack.alpha.requests_for("TIME_SERIES_DAILY") == ["VTI"]
    assert stack.serp.queries == ["stock market"]


def test_every_figure_in_the_conversation_carries_a_label(conversation):
    _, turns = conversation
    market, news, portfolio = turns[1][0], turns[5][0], turns[6][0]
    assert [l.text for l in market.labels] == [LIVE_LABEL] and [l.text for l in news.labels] == ["Live · as of Oct 14"]
    assert portfolio.labels and all(l.text.startswith(("Live", "Cached")) for l in portfolio.labels)


# --- fallbacks, end to end -------------------------------------------------------------------------------------------


def test_when_alpha_vantage_says_the_daily_limit_is_reached_the_answer_uses_labeled_sample_data(stack):
    stack.alpha.limit_after = 0
    response = stack.ask("How is VTI doing?")
    assert response.answer == "VTI closed at $377.00."  # the sample price, from the built-in sample data
    assert [label.text for label in response.labels] == ["Sample data · not real prices"]
    assert "SAMPLE DATA, NOT REAL PRICES" in stack.openai.calls[1].system  # and the model is told, in plain words
    requests = len(stack.alpha.calls)
    stack.ask("How is SPY doing?")
    assert len(stack.alpha.calls) == requests  # Finnie stopped asking once it was told the limit was reached


def test_when_serpapi_is_out_of_searches_news_falls_back_to_labeled_sample_headlines(stack):
    stack.serp.out_of_searches = True
    response = stack.ask("What's in the financial news today?")
    assert response.answer.startswith("According to Finnie sample data, Sample:")
    assert [label.text for label in response.labels] == ["Sample data · not real headlines"]
    queries = len(stack.serp.queries)
    stack.ask("Any news about the Fed?")
    assert len(stack.serp.queries) == queries


def test_when_openai_is_down_the_user_is_told_kindly_after_the_configured_retries(stack):
    stack.openai.fail_next(500, times=20)
    response = stack.ask("What is compound interest?")
    assert response.answer == LLM_UNAVAILABLE and response.error and response.agent is None
    assert stack.openai.schemas == ["RouteDecision"] * (stack.settings.llm.max_retries + 1)  # the router is retried, then we stop


def test_a_rejected_openai_key_is_not_retried_and_the_user_gets_a_friendly_message(stack):
    stack.openai.fail_next(401, times=20)
    response = stack.ask("What is compound interest?")
    assert response.answer == AGENT_FAILED and response.error
    assert stack.openai.schemas == ["RouteDecision", "GroundedAnswer"]  # one try each, no retries


def test_openai_recovers_after_a_temporary_failure(stack):
    stack.openai.fail_next(429, times=2)
    response = stack.ask("What is compound interest?")
    assert response.agent is AgentName.FINANCE_QA and not response.error
    assert stack.openai.schemas[:3] == ["RouteDecision"] * 3  # two refusals, then it worked
