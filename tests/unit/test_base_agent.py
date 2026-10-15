"""Story 3.1: the base agent, disclaimer policy and shared LLM client."""

import asyncio
import logging

import httpx
import openai
import pytest

from src.agents.base import AGENT_FAILED, BEGINNER_STYLE, LLM_UNAVAILABLE, BaseAgent, LLMAnswer
from src.core.config import load_settings
from src.core.disclaimer import apply_disclaimer
from src.core.llm import LLMClient, LLMUnavailableError
from src.core.models import AgentName, AgentRequest, AgentResponse, ChatTurn, SessionProfile

DISCLAIMER = "This is general information for learning purposes, not personalized advice."
KEYS = {"OPENAI_API_KEY": "sk-test-123456", "ALPHA_VANTAGE_API_KEY": "a", "SERPAPI_API_KEY": "s"}


class FakeLLM:
    """Stands in for LLMClient: records prompts and returns a scripted answer or error."""

    def __init__(self, result):
        self.result, self.calls = result, []

    async def structured(self, schema, system, user, history=None):
        self.calls.append({"schema": schema, "system": system, "user": user, "history": history})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class EchoAgent(BaseAgent):
    name = AgentName.FINANCE_QA
    instructions = "You answer general finance questions."

    async def _run(self, request):
        reply = await self.ask(request)
        return AgentResponse(agent=self.name, answer=reply.answer, response_type=reply.response_type)


class BrokenAgent(BaseAgent):
    name = AgentName.MARKET
    instructions = "Broken on purpose."

    async def _run(self, request):
        raise KeyError("bug")


def run(agent, message="What is an ETF?", **kwargs):
    return asyncio.run(agent.run(AgentRequest(message=message, **kwargs)))


# --- disclaimer policy (FR28, D-7, D-43) ---


@pytest.mark.parametrize("kind, shown", [("advice", True), ("uncertain", True), ("education", False)])
def test_disclaimer_only_on_advice_and_uncertain(kind, shown):
    response = apply_disclaimer(AgentResponse(agent=AgentName.TAX, answer="x", response_type=kind), DISCLAIMER)
    assert (response.disclaimer == DISCLAIMER) is shown and (response.disclaimer is None) is not shown


def test_disclaimer_is_idempotent_and_skips_errors():
    advice = AgentResponse(agent=AgentName.TAX, answer="x", response_type="advice")
    assert apply_disclaimer(apply_disclaimer(advice, DISCLAIMER), DISCLAIMER).disclaimer == DISCLAIMER
    failure = AgentResponse(agent=AgentName.TAX, answer="x", response_type="advice", error=True)
    assert apply_disclaimer(failure, DISCLAIMER).disclaimer is None


# --- base agent ---


@pytest.mark.parametrize("kind", ["advice", "uncertain", "education"])
def test_agent_flags_response_type_and_adds_disclaimer_automatically(kind):
    agent = EchoAgent(FakeLLM(LLMAnswer(answer="An ETF is a fund.", response_type=kind)), DISCLAIMER)
    response = run(agent)
    assert response.answer == "An ETF is a fund." and response.response_type == kind
    assert (response.disclaimer is not None) == (kind != "education")
    assert response.agent is AgentName.FINANCE_QA and not response.error


def test_system_prompt_targets_beginners_and_includes_the_profile():
    llm = FakeLLM(LLMAnswer(answer="ok", response_type="education"))
    profile = SessionProfile(knowledge_level="beginner", risk_tolerance="moderate", goal_note="house in 5 years")
    history = [ChatTurn(role="user", content="hi"), ChatTurn(role="assistant", content="hello")]
    run(EchoAgent(llm, DISCLAIMER), message="Explain bonds", profile=profile, history=history)
    call = llm.calls[0]
    assert BEGINNER_STYLE in call["system"] and "plain, everyday language" in call["system"]
    assert "You answer general finance questions." in call["system"]
    assert "Assume no prior financial knowledge" in call["system"]
    assert "risk tolerance is moderate" in call["system"] and "house in 5 years" in call["system"]
    assert call["user"] == "Explain bonds" and call["history"] == history and call["schema"] is LLMAnswer


def test_intermediate_users_get_different_guidance():
    llm = FakeLLM(LLMAnswer(answer="ok", response_type="education"))
    run(EchoAgent(llm, DISCLAIMER), profile=SessionProfile(knowledge_level="intermediate"))
    assert "knows the basics" in llm.calls[0]["system"] and "risk tolerance" not in llm.calls[0]["system"]


