"""Route each chat message to exactly one agent (Story 5.1, D-16, architecture §6.2)."""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from src.core.llm import LLMUnavailableError
from src.core.models import AgentName, AgentRequest
from src.utils.logging import get_logger, log_event

logger = get_logger(__name__)

CLARIFY, OFF_TOPIC = "clarify", "off_topic"
Route = Literal["finance_qa", "portfolio", "market", "goal_planning", "news", "tax", "clarify", "off_topic"]

ROUTER_PROMPT = """You route questions for Finnie, a financial education assistant for US beginners.
Pick exactly ONE route for the user's latest message. Use the earlier conversation to understand short follow-ups.

Routes:
- finance_qa: general finance or investing concepts. e.g. "What is compound interest?", "ETFs vs mutual funds?", "What is a bond?"
- portfolio: the user's own holdings or portfolio. e.g. "Analyze my portfolio", "Am I diversified?", "Are my fees too high?"
- market: prices or recent performance of specific stocks, funds or the market. e.g. "How is VTI doing?", "What's Apple's stock price?", "How's the market today?"
- goal_planning: saving toward a goal or how much to save. e.g. "How much should I save monthly for a $20,000 down payment?", "Can I retire at 60?"
- news: current financial news or events. e.g. "What's in the financial news today?", "Why did stocks fall this week?"
- tax: US tax concepts and accounts. e.g. "401(k) vs Roth IRA?", "How are capital gains taxed?", "What is an HSA?"
- clarify: a finance question too vague to route. Also write a short clarifying_question.
- off_topic: not about personal finance or investing at all.

Give a confidence from 0 to 1."""


class RouteDecision(BaseModel):
    route: Route
    confidence: float = Field(ge=0, le=1)
    clarifying_question: str | None = Field(default=None, description="Only for route=clarify: one short question.")


class Router:
    def __init__(self, llm, min_confidence: float = 0.5):
        self.llm = llm
        self.min_confidence = min_confidence

    async def classify(self, request: AgentRequest) -> RouteDecision:
        """Classify a message.

        If routing fails, fall back to Finance Q&A (Story 5.3 AC 1). If OpenAI itself is
        unavailable, raise LLMUnavailableError: no agent could answer either, so the
        workflow tells the user straight away instead of retrying the same outage.
        """
        try:
            decision = await self.llm.structured(RouteDecision, ROUTER_PROMPT, request.message, request.history)
        except LLMUnavailableError:
            raise
        except Exception as exc:  # a broken router must never block the chat
            log_event(logger, "error", level=logging.ERROR, kind="router_failed", detail=type(exc).__name__)
            return RouteDecision(route=AgentName.FINANCE_QA.value, confidence=0.0)
        if decision.route not in (CLARIFY, OFF_TOPIC) and decision.confidence < self.min_confidence:
            decision = RouteDecision(
                route=CLARIFY,
                confidence=decision.confidence,
                clarifying_question=decision.clarifying_question,
            )
        log_event(logger, "route", route=decision.route, confidence=round(decision.confidence, 2))
        return decision
