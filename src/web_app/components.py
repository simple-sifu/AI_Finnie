"""Reusable display pieces for the Streamlit app (front-end spec §3).

Shared by the Chat tab now, and by the Portfolio, Markets and Goals tabs later:
agent badges, freshness labels, disclaimer callouts, source lists, and the
New conversation action.
"""

from __future__ import annotations

import streamlit as st

from src.core.freshness import DataLabel
from src.core.models import AgentName, Source, format_sources
from src.utils.logging import get_logger, log_event
from src.workflow.conversation import get_conversation, reset_conversation

logger = get_logger(__name__)

# DataLabel colors -> Streamlit's colored-text names. The word in the label always carries
# the meaning too, so color is never the only signal (front-end spec §3.1, Story 7.5).
_STREAMLIT_COLORS = {"green": "green", "amber": "orange", "grey": "gray"}
NEW_CONVERSATION_CONFIRM = "Start a new conversation? Your current chat and profile will be cleared."


def agent_badge(agent: AgentName | None) -> None:
    """A small label above an answer naming the agent that wrote it ("Finnie" for Finnie's own replies)."""
    st.markdown(f":blue-badge[{agent.display_name if agent else 'Finnie'}]")


def freshness_label(label: DataLabel) -> None:
    """`● Live · as of Oct 14 close`, with the dot colored green, amber or grey."""
    st.caption(f":{_STREAMLIT_COLORS.get(label.color, 'gray')}[●] {label.text}")


def freshness_labels(labels: list[DataLabel]) -> None:
    seen: set[str] = set()
    for label in labels:
        if label.text not in seen:  # one line per distinct label
            seen.add(label.text)
            freshness_label(label)


def disclaimer_callout(text: str) -> None:
    """The disclaimer, set apart from the answer in Streamlit's warning style."""
    st.warning(text)


def sources_expander(sources: list[Source]) -> None:
    """A collapsed "Sources" section; nothing at all when there are no sources."""
    if sources:
        with st.expander("Sources"):
            st.markdown(format_sources(sources))


def render_new_conversation(location: str) -> None:
    """The New conversation action, with its confirmation (front-end spec §6).

    `location` ("sidebar" or "tab") keeps each copy's widgets and confirmation separate.
    Disabled until there is something to clear.
    """
    flag = f"confirm_reset_{location}"
    if not st.session_state.get(flag):
        has_chat = bool(get_conversation(st.session_state).exchanges)
        if st.button("New conversation", key=f"new_conversation_{location}", disabled=not has_chat):
            st.session_state[flag] = True
            st.rerun()
        return
    st.warning(NEW_CONVERSATION_CONFIRM)
    yes, cancel = st.columns(2)
    if yes.button("Yes, start over", key=f"reset_yes_{location}", type="primary"):
        reset_conversation(st.session_state)
        st.session_state[flag] = False
        log_event(logger, "conversation_reset", location=location)
        st.rerun()
    if cancel.button("Cancel", key=f"reset_cancel_{location}"):
        st.session_state[flag] = False
        st.rerun()
