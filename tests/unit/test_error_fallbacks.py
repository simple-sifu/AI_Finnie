"""Story 5.3: the chat keeps working when something goes wrong."""

import asyncio

import pytest

from src.agents.base import AGENT_FAILED, LLM_UNAVAILABLE, BaseAgent
from src.core.llm import LLMUnavailableError
from src.core.models import AgentName, AgentRequest, AgentResponse
from src.workflow.conversation import Conversation
from src.workflow.graph import EMPTY_INPUT, TOO_SLOW, FinnieWorkflow
from src.workflow.router import RouteDecision, Router

DISCLAIMER = "Not personalized advice."


class FakeLLM:
    def __init__(self, decision=None, error=None):
        self.decision, self.error = decision, error

    async def structured(self, schema, system, user, history=None):
        if self.error:
            raise self.error
        return self.decision


class WorkingAgent:
    def __init__(self, name):
        self.name, self.messages = name, []

    async def run(self, request):
        self.messages.append(request.message)
        return AgentResponse(agent=self.name, answer=f"{self.name.value} answer")


class ExplodingAgent:
    """An agent whose run() itself raises, bypassing BaseAgent's own safety net."""

    def __init__(self, name):
        self.name = name

    async def run(self, request):
        raise KeyError("bug in the agent")


class SlowAgent:
    name = AgentName.MARKET

    async def run(self, request):
        await asyncio.sleep(5)


def flow(route="finance_qa", llm_error=None, agents=None, timeout_s=90, max_chars=50):
    llm = FakeLLM(RouteDecision(route=route, confidence=0.9), llm_error)
    agents = agents if agents is not None else {AgentName.FINANCE_QA: WorkingAgent(AgentName.FINANCE_QA)}
    return FinnieWorkflow(Router(llm, 0.5), agents, DISCLAIMER, max_chars, timeout_s)


def ask(workflow, message="What is a bond?"):
    return asyncio.run(workflow.run(AgentRequest(message=message)))


# --- AC 1: router failure ---


def test_router_failure_sends_the_question_to_finance_qa():
    agent = WorkingAgent(AgentName.FINANCE_QA)
    response = ask(flow(llm_error=RuntimeError("router broke"), agents={AgentName.FINANCE_QA: agent}))
    assert response.answer == "finance_qa answer" and agent.messages == ["What is a bond?"]


def test_malformed_router_output_also_falls_back_to_finance_qa():
    workflow = flow(llm_error=ValueError("could not parse structured output"))
    assert ask(workflow).answer == "finance_qa answer"


# --- AC 2: agent failure ---


def test_agent_that_raises_gives_a_friendly_message_and_the_chat_goes_on():
    agents = {AgentName.MARKET: ExplodingAgent(AgentName.MARKET), AgentName.FINANCE_QA: WorkingAgent(AgentName.FINANCE_QA)}
    workflow = flow("market", agents=agents)
    response = ask(workflow)
    assert response.answer == AGENT_FAILED and response.error and response.agent is AgentName.MARKET
    # The next question works normally.
    follow_up = flow("finance_qa", agents=agents)
    assert ask(follow_up).answer == "finance_qa answer"


def test_base_agent_failures_are_friendly_too():
    class Broken(BaseAgent):
        name = AgentName.TAX
        instructions = "x"

        async def _run(self, request):
            raise RuntimeError("bug")

    response = asyncio.run(Broken(FakeLLM(), DISCLAIMER).run(AgentRequest(message="hi")))
    assert response.answer == AGENT_FAILED and response.error


# --- AC 3: OpenAI unavailable ---


def test_openai_down_tells_the_user_straight_away_without_calling_an_agent():
    agent = WorkingAgent(AgentName.FINANCE_QA)
    workflow = flow(llm_error=LLMUnavailableError("APIConnectionError"), agents={AgentName.FINANCE_QA: agent})
    response = ask(workflow)
    assert response.answer == LLM_UNAVAILABLE and response.error and response.agent is None
    assert agent.messages == []


def test_a_workflow_bug_never_escapes():
    workflow = flow()

    async def boom(state):
        raise RuntimeError("unexpected")

    workflow._route = boom  # noqa: SLF001
    workflow.graph = workflow._build()  # noqa: SLF001
    response = ask(workflow)
    assert response.answer == AGENT_FAILED and response.error


def test_a_hung_request_times_out_with_a_friendly_message():
    workflow = flow("market", agents={AgentName.MARKET: SlowAgent()}, timeout_s=0.05)
    response = ask(workflow)
    assert response.answer == TOO_SLOW and response.error


# --- AC 4: odd input ---


@pytest.mark.parametrize("message", ["", "   ", "\n\t", "???", "...", "!@#$%", "😀😀", "\x00\x07"])
def test_empty_and_symbol_only_input_gets_a_prompt_not_an_error(message):
    agent = WorkingAgent(AgentName.FINANCE_QA)
    response = ask(flow(agents={AgentName.FINANCE_QA: agent}), message)
    assert response.answer == EMPTY_INPUT and not response.error and agent.messages == []


def test_very_long_input_is_declined_politely():
    assert "under 50 characters" in ask(flow(), "a" * 51).answer


def test_control_characters_are_removed_before_the_question_is_used():
    agent = WorkingAgent(AgentName.FINANCE_QA)
    ask(flow(agents={AgentName.FINANCE_QA: agent}), "What\x00 is\x07 a bond?")
    assert agent.messages == ["What is a bond?"]


@pytest.mark.parametrize("message", ["asdfghjkl qwerty", "ñandú 你好 مرحبا", "'; DROP TABLE users; --", "<script>alert(1)</script>"])
def test_nonsense_and_unusual_text_is_handled_without_errors(message):
    response = ask(flow(), message)
    assert response.answer and not response.error


def test_malformed_question_is_just_a_question():
    assert not ask(flow(), "what is a bond??!!  ").error


# --- the failed exchange stays out of what the models see next ---


def test_errors_are_shown_but_not_fed_back_to_the_models():
    conversation = Conversation()
    conversation.add("first", AgentResponse(agent=AgentName.FINANCE_QA, answer="good answer"))
    conversation.add("second", AgentResponse(agent=None, answer=AGENT_FAILED, error=True))
    assert len(conversation.exchanges) == 2  # both are displayed
    assert [t.content for t in conversation.history(10)] == ["first", "good answer"]


def test_a_missing_knowledge_base_index_disables_only_the_agents_that_need_it(tmp_path, monkeypatch):
    from src.core.config import load_settings
    from src.rag.index import IndexLoadError
    from src.workflow import factory

    def no_index(settings):
        raise IndexLoadError("The knowledge base index is missing (faiss.index). Run `python -m src.rag.build_index` to build it.")

    monkeypatch.setattr(factory, "create_retriever", no_index)
    keys = {"OPENAI_API_KEY": "sk-x-123456", "ALPHA_VANTAGE_API_KEY": "a", "SERPAPI_API_KEY": "s"}
    services = factory.build_services(load_settings(config_path=tmp_path / "none.yaml", environ=keys), cache_dir=tmp_path)
    assert services.retriever is None
    assert AgentName.FINANCE_QA not in services.agents and AgentName.TAX not in services.agents
    assert {AgentName.PORTFOLIO, AgentName.MARKET, AgentName.GOAL_PLANNING, AgentName.NEWS} <= set(services.agents)
