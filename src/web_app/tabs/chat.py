"""Chat tab (Story 5.1): the conversation, connected to the LangGraph workflow.

Styling and the full message layout (agent badges, sources, labels and the
disclaimer callout) are finished in Story 7.1.
"""

from __future__ import annotations

import streamlit as st

from src.core.models import AgentRequest, AgentResponse, ChatTurn, SessionProfile, format_sources

MESSAGES_KEY = "chat_messages"  # list of (ChatTurn, AgentResponse | None)


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


def render(services=None, runner=None, history_turns: int = 10) -> None:
    st.subheader("Chat")
    messages = st.session_state.setdefault(MESSAGES_KEY, [])
    if services is None or runner is None:
        st.info("The chat isn't available right now. Please check the configuration message above.")
        return

    for turn, response in messages:
        _render(turn, response)

    question = st.chat_input("Ask Finnie about investing…")
    if not question:
        return
    user_turn = ChatTurn(role="user", content=question)
    _render(user_turn, None)

    history = [turn for turn, _ in messages][-history_turns:]
    profile = st.session_state.get("profile", SessionProfile())
    with st.spinner("Finnie is thinking…"):
        response = runner.run(services.workflow.run(AgentRequest(message=question, history=history, profile=profile)))
    reply = ChatTurn(role="assistant", content=response.answer, agent=response.agent)
    messages.extend([(user_turn, None), (reply, response)])
    _render(reply, response)
