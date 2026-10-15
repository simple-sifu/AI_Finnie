"""Story 5.4: the router and agents receive the recent conversation, across agents."""

import asyncio

from src.agents.base import LLMAnswer
from src.agents.market import MarketAgent
from src.core.models import AgentName, AgentRequest, AgentResponse, ChatTurn
from src.workflow.conversation import Conversation
from src.workflow.graph import FinnieWorkflow
from src.workflow.router import ROUTER_PROMPT, RouteDecision, Router, router_prompt

DISCLAIMER = "Not personalized advice."


# --- the router sees the history and which agent answered last ---


class RecordingLLM:
    def __init__(self, decisions):
        self.decisions, self.calls = list(decisions), []

    async def structured(self, schema, system, user, history=None):
        self.calls.append({"system": system, "user": user, "history": history})
        return self.decisions.pop(0)


def test_router_prompt_names_the_previous_agent_from_the_history():
    history = [
        ChatTurn(role="user", content="How is VTI doing?"),
        ChatTurn(role="assistant", content="VTI fell.", agent=AgentName.MARKET),
    ]
    prompt = router_prompt(history)
    assert prompt.startswith(ROUTER_PROMPT)
    assert "came from the Market Analysis agent (market)" in prompt and "follow-up usually belongs" in prompt


def test_router_prompt_is_unchanged_without_a_previous_agent():
    assert router_prompt([]) == ROUTER_PROMPT
    answered_by_finnie = [ChatTurn(role="assistant", content="Could you say more?", agent=None)]
    assert router_prompt(answered_by_finnie) == ROUTER_PROMPT


def test_router_receives_the_history_with_the_question():
    llm = RecordingLLM([RouteDecision(route="market", confidence=0.9)])
    history = [ChatTurn(role="user", content="How is VTI doing?"), ChatTurn(role="assistant", content="Down.", agent=AgentName.MARKET)]
    asyncio.run(Router(llm).classify(AgentRequest(message="And over 3 months?", history=history)))
    assert llm.calls[0]["history"] == history and llm.calls[0]["user"] == "And over 3 months?"


# --- an agent that resolves "it" uses the earlier messages ---


class TickerLLM:
    def __init__(self):
        self.calls = []

    async def structured(self, schema, system, user, history=None):
        self.calls.append({"schema": schema, "history": history})
        if schema.__name__ == "TickerRequest":
            from src.agents.market import TickerRequest

            return TickerRequest(tickers=["VTI"], overall_market=False)
        return LLMAnswer(answer="ok", response_type="education")


def test_market_agent_gives_the_history_to_the_ticker_lookup():
    from tests.unit.test_market_agent import FakeMarket

    llm, history = TickerLLM(), [ChatTurn(role="user", content="How is VTI doing?")]
    agent = MarketAgent(llm, DISCLAIMER, FakeMarket())
    asyncio.run(agent.run(AgentRequest(message="how about over 3 months?", history=history)))
    assert llm.calls[0]["schema"].__name__ == "TickerRequest" and llm.calls[0]["history"] == history


# --- a whole conversation moving across agents ---


class RecordingAgent:
    def __init__(self, name):
        self.name, self.requests = name, []

    async def run(self, request):
        self.requests.append(request)
        return AgentResponse(agent=self.name, answer=f"{self.name.value} reply {len(self.requests)}")


def test_conversation_moves_across_three_agents_and_each_sees_the_earlier_turns():
    script = [
        ("What is an ETF?", "finance_qa"),
        ("How is VTI doing?", "market"),
        ("And over 3 months?", "market"),
        ("What is an index fund?", "finance_qa"),
        ("Is my portfolio diversified?", "portfolio"),
    ]
    agents = {name: RecordingAgent(name) for name in (AgentName.FINANCE_QA, AgentName.MARKET, AgentName.PORTFOLIO)}
    llm = RecordingLLM([RouteDecision(route=route, confidence=0.9) for _, route in script])
    workflow = FinnieWorkflow(Router(llm), agents, DISCLAIMER)
    conversation, history_turns = Conversation(), 10

    answered_by = []
    for question, _ in script:
        request = conversation.request(question, history_turns)
        response = asyncio.run(workflow.run(request))
        conversation.add(question, response)
        answered_by.append(response.agent)

    assert answered_by == [AgentName.FINANCE_QA, AgentName.MARKET, AgentName.MARKET, AgentName.FINANCE_QA, AgentName.PORTFOLIO]
    assert len(set(answered_by)) >= 3  # AC 3

    # The portfolio agent, last to answer, saw the earlier questions and answers from the OTHER agents.
    seen = [turn.content for turn in agents[AgentName.PORTFOLIO].requests[0].history]
    assert "What is an ETF?" in seen and "market reply 2" in seen and "finance_qa reply 2" in seen
    # Market's second turn saw its own first answer and the Finance Q&A answer before it.
    second_market = agents[AgentName.MARKET].requests[1].history
    assert [t.content for t in second_market] == ["What is an ETF?", "finance_qa reply 1", "How is VTI doing?", "market reply 1"]
    # The router was told which agent answered last at each step.
    assert "previous answer" not in llm.calls[0]["system"]  # nothing to remember on the first question
    assert "(finance_qa)" in llm.calls[1]["system"] and "(market)" in llm.calls[2]["system"]
    assert "(market)" in llm.calls[3]["system"] and "(finance_qa)" in llm.calls[4]["system"]


def test_history_sent_is_limited_to_the_configured_number_of_messages():
    agent = RecordingAgent(AgentName.FINANCE_QA)
    llm = RecordingLLM([RouteDecision(route="finance_qa", confidence=0.9)] * 8)
    workflow = FinnieWorkflow(Router(llm), {AgentName.FINANCE_QA: agent}, DISCLAIMER)
    conversation = Conversation()
    for i in range(8):
        response = asyncio.run(workflow.run(conversation.request(f"question {i}", turns=4)))
        conversation.add(f"question {i}", response)
    last = agent.requests[-1].history
    assert len(last) == 4 and [t.content for t in last][0] == "question 5"  # only the last 2 exchanges
    assert len(llm.calls[-1]["history"]) == 4  # and the router got the same limit
