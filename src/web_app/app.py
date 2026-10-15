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
from src.web_app import components  # noqa: E402
from src.web_app.tabs import chat, goals, markets, portfolio  # noqa: E402
from src.workflow.conversation import get_conversation  # noqa: E402
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


KNOWLEDGE_LEVELS = {"Beginner": "beginner", "Intermediate": "intermediate"}
RISK_LEVELS = {"Conservative": "conservative", "Moderate": "moderate", "Aggressive": "aggressive"}
GOAL_NOTE_MAX_CHARS = 200


def _label(options: dict[str, str], value: str | None) -> str | None:
    return next((label for label, key in options.items() if key == value), None)


def render_profile() -> None:
    """The session profile (Story 5.5, front-end spec §2). It lasts only for this session (D-15).

    The widgets are built from the conversation's profile on every run, so a risk level
    the user gives in the chat shows up here, and "New conversation" resets them.
    """
    profile = get_conversation(st.session_state).profile
    st.subheader("Your profile")
    level = st.selectbox(
        "Knowledge level", list(KNOWLEDGE_LEVELS), index=list(KNOWLEDGE_LEVELS.values()).index(profile.knowledge_level),
        help="Beginner explains everything from scratch; Intermediate assumes the basics.",
    )
    risk_label = _label(RISK_LEVELS, profile.risk_tolerance)
    risk = st.selectbox(
        "Risk tolerance", list(RISK_LEVELS), index=None if risk_label is None else list(RISK_LEVELS).index(risk_label),
        placeholder="Not set yet",
        help="How much ups and downs in your investments you can handle. Goal planning uses it.",
    )
    goal = st.text_input("Goal (optional)", value=profile.goal_note or "", max_chars=GOAL_NOTE_MAX_CHARS,
                         placeholder="e.g. a house down payment in 5 years")
    profile.knowledge_level = KNOWLEDGE_LEVELS[level]
    profile.risk_tolerance = RISK_LEVELS.get(risk) if risk else None
    profile.goal_note = goal.strip() or None


def render_sidebar() -> None:
    with st.sidebar:
        st.title("Finnie")
        st.caption("AI Finance Assistant")
        render_profile()
        components.render_new_conversation("sidebar")
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
    with tabs[1]:
        portfolio.render(services, runner, settings.chat.timeout_s + 15)
    for tab, module in zip(tabs[2:], list(TABS.values())[2:]):
        with tab:
            module.render()


main()
