"""The LangGraph workflow (Story 5.1, architecture §6.1).

    START -> validate_input -> route -> one agent -> finalize -> END
                       |           \\-> (clarify / off_topic) -> finalize
                       \\-> (invalid input) -> finalize

Each agent node wraps one agent's `run`, which already turns failures into
friendly messages. `finalize` re-applies the disclaimer policy so no path can
skip it (architecture §7.4).
"""

from __future__ import annotations

import uuid

from langgraph.graph import END, START, StateGraph

from src.agents.base import BaseAgent
from src.core.disclaimer import apply_disclaimer
from src.core.models import AgentName, AgentRequest, AgentResponse
from src.utils.logging import request_context
from src.workflow.router import CLARIFY, OFF_TOPIC, Router
from src.workflow.state import FinnieState

EMPTY_INPUT = "Ask me anything about investing or personal finance."
TOO_LONG = "That message is a bit long. Please shorten it to under {limit} characters."
DEFAULT_CLARIFY = "Could you tell me a bit more about what you'd like to know?"
OFF_TOPIC_REPLY = (
    "I'm Finnie, and I help with investing and personal finance: explaining concepts, analyzing "
    "your portfolio, checking stock and fund prices, planning savings goals, financial news and US "
    "retirement and tax accounts. What would you like to know?"
)
COMING_SOON = {
    AgentName.GOAL_PLANNING: "Goal planning is coming soon.",
    AgentName.NEWS: "Financial news is coming soon.",
    AgentName.TAX: "Tax education is coming soon.",
}
UNAVAILABLE = "That part of Finnie isn't available right now. Please try again later."
COMING_SOON_SUFFIX = " For now I can explain finance concepts, analyze your portfolio and look up stock and fund prices."


class FinnieWorkflow:
    def __init__(self, router: Router, agents: dict[AgentName, BaseAgent], disclaimer_text: str, max_input_chars: int = 2000):
        self.router = router
        self.agents = agents
        self.disclaimer_text = disclaimer_text
        self.max_input_chars = max_input_chars
        self.graph = self._build()

    # -- nodes ---------------------------------------------------------------

    async def _validate(self, state: FinnieState) -> FinnieState:
        message = state["request"].message.strip()
        if not message:
            return {"response": AgentResponse(agent=None, answer=EMPTY_INPUT)}
        if len(message) > self.max_input_chars:
            return {"response": AgentResponse(agent=None, answer=TOO_LONG.format(limit=self.max_input_chars))}
        return {}

    async def _route(self, state: FinnieState) -> FinnieState:
        decision = await self.router.classify(state["request"])
        return {"route": decision.route, "confidence": decision.confidence, "clarifying_question": decision.clarifying_question}

    def _agent_node(self, name: AgentName):
        async def node(state: FinnieState) -> FinnieState:
            agent = self.agents.get(name)
            if agent is None:
                answer = COMING_SOON[name] + COMING_SOON_SUFFIX if name in COMING_SOON else UNAVAILABLE
                return {"response": AgentResponse(agent=name, answer=answer)}
            return {"response": await agent.run(state["request"])}

        return node

    async def _clarify(self, state: FinnieState) -> FinnieState:
        return {"response": AgentResponse(agent=None, answer=state.get("clarifying_question") or DEFAULT_CLARIFY)}

    async def _off_topic(self, state: FinnieState) -> FinnieState:
        return {"response": AgentResponse(agent=None, answer=OFF_TOPIC_REPLY)}

    async def _finalize(self, state: FinnieState) -> FinnieState:
        return {"response": apply_disclaimer(state["response"], self.disclaimer_text)}

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
        graph.add_node("finalize", self._finalize)

        graph.add_edge(START, "validate_input")
        graph.add_conditional_edges(
            "validate_input", lambda s: "finalize" if s.get("response") else "route", {"finalize": "finalize", "route": "route"}
        )
        targets = {name.value: name.value for name in AgentName} | {CLARIFY: CLARIFY, OFF_TOPIC: OFF_TOPIC}
        graph.add_conditional_edges("route", lambda s: s["route"], targets)
        graph.add_edge(CLARIFY, "finalize")
        graph.add_edge(OFF_TOPIC, "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    async def run(self, request: AgentRequest) -> AgentResponse:
        """Answer one chat message. Every line logged during it shares a request ID."""
        with request_context(uuid.uuid4().hex[:8]):
            final = await self.graph.ainvoke({"request": request})
        return final["response"]
