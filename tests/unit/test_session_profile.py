"""Story 5.5: session profile, asking for a missing risk tolerance, and the agents using the profile."""

import asyncio

import pytest

from src.agents.base import RISK_QUESTION, BaseAgent, LLMAnswer
from src.agents.finance_qa import FinanceQAAgent, GroundedAnswer
from src.agents.market import MarketAgent
from src.agents.portfolio import PortfolioAgent, PortfolioExplanation
from src.core.models import AgentName, AgentRequest, AgentResponse, SessionProfile
from src.workflow.conversation import (
    RISK_REASK,
    Conversation,
    get_conversation,
    parse_risk_tolerance,
    plan_turn,
    reset_conversation,
)


# --- defaults (AC 1) ---


def test_defaults_beginner_and_no_risk_tolerance():
    profile = SessionProfile()
    assert profile.knowledge_level == "beginner" and profile.risk_tolerance is None and profile.goal_note is None


# --- reading the answer ---


@pytest.mark.parametrize(
    "text, level",
    [
        ("Conservative", "conservative"), ("i'm pretty cautious", "conservative"), ("low risk please", "conservative"),
        ("moderate", "moderate"), ("somewhere balanced", "moderate"), ("Medium", "moderate"),
        ("Aggressive!", "aggressive"), ("high-risk", "aggressive"), ("I like to be bold", "aggressive"),
    ],
)
def test_parse_risk_tolerance(text, level):
    assert parse_risk_tolerance(text) == level


@pytest.mark.parametrize("text", ["", "ok", "I don't know", "moderate, not aggressive", "what is a bond?", "unconservative"])
def test_unreadable_or_ambiguous_answers_are_not_guessed(text):
    assert parse_risk_tolerance(text) is None


# --- asking, and storing the answer in the session profile (AC 2) ---


class NeedsRiskAgent(BaseAgent):
    name = AgentName.GOAL_PLANNING
    instructions = "Plan savings goals."
    requires_risk_tolerance = True

    def __init__(self, llm):
        super().__init__(llm, "disclaimer")
        self.ran = 0

    async def _run(self, request):
        self.ran += 1
        return AgentResponse(agent=self.name, answer=f"plan for {request.profile.risk_tolerance}")


def test_agent_that_needs_risk_tolerance_asks_and_does_not_run_without_it():
    agent = NeedsRiskAgent(llm=None)
    response = asyncio.run(agent.run(AgentRequest(message="Plan my savings")))
    assert response.answer == RISK_QUESTION and response.needs_input == "risk_tolerance"
    assert not response.error and response.disclaimer is None and agent.ran == 0
    for level in ("Conservative", "Moderate", "Aggressive"):
        assert level in RISK_QUESTION and "sidebar" in RISK_QUESTION


def test_agent_runs_once_risk_tolerance_is_set():
    agent = NeedsRiskAgent(llm=None)
    request = AgentRequest(message="Plan my savings", profile=SessionProfile(risk_tolerance="moderate"))
    assert asyncio.run(agent.run(request)).answer == "plan for moderate" and agent.ran == 1


def asked_conversation():
    """A conversation where an agent has just asked for the risk tolerance."""
    conversation = Conversation()
    ask = AgentResponse(agent=AgentName.GOAL_PLANNING, answer=RISK_QUESTION, needs_input="risk_tolerance")
    conversation.add("Plan my savings for a $20,000 goal", ask)
    return conversation


def test_asking_remembers_the_question_to_answer_later():
    conversation = asked_conversation()
    assert conversation.pending.original_message == "Plan my savings for a $20,000 goal"
    assert conversation.pending.agent is AgentName.GOAL_PLANNING


def test_the_answer_is_stored_in_the_profile_and_the_original_question_is_answered():
    conversation = asked_conversation()
    plan = plan_turn(conversation, "moderate")
    assert conversation.profile.risk_tolerance == "moderate"
    assert plan.message == "Plan my savings for a $20,000 goal" and plan.reply is None
    conversation.add("moderate", AgentResponse(agent=AgentName.GOAL_PLANNING, answer="Your plan"), asked=plan.message)
    assert conversation.pending is None


def test_an_unreadable_short_answer_is_asked_again_with_the_options():
    conversation = asked_conversation()
    plan = plan_turn(conversation, "dunno")
    assert plan.reply.answer == RISK_REASK and plan.reply.needs_input == "risk_tolerance"
    assert conversation.profile.risk_tolerance is None
    conversation.add("dunno", plan.reply, asked=plan.message)
    assert conversation.pending.original_message == "Plan my savings for a $20,000 goal"  # still waiting
    assert plan_turn(conversation, "aggressive").message == "Plan my savings for a $20,000 goal"


