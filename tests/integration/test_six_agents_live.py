"""Story 4.4 AC 2 and AC 3: one conversation that reaches all six agents, with the real model.

Uses sample market and news data (no Alpha Vantage or SerpApi requests) but calls
OpenAI (about 25 short requests). Runs only when asked:
    RUN_LIVE_TESTS=1 pytest -m live tests/integration/test_six_agents_live.py -s
"""

import asyncio
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from src.core.config import load_settings
from src.core.models import AgentName
from src.workflow.conversation import Conversation, plan_turn
from src.workflow.factory import build_services

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.getenv("RUN_LIVE_TESTS"), reason="set RUN_LIVE_TESTS=1 to call OpenAI"),
]
ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "src" / "data" / "samples"

SCRIPT = [
    ("What is an ETF?", None),
    ("How is VTI doing today?", None),
    ("I want to save $20,000 for a house in 4 years. I have $3,000 saved, and I keep it in a Roth IRA.", None),
    ("moderate", None),  # the risk tolerance the goal planner asked for
    ("Would I owe taxes if I take it out early?", None),  # "it" is the Roth IRA from the goal turn
    ("What's in the financial news today?", None),
    ("Is my portfolio diversified?", {"csv": (SAMPLES / "diversified.csv").read_bytes()}),
]


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    load_dotenv(ROOT / ".env")  # passing environ= below skips load_settings' own .env loading
    settings = load_settings(environ={**os.environ, "MARKET_DATA_MODE": "mock"})
    services = build_services(settings, cache_dir=tmp_path_factory.mktemp("cache"))
    conversation = Conversation()

    async def converse():
        responses = []
        for text, payload in SCRIPT:
            plan = plan_turn(conversation, text)
            response = plan.reply or await services.workflow.run(
                conversation.request(plan.message, settings.chat.history_turns, payload)
            )
            conversation.add(text, response, asked=plan.message)
            responses.append((text, response))
        return responses

    responses = asyncio.run(converse())
    for text, response in responses:
        print(f"\n{text!r} -> {response.agent.value if response.agent else 'finnie'}: {response.answer[:120]!r}")
    return conversation, responses


def test_all_six_agents_answer_in_one_session(session):
    _, responses = session
    assert not any(r.error for _, r in responses)
    assert {r.agent for _, r in responses} == set(AgentName)


def test_the_goal_planner_asked_for_the_risk_tolerance_and_the_chat_answer_was_stored(session):
    conversation, responses = session
    assert responses[2][1].needs_input == "risk_tolerance" and conversation.profile.risk_tolerance == "moderate"
    assert responses[3][1].agent is AgentName.GOAL_PLANNING and "plan" in responses[3][1].data


def test_a_tax_follow_up_that_relies_on_the_goal_planning_turn_is_answered_correctly(session):
    """AC 3: "it" means the Roth IRA mentioned while planning, so the answer should be about Roth withdrawals."""
    _, responses = session
    tax = responses[4][1]
    assert tax.agent is AgentName.TAX
    assert {s.category for s in tax.sources} == {"Retirement & Tax Accounts"} and tax.sources
    assert "roth" in tax.answer.lower()
    assert "Early Withdrawals from Retirement Accounts" in [s.title for s in tax.sources] or "Roth IRAs" in [s.title for s in tax.sources]


def test_the_later_agents_work_with_sample_data_and_say_so(session):
    _, responses = session
    for index in (1, 5, 6):  # market, news, portfolio
        labels = [label.text for label in responses[index][1].labels]
        assert labels and all(text.startswith("Sample data") for text in labels)
