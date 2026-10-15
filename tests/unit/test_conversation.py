"""Story 5.2: conversation state for one session."""

from src.core.models import AgentName, AgentResponse, SessionProfile
from src.workflow.conversation import SESSION_KEY, Conversation, get_conversation, reset_conversation


def reply(agent=AgentName.FINANCE_QA, text="An answer."):
    return AgentResponse(agent=agent, answer=text)


def test_get_creates_once_and_returns_the_same_object():
    session = {}
    first = get_conversation(session)
    assert isinstance(first, Conversation) and get_conversation(session) is first


def test_state_is_kept_between_turns():
    conversation = get_conversation({})
    conversation.add("What is a bond?", reply(text="A loan."))
    conversation.add("And a stock?", reply(AgentName.MARKET, "A share."))
    assert [(t.role, t.content) for t in conversation.history(10)] == [
        ("user", "What is a bond?"), ("assistant", "A loan."), ("user", "And a stock?"), ("assistant", "A share."),
    ]
    assert conversation.last_agent is AgentName.MARKET
    assert conversation.history(10)[-1].agent is AgentName.MARKET


def test_history_is_limited_to_the_most_recent_turns():
    conversation = Conversation()
    for i in range(6):
        conversation.add(f"q{i}", reply(text=f"a{i}"))
    assert [t.content for t in conversation.history(3)] == ["a4", "q5", "a5"]
    assert conversation.history(0) == []


def test_request_carries_history_profile_and_payload():
    conversation = Conversation(profile=SessionProfile(risk_tolerance="moderate"))
    conversation.add("first", reply())
    request = conversation.request("second", turns=10, payload={"ticker": "VTI"})
    assert request.message == "second" and len(request.history) == 2
    assert request.profile.risk_tolerance == "moderate" and request.payload == {"ticker": "VTI"}


def test_new_conversation_clears_history_and_profile():
    session = {}
    conversation = get_conversation(session)
    conversation.profile = SessionProfile(risk_tolerance="aggressive")
    conversation.add("q", reply())
    fresh = reset_conversation(session)
    assert fresh.exchanges == [] and fresh.profile == SessionProfile() and fresh.last_agent is None
    assert get_conversation(session) is fresh


def test_state_lives_only_in_the_session_mapping():
    session = {SESSION_KEY: "something else"}
    conversation = get_conversation(session)
    assert isinstance(conversation, Conversation) and session[SESSION_KEY] is conversation
    assert not hasattr(Conversation, "save") and not hasattr(Conversation, "load")  # D-15: nothing persisted
