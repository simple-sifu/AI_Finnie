"""Story 1.7: the app skeleton starts and shows its four tabs."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.core import config
from src.rag import index as rag_index

APP = str(Path(__file__).resolve().parents[2] / "src" / "web_app" / "app.py")
KEYS = {
    "OPENAI_API_KEY": "sk-test-openai-123456",
    "ALPHA_VANTAGE_API_KEY": "av-test-key-123456",
    "SERPAPI_API_KEY": "serp-test-key-123456",
}


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Point config at an empty folder so the real .env and config.yaml are never read."""
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    for name in [*KEYS, "TAVILY_API_KEY"]:
        monkeypatch.delenv(name, raising=False)
    st.cache_resource.clear()  # start-up is cached per process; each test starts fresh
    yield monkeypatch
    st.cache_resource.clear()


def run_app() -> AppTest:
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    return app


def test_app_starts_with_four_tabs(isolated_env):
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    app = run_app()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Chat", "Portfolio", "Markets", "Goals"]
    assert len(app.info) == 4  # one placeholder per tab
    assert app.sidebar.title[0].value == "Finnie"
    assert not app.error


def test_app_stops_with_clear_message_when_a_key_is_missing(isolated_env):
    isolated_env.setenv("OPENAI_API_KEY", KEYS["OPENAI_API_KEY"])
    app = run_app()
    assert not app.exception
    assert len(app.error) == 1
    message = app.error[0].value
    assert "ALPHA_VANTAGE_API_KEY" in message and "SERPAPI_API_KEY" in message
    assert KEYS["OPENAI_API_KEY"] not in message
    assert not app.tabs  # nothing else renders


def test_app_warns_but_keeps_working_when_the_index_is_missing(isolated_env):
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)

    def missing():
        raise rag_index.IndexLoadError("The knowledge base index is missing (faiss.index).")

    isolated_env.setattr(rag_index, "load_index", missing)
    app = run_app()
    assert not app.exception
    assert len(app.warning) == 1 and "knowledge base isn't available" in app.warning[0].value
    assert [tab.label for tab in app.tabs] == ["Chat", "Portfolio", "Markets", "Goals"]


def test_app_shows_no_warning_when_the_index_loads(isolated_env):
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    app = run_app()
    assert not app.warning
