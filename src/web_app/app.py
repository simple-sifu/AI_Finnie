"""Finnie Streamlit app (Story 1.7). Run with: streamlit run src/web_app/app.py"""

import logging
import sys
from pathlib import Path

# `streamlit run` puts this file's folder on sys.path, not the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from src import __version__  # noqa: E402
from src.core.config import ConfigError, Settings, load_settings  # noqa: E402
from src.core.async_runner import AsyncRunner  # noqa: E402
from src.rag.index import IndexLoadError, KnowledgeIndex, is_stale, load_index  # noqa: E402
from src.utils.logging import get_logger, log_event, setup_logging_from_settings  # noqa: E402
from src.web_app.tabs import chat, goals, markets, portfolio  # noqa: E402
from src.workflow.conversation import get_conversation, reset_conversation  # noqa: E402
from src.workflow.factory import FinnieServices, build_services  # noqa: E402

TABS = {"Chat": chat, "Portfolio": portfolio, "Markets": markets, "Goals": goals}

ABOUT_TEXT = (
    "Finnie is an educational tool. Information is for learning and may be delayed. "
    "Advice-type answers include a disclaimer."
)

logger = get_logger("src.web_app.app")  # __name__ is "__main__" under streamlit run


@st.cache_resource
def start_up() -> Settings:
    """Load settings and configure logging once per app process."""
    settings = load_settings()
    setup_logging_from_settings(settings)
    log_event(logger, "app_start", version=__version__, mode=settings.market.mode)
    return settings


@st.cache_resource
def load_knowledge() -> KnowledgeIndex | None:
    """Load the knowledge-base index once. Returns None, after logging why, if it can't load."""
    try:
        knowledge = load_index()
    except IndexLoadError as exc:
        log_event(logger, "error", level=logging.ERROR, kind="index_load", detail=str(exc))
        return None
    log_event(logger, "index_loaded", chunks=knowledge.size)
    if is_stale(knowledge):
        log_event(
            logger, "index_stale", level=logging.WARNING,
            detail="content changed since the index was built; run python -m src.rag.build_index",
        )
    return knowledge


@st.cache_resource
def get_runner() -> AsyncRunner:
    """One background event loop for the whole app (architecture §10)."""
    return AsyncRunner()


@st.cache_resource
def get_services(_settings: Settings) -> FinnieServices:
    """Build the LLM client, data services, agents and workflow once per app process."""
    return build_services(_settings)


NEW_CONVERSATION_CONFIRM = "Start a new conversation? Your current chat and profile will be cleared."


def render_new_conversation() -> None:
    """The New conversation action, with the confirmation from front-end spec §6."""
    if not st.session_state.get("confirm_reset"):
        if st.button("New conversation", disabled=not get_conversation(st.session_state).exchanges):
            st.session_state["confirm_reset"] = True
            st.rerun()
        return
    st.warning(NEW_CONVERSATION_CONFIRM)
    yes, cancel = st.columns(2)
    if yes.button("Yes, start over", type="primary"):
        reset_conversation(st.session_state)
        st.session_state["confirm_reset"] = False
        log_event(logger, "conversation_reset")
        st.rerun()
    if cancel.button("Cancel"):
        st.session_state["confirm_reset"] = False
        st.rerun()


def render_sidebar() -> None:
    with st.sidebar:
        st.title("Finnie")
        st.caption("AI Finance Assistant")
        render_new_conversation()
        with st.expander("About Finnie"):
            st.write(ABOUT_TEXT)


def main() -> None:
    st.set_page_config(page_title="Finnie", layout="wide")
    try:
        settings = start_up()
    except ConfigError as exc:
        st.error(f"Finnie can't start because of a configuration problem.\n\n{exc}")
        st.stop()

    if load_knowledge() is None:
        st.warning(
            "Finnie's knowledge base isn't available right now, so answers can't cite "
            "articles. Other features still work. (Details are in the log.)"
        )

    render_sidebar()
    runner = get_runner()
    services = get_services(settings)
    tabs = st.tabs(list(TABS))
    with tabs[0]:
        chat.render(services, runner, settings.chat.history_turns, settings.chat.timeout_s + 15)
    for tab, module in zip(tabs[1:], list(TABS.values())[1:]):
        with tab:
            module.render()


main()
