"""Chat tab (Stories 5.1 and 5.2): the conversation, connected to the LangGraph workflow.

Styling and the full message layout (agent badges, sources, labels and the
disclaimer callout) are finished in Story 7.1.
"""

from __future__ import annotations

import logging

import streamlit as st

from src.agents.base import AGENT_FAILED
from src.core.models import AgentResponse, ChatTurn, format_sources
from src.utils.logging import get_logger, log_event
from src.workflow.conversation import get_conversation, plan_turn

logger = get_logger(__name__)


def _render(turn: ChatTurn, response: AgentResponse | None) -> None:
    with st.chat_message(turn.role):
        if response is not None:
            st.caption(response.agent.display_name if response.agent else "Finnie")
        st.markdown(turn.content)
        if response is None:
            return
        if response.labels:
            st.caption(" · ".join(dict.fromkeys(label.text for label in response.labels)))
        if response.disclaimer:
            st.warning(response.disclaimer)
        if response.sources:
            with st.expander("Sources"):
                st.markdown(format_sources(response.sources))


def render(services=None, runner=None, history_turns: int = 10, timeout: float = 120) -> None:
    st.subheader("Chat")
    if services is None or runner is None:
        st.info("The chat isn't available right now. Please check the configuration message above.")
        return

    conversation = get_conversation(st.session_state)
    for exchange in conversation.exchanges:
        _render(exchange.question, None)
        _render(exchange.answer, exchange.response)

    question = st.chat_input("Ask Finnie about investing…")
    if not question:
        return
    _render(ChatTurn(role="user", content=question), None)
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
    # Re-render the whole page so the sidebar (New conversation) sees the updated chat.
    st.rerun()