def test_llm_unavailable_gives_a_friendly_message():
    response = run(EchoAgent(FakeLLM(LLMUnavailableError("APIConnectionError")), DISCLAIMER))
    assert response.answer == LLM_UNAVAILABLE and response.error and response.disclaimer is None


def test_agent_bug_gives_a_friendly_message_and_is_logged(caplog):
    with caplog.at_level(logging.INFO, logger="src.agents.base"):
        response = run(BrokenAgent(FakeLLM(None), DISCLAIMER))
    assert response.answer == AGENT_FAILED and response.error and response.agent is AgentName.MARKET
    assert "agent agent=market" in caplog.text and "kind=agent_failed" in caplog.text


def test_agent_names_have_display_names():
    assert AgentName.GOAL_PLANNING.display_name == "Goal Planning"
    assert {a.display_name for a in AgentName} >= {"Finance Q&A", "Tax Education"}


# --- shared LLM client ---


class FakeRunnable:
    def __init__(self, outcomes, tracker):
        self.outcomes, self.tracker = outcomes, tracker

    async def ainvoke(self, messages):
        self.tracker["calls"] += 1
        self.tracker["in_flight"] += 1
        self.tracker["max_in_flight"] = max(self.tracker["max_in_flight"], self.tracker["in_flight"])
        await asyncio.sleep(0.01)
        self.tracker["in_flight"] -= 1
        self.tracker["messages"] = messages
        outcome = self.outcomes.pop(0) if self.outcomes else LLMAnswer(answer="ok", response_type="education")
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeChatModel:
    def __init__(self, outcomes=None):
        self.tracker = {"calls": 0, "in_flight": 0, "max_in_flight": 0}
        self.outcomes = outcomes or []

    def with_structured_output(self, schema):
        return FakeRunnable(self.outcomes, self.tracker)


def connection_error():
    return openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"))


def test_client_retries_temporary_failures_then_succeeds():
    model = FakeChatModel([connection_error(), connection_error()])
    client = LLMClient(model, max_retries=3, retry_base_seconds=0)
    result = asyncio.run(client.structured(LLMAnswer, "sys", "hi"))
    assert result.answer == "ok" and model.tracker["calls"] == 3


def test_client_gives_up_after_the_configured_retries():
    model = FakeChatModel([connection_error()] * 10)
    client = LLMClient(model, max_retries=2, retry_base_seconds=0)
    with pytest.raises(LLMUnavailableError):
        asyncio.run(client.structured(LLMAnswer, "sys", "hi"))
    assert model.tracker["calls"] == 3


def test_client_does_not_retry_other_errors():
    model = FakeChatModel([ValueError("bad schema")])
    with pytest.raises(ValueError):
        asyncio.run(LLMClient(model, retry_base_seconds=0).structured(LLMAnswer, "sys", "hi"))
    assert model.tracker["calls"] == 1


def test_client_limits_concurrent_calls():
    model = FakeChatModel()
    client = LLMClient(model, max_concurrent=2, retry_base_seconds=0)

    async def many():
        await asyncio.gather(*(client.structured(LLMAnswer, "sys", f"q{i}") for i in range(6)))

    asyncio.run(many())
    assert model.tracker["calls"] == 6 and model.tracker["max_in_flight"] == 2


def test_client_sends_system_history_and_user_in_order():
    model = FakeChatModel()
    history = [ChatTurn(role="user", content="first"), ChatTurn(role="assistant", content="reply")]
    asyncio.run(LLMClient(model).structured(LLMAnswer, "system text", "second", history))
    kinds = [(m.type, m.content) for m in model.tracker["messages"]]
    assert kinds == [("system", "system text"), ("human", "first"), ("ai", "reply"), ("human", "second")]


def test_client_from_settings_uses_openai_model(tmp_path):
    settings = load_settings(config_path=tmp_path / "none.yaml", environ={**KEYS, "OPENAI_MODEL": "gpt-4o-mini"})
    client = LLMClient.from_settings(settings)
    assert client.chat_model.model_name == "gpt-4o-mini" and client.chat_model.temperature == 0.2
    assert client.max_retries == 3 and client.chat_model.max_retries == 0


def test_ask_adds_extra_context_after_the_system_prompt():
    llm = FakeLLM(LLMAnswer(answer="ok", response_type="education"))
    asyncio.run(EchoAgent(llm, DISCLAIMER).ask(AgentRequest(message="hi"), extra_context="EXTRA FACTS"))
    system = llm.calls[0]["system"]
    assert system.endswith("EXTRA FACTS") and BEGINNER_STYLE in system
