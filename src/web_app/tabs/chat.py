"""Chat tab (Stories 5.1, 5.2 and 7.1): the conversation, connected to the LangGraph workflow.

Layout follows front-end spec §4.1. Each answer shows, in order: the agent badge,
the answer, its freshness labels, the disclaimer callout (advice only) and a
collapsed Sources section.
"""

from __future__ import annotations

import logging

import streamlit as st

from src.agents.base import AGENT_FAILED
from src.core.models import AgentResponse, ChatTurn
from src.utils.logging import get_logger, log_event
from src.web_app import components
from src.workflow.conversation import get_conversation, plan_turn

logger = get_logger(__name__)

WELCOME = (
    "Hi, I'm Finnie. I can explain investing concepts, look at your portfolio, check stock and fund prices, "
    "plan savings goals, summarize financial news and explain US retirement accounts. "
    "Try one of these, or ask your own question:"
)
EXAMPLE_QUESTIONS = [
    "What is compound interest?",
    "How much should I save each month for a $20,000 goal?",
    "What's the difference between a 401(k) and a Roth IRA?",
    "How is VTI doing today?",
]
EXAMPLE_KEY = "queued_example_question"


def _ask_example(question: str) -> None:
    """Button callback: queue the example so the next run answers it as if it had been typed."""
    st.session_state[EXAMPLE_KEY] = question


def render_message(turn: ChatTurn, response: AgentResponse | None = None) -> None:
    """One chat message. Assistant answers carry their badge, labels, disclaimer and sources."""
    with st.chat_message(turn.role):
        if response is not None:
            components.agent_badge(response.agent)
        if turn.role == "assistant" and response is not None:
            components.render_answer(turn.content)
        else:
            st.markdown(turn.content)
        if response is None:
            return
        components.freshness_labels(response.labels)
        if response.disclaimer:
            components.disclaimer_callout(response.disclaimer)
        components.sources_expander(response.sources)


def render_header() -> None:
    title, action = st.columns([4, 1])
    title.subheader("Chat")
    with action:
        components.render_new_conversation("tab")


def render(services=None, runner=None, history_turns: int = 10, timeout: float = 120) -> None:
    render_header()
    if services is None or runner is None:
        st.info("The chat isn't available right now. Please check the configuration message above.")
        return

    conversation = get_conversation(st.session_state)
    queued = st.session_state.pop(EXAMPLE_KEY, None)  # an example question the user just clicked
    if not conversation.exchanges and not queued:
        st.markdown(WELCOME)
        for i, example in enumerate(EXAMPLE_QUESTIONS):
            st.button(example, key=f"example_{i}", on_click=_ask_example, args=(example,), width="stretch")

    for exchange in conversation.exchanges:
        render_message(exchange.question)
        render_message(exchange.answer, exchange.response)

    question = st.chat_input("Ask Finnie about investing…") or queued
    if not question:
        return
    render_message(ChatTurn(role="user", content=question))
    plan = plan_turn(conversation, question)  # may store a risk level the user just gave us
    if plan.reply is not None:
        response = plan.reply
    else:
        with st.spinner("Finnie is thinking…"):
            try:
                response = runner.run(services.workflow.run(conversation.request(plan.message, history_turns)), timeout)
            except Exception as exc:  # the workflow never raises, but the runner or loop might
                log_event(logger, "error", level=logging.ERROR, kind="chat_failed", detail=type(exc).__name__)
                response = AgentResponse(agent=None, answer=AGENT_FAILED, error=True)

    conversation.add(question, response, asked=plan.message)
    # Re-render the whole page so the sidebar and the New conversation buttons see the updated chat.
    st.rerun()
