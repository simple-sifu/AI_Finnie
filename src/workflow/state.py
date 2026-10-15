"""LangGraph state for one chat turn (architecture §6.3).

The conversation itself lives in Streamlit session state and is passed in as
part of the request on every turn, so no LangGraph checkpointer is needed.
"""

from __future__ import annotations

from typing import TypedDict

from src.core.models import AgentRequest, AgentResponse


class FinnieState(TypedDict, total=False):
    request: AgentRequest
    route: str | None
    confidence: float | None
    clarifying_question: str | None
    response: AgentResponse | None
