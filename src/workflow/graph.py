"""The LangGraph workflow (Story 5.1, architecture §6.1).

    START -> validate_input -> route -> one agent -> finalize -> END
                       |           \\-> (clarify / off_topic) -> finalize
                       \\-> (invalid input) -> finalize

Each agent node wraps one agent's `run`, which already turns failures into
friendly messages. `finalize` re-applies the disclaimer policy so no path can
skip it (architecture §7.4).
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from langgraph.graph import END, START, StateGraph

from src.agents.base import AGENT_FAILED, LLM_UNAVAILABLE, BaseAgent
from src.core.disclaimer import apply_disclaimer
from src.core.llm import LLMUnavailableError
from src.core.models import AgentName, AgentRequest, AgentResponse
from src.utils.logging import get_logger, log_event, request_context
from src.workflow.router import CLARIFY, OFF_TOPIC, Router
from src.workflow.state import FinnieState

logger = get_logger(__name__)

UNAVAILABLE_ROUTE = "unavailable"
TOO_SLOW = "That's taking longer than expected. Please try asking again in a moment."
EMPTY_INPUT = "Ask me anything about investing or personal finance."
TOO_LONG = "That message is a bit long. Please shorten it to under {limit} characters."
DEFAULT_CLARIFY = "Could you tell me a bit more about what you'd like to know?"
OFF_TOPIC_REPLY = (
    "I'm Finnie, and I help with investing and personal finance: explaining concepts, analyzing "
    "your portfolio, checking stock and fund prices, planning savings goals, financial news and US "
    "retirement and tax accounts. What would you like to know?"
)
# Shown if an agent couldn't be built at start-up, e.g. the knowledge base index is missing (Finance Q&A and Tax).
UNAVAILABLE = "That part of Finnie isn't available right now. Please try again later."


class FinnieWorkflow:
    """LangGraph graph: validate, route, run one agent, finalize with disclaimers and labels."""

    def __init__(
        self, router: Router, agents: dict[AgentName, BaseAgent], disclaimer_text: str,
        max_input_chars: int = 2000, timeout_s: float = 90,
    ):
        self.router = router
        self.agents = agents
        self.disclaimer_text = disclaimer_text
        self.max_input_chars = max_input_chars
        self.timeout_s = timeout_s
        self.graph = self._build()

    # -- nodes ---------------------------------------------------------------

    async def _validate(self, state: FinnieState) -> FinnieState:
        request = state["request"]
        # Control characters (null bytes, escape codes) are removed; ordinary text is untouched.
        message = "".join(ch for ch in request.message if ch.isprintable() or ch in "\n\t").strip()
        # Nothing to answer: empty, or no letters or digits at all ("???", "...", emoji only).
        if not any(ch.isalnum() for ch in message):
            return {"response": AgentResponse(agent=None, answer=EMPTY_INPUT)}
        if len(message) > self.max_input_chars:
            return {"response": AgentResponse(agent=None, answer=TOO_LONG.format(limit=self.max_input_chars))}
        if message != request.message:
            return {"request": request.model_copy(update={"message": message})}
        return {}

    async def _route(self, state: FinnieState) -> FinnieState:
        try:
            decision = await self.router.classify(state["request"])
        except LLMUnavailableError:
            return {"route": UNAVAILABLE_ROUTE, "confidence": 0.0, "clarifying_question": None}
        return {"route": decision.route, "confidence": decision.confidence, "clarifying_question": decision.clarifying_question}

    def _agent_node(self, name: AgentName):
        async def node(state: FinnieState) -> FinnieState:
            agent = self.agents.get(name)
            if agent is None:
                return {"response": AgentResponse(agent=name, answer=UNAVAILABLE)}
            try:
                return {"response": await agent.run(state["request"])}
            except Exception as exc:  # agents already catch their own errors; this is the last safety net
                log_event(logger, "error", level=logging.ERROR, kind="agent_node_failed", agent=name.value, detail=type(exc).__name__)
                return {"response": AgentResponse(agent=name, answer=AGENT_FAILED, error=True)}

        return node

    async def _clarify(self, state: FinnieState) -> FinnieState:
        return {"response": AgentResponse(agent=None, answer=state.get("clarifying_question") or DEFAULT_CLARIFY)}

    async def _unavailable(self, state: FinnieState) -> FinnieState:
        return {"response": AgentResponse(agent=None, answer=LLM_UNAVAILABLE, error=True)}

    async def _off_topic(self, state: FinnieState) -> FinnieState:
        return {"response": AgentResponse(agent=None, answer=OFF_TOPIC_REPLY)}

    async def _finalize(self, state: FinnieState) -> FinnieState:
        response = state.get("response") or AgentResponse(agent=None, answer=AGENT_FAILED, error=True)
        return {"response": apply_disclaimer(response, self.disclaimer_text)}

    # -- graph ---------------------------------------------------------------

    def _build(self):
        graph = StateGraph(FinnieState)
        graph.add_node("validate_input", self._validate)
        graph.add_node("route", self._route)
        for name in AgentName:
            graph.add_node(name.value, self._agent_node(name))
            graph.add_edge(name.value, "finalize")
        graph.add_node(CLARIFY, self._clarify)
        graph.add_node(OFF_TOPIC, self._off_topic)
        graph.add_node(UNAVAILABLE_ROUTE, self._unavailable)
        graph.add_node("finalize", self._finalize)

        graph.add_edge(START, "validate_input")
        graph.add_conditional_edges(
            "validate_input", lambda s: "finalize" if s.get("response") else "route", {"finalize": "finalize", "route": "route"}
        )
        targets = {name.value: name.value for name in AgentName} | {
            CLARIFY: CLARIFY, OFF_TOPIC: OFF_TOPIC, UNAVAILABLE_ROUTE: UNAVAILABLE_ROUTE,
        }
        graph.add_conditional_edges("route", lambda s: s["route"], targets)
        graph.add_edge(CLARIFY, "finalize")
        graph.add_edge(OFF_TOPIC, "finalize")
        graph.add_edge(UNAVAILABLE_ROUTE, "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    async def run(self, request: AgentRequest) -> AgentResponse:
        """Answer one chat message. Every line logged during it shares a request ID.

        Never raises: a timeout or an unexpected failure becomes a friendly message, so
        the chat stays usable (Story 5.3).
        """
        with request_context(uuid.uuid4().hex[:8]):
            try:
                final = await asyncio.wait_for(self.graph.ainvoke({"request": request}), self.timeout_s)
            except asyncio.TimeoutError:
                log_event(logger, "error", level=logging.ERROR, kind="timeout", seconds=self.timeout_s)
                return AgentResponse(agent=None, answer=TOO_SLOW, error=True)
            except Exception as exc:
                logger.exception("workflow failed")
                log_event(logger, "error", level=logging.ERROR, kind="workflow_failed", detail=type(exc).__name__)
                return AgentResponse(agent=None, answer=AGENT_FAILED, error=True)
        return final["response"]
