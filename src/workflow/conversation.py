"""Conversation state for one browser session (Story 5.2, D-15, architecture §6.3).

One object holds everything the router and agents share across turns: the
message history, the agent that handled the last turn and the session
profile. It lives only in Streamlit session state, in memory; nothing is
written to disk, so it ends when the session ends.
"""

from __future__ import annotations

from collections.abc import MutableMapping
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


class Conversation(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    exchanges: list[Exchange] = Field(default_factory=list)
    profile: SessionProfile = Field(default_factory=SessionProfile)

    @property
    def last_agent(self) -> AgentName | None:
        return self.exchanges[-1].response.agent if self.exchanges else None

    def history(self, turns: int) -> list[ChatTurn]:
        """The most recent `turns` chat turns (questions and answers), oldest first."""
        flat = [turn for exchange in self.exchanges for turn in (exchange.question, exchange.answer)]
        return flat[-turns:] if turns > 0 else []

    def request(self, message: str, turns: int, payload: dict[str, Any] | None = None) -> AgentRequest:
        return AgentRequest(message=message, history=self.history(turns), profile=self.profile, payload=payload)

    def add(self, message: str, response: AgentResponse) -> Exchange:
        exchange = Exchange(
            question=ChatTurn(role="user", content=message),
            answer=ChatTurn(role="assistant", content=response.answer, agent=response.agent),
            response=response,
        )
        self.exchanges.append(exchange)
        return exchange


def get_conversation(session: MutableMapping) -> Conversation:
    """The current session's conversation, created on first use."""
    if not isinstance(session.get(SESSION_KEY), Conversation):
        session[SESSION_KEY] = Conversation()
    return session[SESSION_KEY]


def reset_conversation(session: MutableMapping) -> Conversation:
    """Start over: clears the history and the session profile (front-end spec §6)."""
    session[SESSION_KEY] = Conversation()
    return session[SESSION_KEY]
