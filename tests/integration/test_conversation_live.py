"""Story 5.4 AC 3: a multi-turn conversation across agents, with the real model.

Uses sample market data (no Alpha Vantage requests) but calls OpenAI (about 15
short requests). Runs only when asked:
    RUN_LIVE_TESTS=1 pytest -m live tests/integration/test_conversation_live.py -s
"""

import asyncio
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from src.core.config import load_settings
from src.core.models import AgentName
from src.workflow.conversation import Conversation
from src.workflow.factory import build_services

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.getenv("RUN_LIVE_TESTS"), reason="set RUN_LIVE_TESTS=1 to call OpenAI"),
]
ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "src" / "data" / "samples"


@pytest.fixture(scope="module")
def conversation_run(tmp_path_factory):
    load_dotenv(ROOT / ".env")  # passing environ= below skips load_settings' own .env loading
    settings = load_settings(environ={**os.environ, "MARKET_DATA_MODE": "mock"})
    services = build_services(settings, cache_dir=tmp_path_factory.mktemp("cache"))
    conversation = Conversation()
    script = [
        ("What is an ETF?", None),
        ("How is VTI doing today?", None),
        ("And over the last 3 months?", None),  # "it" is VTI, only from the conversation
        ("What is an index fund?", None),
        ("Is my portfolio diversified?", {"csv": (SAMPLES / "diversified.csv").read_bytes()}),
    ]

    async def converse():
        results = []
        for question, payload in script:
            request = conversation.request(question, settings.chat.history_turns, payload)
            response = await services.workflow.run(request)
            conversation.add(question, response)
            results.append((question, response))
        return results

    results = asyncio.run(converse())
    for question, response in results:
        print(f"\n{question!r} -> {response.agent.value if response.agent else 'finnie'}: {response.answer[:110]!r}")
    return results


def test_conversation_moves_across_at_least_three_agents(conversation_run):
    agents = [response.agent for _, response in conversation_run]
    assert not any(response.error for _, response in conversation_run)
    assert {AgentName.FINANCE_QA, AgentName.MARKET, AgentName.PORTFOLIO} <= set(agents)


def test_a_follow_up_with_no_ticker_is_resolved_from_the_conversation(conversation_run):
    _, response = conversation_run[2]  # "And over the last 3 months?"
    assert response.agent is AgentName.MARKET
    assert [row["symbol"] for row in response.data["tickers"]] == ["VTI"]


def test_the_portfolio_turn_works_in_the_same_conversation(conversation_run):
    _, response = conversation_run[4]
    assert response.agent is AgentName.PORTFOLIO and response.data["metrics"].total_value > 0
