"""Conversation state for one browser session (Story 5.2, D-15, architecture §6.3).

One object holds everything the router and agents share across turns: the
message history, the agent that handled the last turn and the session
profile. It lives only in Streamlit session state, in memory; nothing is
written to disk, so it ends when the session ends.
"""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from src.core.models import AgentName, AgentRequest, AgentResponse, ChatTurn, SessionProfile

SESSION_KEY = "conversation"


class Exchange(BaseModel):
    """One question and its answer, kept together for display."""

    model_config = {"arbitrary_types_allowed": True}

    question: ChatTurn
    answer: ChatTurn
    response: AgentResponse


RISK_PENDING = "risk_tolerance"
RISK_REASK = (
    "I didn't catch that. Which describes you best: Conservative (you prefer stability), "
    "Moderate (a balance) or Aggressive (you accept big ups and downs for more growth)?"
)
SHORT_ANSWER_WORDS = 4  # a reply this short to a question we asked is treated as the answer

_RISK_WORDS = {
    "conservative": r"conservative(?:ly)?|cautious(?:ly)?|careful(?:ly)?|safe(?:ly)?|low[- ]risk|risk[- ]averse",
    "moderate": r"moderate(?:ly)?|balanced|medium|middle|in the middle",
    "aggressive": r"aggressive(?:ly)?|risky|high[- ]risk|bold(?:ly)?",
}


def parse_risk_tolerance(text: str) -> str | None:
    """Read Conservative, Moderate or Aggressive from a short chat answer.

    Returns None if none matches, or if the answer matches more than one
    ("moderate, not aggressive"), so the question is asked again.
    """
    found = [level for level, words in _RISK_WORDS.items() if re.search(rf"\b(?:{words})\b", text.lower())]
    return found[0] if len(found) == 1 else None


class PendingInput(BaseModel):
    """A question an agent asked the user, waiting for the answer (Story 5.5)."""

    kind: str  # RISK_PENDING
    original_message: str  # the question to answer once we have the missing information
    agent: AgentName | None = None


@dataclass(frozen=True)
class TurnPlan:
    """What to send to the workflow this turn, or a reply that skips it."""

    message: str  # what to send to the workflow
    reply: AgentResponse | None = None  # a ready-made reply that skips the workflow


class Conversation(BaseModel):
    """In-memory chat history and profile for one Streamlit session."""

    model_config = {"arbitrary_types_allowed": True}

    exchanges: list[Exchange] = Field(default_factory=list)
    profile: SessionProfile = Field(default_factory=SessionProfile)
    pending: PendingInput | None = None

    @property
    def last_agent(self) -> AgentName | None:
        return self.exchanges[-1].response.agent if self.exchanges else None

    def history(self, turns: int) -> list[ChatTurn]:
        """The most recent `turns` chat turns (questions and answers), oldest first.

        Exchanges that ended in an error are left out: "Sorry, something went wrong"
        would only confuse the router and agents on the next question.
        """
        flat = [turn for e in self.exchanges if not e.response.error for turn in (e.question, e.answer)]
        return flat[-turns:] if turns > 0 else []

    def request(self, message: str, turns: int, payload: dict[str, Any] | None = None) -> AgentRequest:
        return AgentRequest(message=message, history=self.history(turns), profile=self.profile, payload=payload)

    def add(self, message: str, response: AgentResponse, asked: str | None = None) -> Exchange:
        """Record an exchange. If the agent asked for missing information, remember what to do with it.

        `asked` is the question the workflow actually answered, which differs from `message`
        when the user's message was the answer to a question we had asked.
        """
        self.pending = (
            PendingInput(kind=RISK_PENDING, original_message=asked or message, agent=response.agent)
            if response.needs_input == RISK_PENDING
            else None
        )
        exchange = Exchange(
            question=ChatTurn(role="user", content=message),
            answer=ChatTurn(role="assistant", content=response.answer, agent=response.agent),
            response=response,
        )
        self.exchanges.append(exchange)
        return exchange


def plan_turn(conversation: Conversation, message: str) -> TurnPlan:
    """Decide what to do with the user's message, given any question we are waiting on.

    - Nothing pending: it is a normal question.
    - The message names a risk level: store it in the session profile and answer the
      original question, now with that profile.
    - The profile already has a risk level (set in the sidebar meanwhile) and the message is
      short: answer the original question.
    - A short message we can't read: ask again, listing the options.
    - Anything longer: the user moved on, so drop the pending question.
    """
    pending = conversation.pending
    if pending is None or pending.kind != RISK_PENDING:
        return TurnPlan(message)

    level = parse_risk_tolerance(message)
    if level:
        conversation.profile.risk_tolerance = level
        return TurnPlan(pending.original_message)
    short = len(message.split()) <= SHORT_ANSWER_WORDS
    if short and conversation.profile.risk_tolerance:
        return TurnPlan(pending.original_message)
    if short:
        return TurnPlan(pending.original_message, AgentResponse(agent=pending.agent, answer=RISK_REASK, needs_input=RISK_PENDING))
    conversation.pending = None
    return TurnPlan(message)


def get_conversation(session: MutableMapping) -> Conversation:
    """The current session's conversation, created on first use."""
    if not isinstance(session.get(SESSION_KEY), Conversation):
        session[SESSION_KEY] = Conversation()
    return session[SESSION_KEY]


def reset_conversation(session: MutableMapping) -> Conversation:
    """Start over: clears the history and the session profile (front-end spec §6)."""
    session[SESSION_KEY] = Conversation()
    return session[SESSION_KEY]
