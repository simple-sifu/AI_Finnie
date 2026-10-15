"""Story 5.1: router, LangGraph workflow and async runner."""

import asyncio
import logging

import pytest

from src.core.async_runner import AsyncRunner
from src.core.models import AgentName, AgentRequest, AgentResponse
from src.workflow.graph import COMING_SOON, EMPTY_INPUT, OFF_TOPIC_REPLY, UNAVAILABLE, FinnieWorkflow
from src.workflow.router import ROUTER_PROMPT, RouteDecision, Router

DISCLAIMER = "Not personalized advice."


class FakeLLM:
    def __init__(self, decision=None, error=None):
        self.decision, self.error, self.calls = decision, error, []

    async def structured(self, schema, system, user, history=None):
        self.calls.append((schema, system, user))
        if self.error:
            raise self.error
        return self.decision


class FakeAgent:
    def __init__(self, name, kind="education"):
        self.name, self.kind, self.calls = name, kind, []

    async def run(self, request):
        self.calls.append(request.message)
        # Deliberately returns advice WITHOUT a disclaimer, to prove finalize adds it.
        return AgentResponse(agent=self.name, answer=f"{self.name.value} answer", response_type=self.kind)


def workflow(route, confidence=0.9, agents=None, question=None, error=None):
    llm = FakeLLM(RouteDecision(route=route, confidence=confidence, clarifying_question=question), error)
    agents = agents if agents is not None else {name: FakeAgent(name) for name in AgentName}
    return FinnieWorkflow(Router(llm, 0.5), agents, DISCLAIMER, max_input_chars=50), llm, agents


def ask(flow, message="What is a bond?"):
    return asyncio.run(flow.run(AgentRequest(message=message)))


# --- router ---


def test_router_prompt_describes_all_six_agents_with_examples():
    for name in AgentName:
        assert f"- {name.value}:" in ROUTER_PROMPT
    assert "- clarify:" in ROUTER_PROMPT and "- off_topic:" in ROUTER_PROMPT


def test_low_confidence_becomes_a_clarifying_question():
    decision = asyncio.run(Router(FakeLLM(RouteDecision(route="market", confidence=0.3)), 0.5).classify(AgentRequest(message="it?")))
    assert decision.route == "clarify"


def test_router_failure_falls_back_to_finance_qa(caplog):
    with caplog.at_level(logging.INFO, logger="src.workflow.router"):
        decision = asyncio.run(Router(FakeLLM(error=RuntimeError("boom")), 0.5).classify(AgentRequest(message="x")))
    assert decision.route == "finance_qa" and "kind=router_failed" in caplog.text


def test_route_is_logged(caplog):
    with caplog.at_level(logging.INFO, logger="src.workflow.router"):
        asyncio.run(Router(FakeLLM(RouteDecision(route="tax", confidence=0.88)), 0.5).classify(AgentRequest(message="x")))
    assert "route route=tax confidence=0.88" in caplog.text


# --- workflow ---


@pytest.mark.parametrize("name", list(AgentName))
def test_each_route_runs_exactly_one_agent(name):
    flow, _, agents = workflow(name.value)
    response = ask(flow)
    assert response.agent is name and response.answer == f"{name.value} answer"
    assert [n for n, a in agents.items() if a.calls] == [name]


def test_finalize_adds_the_disclaimer_even_if_an_agent_forgot():
    flow, _, _ = workflow("market", agents={AgentName.MARKET: FakeAgent(AgentName.MARKET, kind="advice")})
    assert ask(flow).disclaimer == DISCLAIMER


def test_clarify_uses_the_routers_question():
    flow, _, agents = workflow("clarify", question="Do you mean a stock or a fund?")
    response = ask(flow, "tell me about it")
    assert response.agent is None and response.answer == "Do you mean a stock or a fund?"
    assert not any(a.calls for a in agents.values())


def test_off_topic_gets_a_polite_note():
    flow, _, _ = workflow("off_topic")
    response = ask(flow, "Best pizza in Chicago?")
    assert response.agent is None and response.answer == OFF_TOPIC_REPLY


@pytest.mark.parametrize("name", [AgentName.GOAL_PLANNING, AgentName.NEWS, AgentName.TAX])
def test_agents_not_built_yet_say_coming_soon(name):
    flow, _, _ = workflow(name.value, agents={})
    response = ask(flow)
    assert response.agent is name and response.answer.startswith(COMING_SOON[name])


def test_missing_core_agent_says_unavailable():
    flow, _, _ = workflow("finance_qa", agents={})
    assert ask(flow).answer == UNAVAILABLE


@pytest.mark.parametrize("message, expected", [("   ", EMPTY_INPUT), ("x" * 51, "under 50 characters")])
def test_invalid_input_never_reaches_the_router(message, expected):
    flow, llm, _ = workflow("market")
    assert expected in ask(flow, message).answer and llm.calls == []


def test_each_request_gets_its_own_request_id(tmp_path):
    import re

    from src.utils.logging import setup_logging

    setup_logging("INFO", log_dir=tmp_path, console=False)
    flow, _, _ = workflow("market")
    ask(flow)
    ask(flow)
    ids = re.findall(r"\[([0-9a-f]{8})\] route route=market", (tmp_path / "finnie.log").read_text())
    assert len(ids) == 2 and ids[0] != ids[1]


# --- async runner ---


def test_runner_runs_coroutines_on_one_long_lived_loop():
    runner = AsyncRunner()

    async def which_loop():
        return asyncio.get_running_loop()

    try:
        assert runner.run(which_loop()) is runner.run(which_loop()) is runner.loop
    finally:
        runner.close()


def test_runner_raises_the_coroutines_error():
    runner = AsyncRunner()

    async def fail():
        raise ValueError("bad")

    try:
        with pytest.raises(ValueError, match="bad"):
            runner.run(fail())
    finally:
        runner.close()
