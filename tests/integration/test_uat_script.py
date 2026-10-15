"""Executable checks for docs/uat-script.md (Story 9.3)."""

from pathlib import Path

import pytest

from src.agents.base import RISK_QUESTION
from src.core.models import AgentName
from tests.integration.test_full_path import CONCENTRATED, DIVERSIFIED, LIVE_LABEL, SCRIPT

SAMPLES = Path(__file__).resolve().parents[2] / "src" / "data" / "samples"


def test_uat_chat_01_finance_qa_education_with_sources(stack):
    response = stack.ask("What is compound interest?")
    assert response.agent is AgentName.FINANCE_QA
    assert response.answer.startswith("From How Compound Interest Grows Your Money:")
    assert response.sources[0].title == "How Compound Interest Grows Your Money"
    assert response.disclaimer is None


def test_uat_chat_02_market_with_freshness_label(stack):
    response = stack.ask("How is VTI doing?")
    assert response.agent is AgentName.MARKET and [label.text for label in response.labels] == [LIVE_LABEL]


def test_uat_chat_03_and_04_goal_planning_and_disclaimer(stack):
    asked = stack.say("I want $20,000 in 4 years for a house. I have $3,000 saved.")
    assert asked.agent is AgentName.GOAL_PLANNING and asked.answer == RISK_QUESTION
    plan = stack.say("moderate")
    assert plan.answer.startswith("To reach your goal, save about $309.17 a month.")
    assert plan.disclaimer == stack.settings.disclaimer.text


def test_uat_chat_05_tax_with_disclaimer(stack):
    response = stack.ask("Should I choose a Roth IRA or a traditional IRA?")
    assert response.agent is AgentName.TAX and response.disclaimer == stack.settings.disclaimer.text


def test_uat_chat_06_news_with_label(stack):
    response = stack.ask("What's in the financial news today?")
    assert response.agent is AgentName.NEWS
    assert [label.text for label in response.labels] == ["Live · as of Oct 14"]


def test_uat_chat_07_portfolio_upload(stack):
    response = stack.ask("Is my portfolio diversified?", payload={"csv": DIVERSIFIED})
    assert response.agent is AgentName.PORTFOLIO
    assert response.answer == "Your portfolio is worth $25,802.20."


def test_uat_chat_08_six_agent_session(stack):
    turns = [stack.say(text, payload) for text, payload in SCRIPT]
    assert [r.agent for r in turns] == [
        AgentName.FINANCE_QA, AgentName.MARKET, AgentName.GOAL_PLANNING, AgentName.GOAL_PLANNING,
        AgentName.TAX, AgentName.NEWS, AgentName.PORTFOLIO,
    ]
    assert not any(r.error for r in turns)


def test_uat_port_01_concentrated_portfolio_advice_disclaimer(stack):
    response = stack.ask("Analyze my portfolio", payload={"csv": CONCENTRATED})
    assert response.response_type == "advice" and response.disclaimer == stack.settings.disclaimer.text


def test_uat_port_03_malformed_upload(stack):
    bad = (SAMPLES / "malformed_bad_values.csv").read_bytes()
    response = stack.ask("Analyze my portfolio", payload={"csv": bad})
    assert "Row 2: shares is not a number ('forty')." in response.answer
    assert stack.alpha.calls == []


def test_uat_mkt_03_chat_spy_quote(stack):
    response = stack.ask("How is SPY doing?")
    assert response.agent is AgentName.MARKET and "769.60" in response.answer
    assert response.labels[0].text.startswith(("Live", "Cached", "Sample data"))


def test_uat_disc_02_education_has_no_disclaimer(stack):
    response = stack.ask("What is compound interest?")
    assert response.disclaimer is None and response.agent is AgentName.FINANCE_QA


def test_uat_fresh_01_live_label_on_first_quote(stack):
    response = stack.ask("How is VTI doing?")
    assert [label.text for label in response.labels] == [LIVE_LABEL]


def test_uat_fresh_02_cached_label_on_repeat(stack):
    stack.ask("How is VTI doing?")
    second = stack.ask("How is VTI doing right now?")
    assert second.labels[0].text.startswith("Cached · updated")


def test_uat_fresh_03_sample_data_label_when_fallback_used(stack):
    stack.alpha.limit_after = 0
    response = stack.ask("How is VTI doing?")
    assert any(label.text.startswith("Sample data") for label in response.labels)


@pytest.mark.parametrize("text,payload", SCRIPT)
def test_uat_script_turns_match_demo_flow(stack, text, payload):
    response = stack.say(text, payload)
    assert not response.error