def test_risk_set_in_the_sidebar_meanwhile_lets_a_short_reply_continue():
    conversation = asked_conversation()
    conversation.profile.risk_tolerance = "conservative"
    plan = plan_turn(conversation, "ok done")
    assert plan.message == "Plan my savings for a $20,000 goal" and plan.reply is None


def test_a_new_question_instead_of_an_answer_drops_the_pending_one():
    conversation = asked_conversation()
    plan = plan_turn(conversation, "Actually, what is the difference between stocks and bonds?")
    assert plan.message.startswith("Actually") and plan.reply is None and conversation.pending is None
    assert conversation.profile.risk_tolerance is None


def test_without_a_pending_question_messages_pass_through_untouched():
    conversation = Conversation()
    assert plan_turn(conversation, "moderate").message == "moderate"
    assert conversation.profile.risk_tolerance is None  # "moderate" alone is not an answer to anything


# --- the profile lasts only for the session (AC 4, D-15) ---


def test_new_conversation_clears_the_profile_and_any_pending_question():
    session = {}
    conversation = get_conversation(session)
    conversation.profile = SessionProfile(knowledge_level="intermediate", risk_tolerance="aggressive", goal_note="a house")
    conversation.pending = asked_conversation().pending
    fresh = reset_conversation(session)
    assert fresh.profile == SessionProfile() and fresh.pending is None


# --- the profile reaches the agents (AC 3, AC 5) ---


class RecordingLLM:
    def __init__(self, reply):
        self.reply, self.systems = reply, []

    async def structured(self, schema, system, user, history=None):
        self.systems.append(system)
        return self.reply


class Silent:
    async def retrieve(self, query, k=None, categories=None):
        from src.rag.chunking import Chunk
        from src.rag.retriever import RetrievedChunk

        return [RetrievedChunk(Chunk("a#0", "T\n\ntext", "article", "a", "T", "Stocks", "S", "https://x/"), 0.9)]


PROFILE = SessionProfile(knowledge_level="intermediate", risk_tolerance="aggressive", goal_note="retire at 60")


def check_profile_in(system):
    assert "knows the basics" in system  # intermediate depth
    assert "risk tolerance is aggressive" in system and "retire at 60" in system


def test_finance_qa_prompt_uses_the_profile():
    llm = RecordingLLM(GroundedAnswer(answer="a", response_type="education", answered_from_content=True))
    asyncio.run(FinanceQAAgent(llm, "d", Silent()).run(AgentRequest(message="What is a bond?", profile=PROFILE)))
    check_profile_in(llm.systems[0])


def test_market_prompt_uses_the_profile():
    from tests.unit.test_market_agent import FakeMarket

    llm = RecordingLLM(LLMAnswer(answer="a", response_type="education"))
    asyncio.run(MarketAgent(llm, "d", FakeMarket()).run(AgentRequest(message="How is VTI doing?", profile=PROFILE)))
    check_profile_in(llm.systems[-1])


def test_portfolio_prompt_uses_the_profile_and_flags_a_risk_mismatch():
    from tests.unit.test_portfolio_agent import SAMPLES, FixedMarket

    llm = RecordingLLM(PortfolioExplanation(answer="a", response_type="education", includes_recommendation=False))
    request = AgentRequest(
        message="Analyze", profile=SessionProfile(risk_tolerance="conservative"),
        payload={"csv": (SAMPLES / "concentrated.csv").read_bytes()},
    )
    response = asyncio.run(PortfolioAgent(llm, "d", FixedMarket()).run(request))
    assert "risk tolerance is conservative" in llm.systems[0]
    assert any("risk level is High" in note for note in response.data["notes"])


def test_beginner_and_intermediate_get_different_depth():
    llm = RecordingLLM(LLMAnswer(answer="a", response_type="education"))
    from tests.unit.test_market_agent import FakeMarket

    agent = MarketAgent(llm, "d", FakeMarket())
    asyncio.run(agent.run(AgentRequest(message="How is VTI doing?", profile=SessionProfile(knowledge_level="beginner"))))
    asyncio.run(agent.run(AgentRequest(message="How is VTI doing?", profile=SessionProfile(knowledge_level="intermediate"))))
    assert "Assume no prior financial knowledge" in llm.systems[0] and "knows the basics" in llm.systems[1]
