"""The base every Finnie agent builds on (Story 3.1, architecture §7.1).

Each agent implements `_run`. The shared `run` adds what every agent must do:
- catch any failure and return a friendly message instead of an error (NFR1),
- log which agent handled the request and any failure (Story 1.6),
- apply the disclaimer policy to advice-type answers (FR28, D-7, D-43).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import ClassVar, Literal

from pydantic import BaseModel, Field

from src.core.disclaimer import apply_disclaimer
from src.core.llm import LLMClient, LLMUnavailableError
from src.core.models import AgentName, AgentRequest, AgentResponse, SessionProfile
from src.utils.logging import get_logger, log_event

logger = get_logger(__name__)

# Friendly messages (front-end spec §6).
AGENT_FAILED = "Sorry, something went wrong answering that. Please try asking again, maybe in different words."
LLM_UNAVAILABLE = "Finnie's assistant is temporarily unavailable. Please try again in a minute."

# Shared style rules for every agent's system prompt (NFR8).
BEGINNER_STYLE = """You are part of Finnie, a friendly financial education assistant for beginner investors in the United States.

How to write:
- Use plain, everyday language. Avoid jargon; when you must use a financial term, explain it in a few words.
- Keep answers short: a few short paragraphs or a brief list. Lead with the direct answer.
- Use small, concrete examples with round numbers.
- Be accurate and conservative. Never promise returns or certainty about the future.
- Everything is about the US: US accounts, US taxes and US markets.

Classifying your answer (response_type):
- "education": you explain how something works in general, without telling this person what to do.
- "advice": you recommend a specific action for this person, such as what to buy or sell, how much to invest, or which account to choose.
- "uncertain": you aren't sure which applies, or the answer mixes both.
"""

RISK_QUESTION = (
    "To tailor this to you, how much risk are you comfortable with? "
    "Conservative: you prefer stability and accept slower growth. "
    "Moderate: a balance of growth and stability. "
    "Aggressive: you accept big ups and downs for the chance of more growth. "
    "You can answer here, or set it in the sidebar."
)

LEVEL_GUIDANCE = {
    "beginner": "The user is a beginner. Assume no prior financial knowledge.",
    "intermediate": "The user knows the basics. You can go a little deeper, but still explain less common terms.",
}


class LLMAnswer(BaseModel):
    """The structured reply agents ask the model for."""

    answer: str = Field(description="The reply to show the user, in plain language.")
    response_type: Literal["advice", "education", "uncertain"] = Field(
        description="advice, education or uncertain, as defined in the instructions."
    )


class BaseAgent(ABC):
    name: ClassVar[AgentName]
    instructions: ClassVar[str]  # the agent's own job, added after the shared style rules
    requires_risk_tolerance: ClassVar[bool] = False  # True: ask for it in the chat when it isn't set

    def __init__(self, llm: LLMClient, disclaimer_text: str):
        self.llm = llm
        self.disclaimer_text = disclaimer_text

    def system_prompt(self, profile: SessionProfile) -> str:
        parts = [BEGINNER_STYLE, self.instructions.strip(), LEVEL_GUIDANCE[profile.knowledge_level]]
        if profile.risk_tolerance:
            parts.append(f"The user's risk tolerance is {profile.risk_tolerance}.")
        if profile.goal_note:
            parts.append(f"The user's goal: {profile.goal_note}")
        return "\n\n".join(parts)

    async def run(self, request: AgentRequest) -> AgentResponse:
        log_event(logger, "agent", agent=self.name.value)
        if self.requires_risk_tolerance and request.profile.risk_tolerance is None:
            return AgentResponse(agent=self.name, answer=RISK_QUESTION, needs_input="risk_tolerance")
        try:
            response = await self._run(request)
        except LLMUnavailableError:
            return self._failure(LLM_UNAVAILABLE)
        except Exception as exc:  # any agent bug must become a friendly message, never a crash
            logger.exception("agent %s failed", self.name.value)
            log_event(logger, "error", level=logging.ERROR, kind="agent_failed", agent=self.name.value, detail=type(exc).__name__)
            return self._failure(AGENT_FAILED)
        return apply_disclaimer(response, self.disclaimer_text)

    async def ask(self, request: AgentRequest, extra_context: str = "") -> LLMAnswer:
        """Ask the shared LLM for a structured answer using this agent's system prompt."""
        system = self.system_prompt(request.profile)
        if extra_context:
            system = f"{system}\n\n{extra_context}"
        return await self.llm.structured(LLMAnswer, system, request.message, request.history)

    @abstractmethod
    async def _run(self, request: AgentRequest) -> AgentResponse:
        """The agent's own work. Exceptions are handled by `run`."""

    def _failure(self, message: str) -> AgentResponse:
        return AgentResponse(agent=self.name, answer=message, response_type="education", error=True)
