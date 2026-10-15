"""Finnie Streamlit app (Story 1.7). Run with: streamlit run src/web_app/app.py"""

import sys
from pathlib import Path

# `streamlit run` puts this file's folder on sys.path, not the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from src import __version__  # noqa: E402
from src.core.config import ConfigError, Settings, load_settings  # noqa: E402
from src.utils.logging import get_logger, log_event, setup_logging_from_settings  # noqa: E402
from src.web_app.tabs import chat, goals, markets, portfolio  # noqa: E402

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


def render_sidebar() -> None:
    with st.sidebar:
        st.title("Finnie")
        st.caption("AI Finance Assistant")
        with st.expander("About Finnie"):
            st.write(ABOUT_TEXT)


def main() -> None:
    st.set_page_config(page_title="Finnie", layout="wide")
    try:
        start_up()
    except ConfigError as exc:
        st.error(f"Finnie can't start because of a configuration problem.\n\n{exc}")
        st.stop()

    render_sidebar()
    for tab, module in zip(st.tabs(list(TABS)), TABS.values()):
        with tab:
            module.render()


main()
