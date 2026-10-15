"""Story 1.7: the app skeleton starts and shows its four tabs."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.core import config
from src.core.models import AgentName, AgentResponse, Source
from src.rag import index as rag_index
from src.workflow import factory

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
    monkeypatch.setattr(factory, "build_services", lambda settings: FakeServices())
    st.cache_resource.clear()  # start-up is cached per process; each test starts fresh
    yield monkeypatch
    st.cache_resource.clear()


class FakeWorkflow:
    def __init__(self):
        self.requests = []

    async def run(self, request):
        self.requests.append(request)
        return AgentResponse(
            agent=AgentName.FINANCE_QA,
            answer="Compound interest is interest on interest.",
            response_type="advice",
            disclaimer="Not personalized advice.",
            sources=[Source(title="How Compound Interest Grows Your Money", url="https://www.investor.gov/x",
                            source_name="Investor.gov (U.S. SEC)", category="Investing Basics")],
        )


class FakeServices:
    def __init__(self):
        self.workflow = FakeWorkflow()


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
    assert len(app.info) == 2  # the Portfolio empty state and the Goals placeholder; Markets is live (Story 7.3)
    assert len(app.chat_input) == 1  # Chat is live (Story 5.1)
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


def test_chat_question_gets_an_agent_answer(isolated_env):
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    app = run_app()
    app.chat_input[0].set_value("What is compound interest?").run()
    assert not app.exception
    texts = [m.value for m in app.markdown]
    assert "What is compound interest?" in texts and "Compound interest is interest on interest." in texts
    assert ":blue-badge[Finance Q&A]" in [m.value for m in app.markdown]
    assert any("Not personalized advice." in w.value for w in app.warning)


def test_chat_history_is_kept_between_questions(isolated_env):
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    app = run_app()
    app.chat_input[0].set_value("first question").run()
    app.chat_input[0].set_value("second question").run()
    texts = [m.value for m in app.markdown]
    assert texts.count("Compound interest is interest on interest.") == 2 and "first question" in texts


def chatted_app(isolated_env, questions=("first question",)):
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    app = run_app()
    for question in questions:
        app.chat_input[0].set_value(question).run()
    return app


def sidebar_button(app, label):
    return next(b for b in app.sidebar.button if b.label == label)


def test_history_is_sent_with_each_question(isolated_env):
    services = FakeServices()
    isolated_env.setattr(factory, "build_services", lambda settings: services)
    chatted_app(isolated_env, ("first question", "second question"))
    first, second = services.workflow.requests
    assert first.history == []
    assert [t.content for t in second.history] == ["first question", "Compound interest is interest on interest."]


def test_new_conversation_is_disabled_until_there_is_a_chat(isolated_env):
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    assert sidebar_button(run_app(), "New conversation").disabled


def test_new_conversation_asks_first_then_clears_the_chat(isolated_env):
    app = chatted_app(isolated_env)
    sidebar_button(app, "New conversation").click().run()
    assert any("Start a new conversation?" in w.value for w in app.sidebar.warning)
    sidebar_button(app, "Yes, start over").click().run()
    assert "first question" not in [m.value for m in app.markdown]
    assert sidebar_button(app, "New conversation").disabled


def test_cancel_keeps_the_chat(isolated_env):
    app = chatted_app(isolated_env)
    sidebar_button(app, "New conversation").click().run()
    sidebar_button(app, "Cancel").click().run()
    assert "first question" in [m.value for m in app.markdown]


def test_a_failing_runner_shows_a_friendly_message_and_the_chat_stays_usable(isolated_env):
    from src.agents.base import AGENT_FAILED

    class FailingWorkflow(FakeWorkflow):
        async def run(self, request):
            if len(self.requests) == 0:
                self.requests.append(request)
                raise RuntimeError("runner exploded")
            return await super().run(request)

    services = FakeServices()
    services.workflow = FailingWorkflow()
    isolated_env.setattr(factory, "build_services", lambda settings: services)
    app = chatted_app(isolated_env, ("will fail",))
    assert not app.exception and AGENT_FAILED in [m.value for m in app.markdown]
    app.chat_input[0].set_value("will work").run()
    assert not app.exception and "Compound interest is interest on interest." in [m.value for m in app.markdown]
    # the failed exchange is not sent back to the models
    assert services.workflow.requests[1].history == []


# --- Story 5.5: the session profile in the sidebar ---


def profile_box(app, label):
    return next(b for b in app.sidebar.selectbox if b.label == label)


def test_sidebar_profile_defaults(isolated_env):
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    app = run_app()
    assert profile_box(app, "Knowledge level").value == "Beginner"
    assert profile_box(app, "Knowledge level").options == ["Beginner", "Intermediate"]
    assert profile_box(app, "Risk tolerance").value is None  # no default
    assert profile_box(app, "Risk tolerance").options == ["Conservative", "Moderate", "Aggressive"]
    assert app.sidebar.text_input[0].value == ""


def test_profile_choices_reach_the_workflow(isolated_env):
    services = FakeServices()
    isolated_env.setattr(factory, "build_services", lambda settings: services)
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    app = run_app()
    profile_box(app, "Knowledge level").select("Intermediate").run()
    profile_box(app, "Risk tolerance").select("Aggressive").run()
    app.sidebar.text_input[0].input("a house in 5 years").run()
    app.chat_input[0].set_value("What is a bond?").run()
    profile = services.workflow.requests[0].profile
    assert (profile.knowledge_level, profile.risk_tolerance, profile.goal_note) == ("intermediate", "aggressive", "a house in 5 years")


def test_new_conversation_resets_the_profile_widgets(isolated_env):
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    app = run_app()
    profile_box(app, "Risk tolerance").select("Moderate").run()
    app.chat_input[0].set_value("hello").run()
    sidebar_button(app, "New conversation").click().run()
    sidebar_button(app, "Yes, start over").click().run()
    assert profile_box(app, "Risk tolerance").value is None
    assert profile_box(app, "Knowledge level").value == "Beginner" and app.sidebar.text_input[0].value == ""


def test_agent_asks_for_risk_tolerance_and_the_chat_answer_fills_the_sidebar(isolated_env):
    from src.agents.base import RISK_QUESTION

    class AskingWorkflow(FakeWorkflow):
        async def run(self, request):
            self.requests.append(request)
            if request.profile.risk_tolerance is None:
                return AgentResponse(agent=AgentName.GOAL_PLANNING, answer=RISK_QUESTION, needs_input="risk_tolerance")
            return AgentResponse(agent=AgentName.GOAL_PLANNING, answer=f"Plan for {request.profile.risk_tolerance}")

    services = FakeServices()
    services.workflow = AskingWorkflow()
    isolated_env.setattr(factory, "build_services", lambda settings: services)
    app = chatted_app(isolated_env, ("Plan my savings for a $20,000 goal",))
    assert RISK_QUESTION in [m.value for m in app.markdown] and profile_box(app, "Risk tolerance").value is None

    app.chat_input[0].set_value("moderate").run()
    texts = [m.value for m in app.markdown]
    assert "Plan for moderate" in texts  # the original question was answered with the new profile
    assert profile_box(app, "Risk tolerance").value == "Moderate"  # and the sidebar shows it
    first, second = services.workflow.requests
    assert second.message == "Plan my savings for a $20,000 goal" and second.profile.risk_tolerance == "moderate"


def test_unreadable_answer_to_the_risk_question_is_asked_again(isolated_env):
    from src.agents.base import RISK_QUESTION
    from src.workflow.conversation import RISK_REASK

    class AskingWorkflow(FakeWorkflow):
        async def run(self, request):
            self.requests.append(request)
            return AgentResponse(agent=AgentName.GOAL_PLANNING, answer=RISK_QUESTION, needs_input="risk_tolerance")

    services = FakeServices()
    services.workflow = AskingWorkflow()
    isolated_env.setattr(factory, "build_services", lambda settings: services)
    app = chatted_app(isolated_env, ("Plan my savings", "dunno"))
    assert RISK_REASK in [m.value for m in app.markdown] and len(services.workflow.requests) == 1


# --- Story 7.1: the chat interface (front-end spec §4.1) ---


def chat_tab_button(app, label):
    return next(b for b in app.tabs[0].button if b.label == label)


class RichWorkflow(FakeWorkflow):
    """Answers with everything an answer can carry: labels, a disclaimer and sources."""

    def __init__(self, agent=AgentName.MARKET):
        super().__init__()
        self.agent = agent

    async def run(self, request):
        from datetime import date, datetime, timedelta, timezone

        from src.core.freshness import DataSource, make_label

        self.requests.append(request)
        now = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)
        labels = [
            make_label(DataSource.LIVE, now, date(2026, 10, 14), now),
            make_label(DataSource.CACHE, now - timedelta(minutes=12), date(2026, 10, 14), now),
            make_label(DataSource.SAMPLE, None, None, now),
        ]
        return AgentResponse(
            agent=self.agent, answer="VTI slipped yesterday.", response_type="advice", labels=labels,
            disclaimer="Not personalized advice.",
            sources=[Source(title="Index Funds", url="https://www.investor.gov/index", source_name="Investor.gov (U.S. SEC)", category="ETFs & Mutual Funds")],
        )


def rich_app(isolated_env, workflow=None, question="How is VTI doing?"):
    services = FakeServices()
    services.workflow = workflow or RichWorkflow()
    isolated_env.setattr(factory, "build_services", lambda settings: services)
    return chatted_app(isolated_env, (question,)), services


def test_first_visit_shows_a_welcome_and_example_questions(isolated_env):
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    app = run_app()
    assert any(m.value.startswith("Hi, I'm Finnie.") for m in app.markdown)
    examples = [b.label for b in app.tabs[0].button if b.key and b.key.startswith("example_")]
    assert examples == [
        "What is compound interest?",
        "How much should I save each month for a $20,000 goal?",
        "What's the difference between a 401(k) and a Roth IRA?",
        "How is VTI doing today?",
    ]


def test_clicking_an_example_asks_that_question_and_removes_the_welcome(isolated_env):
    services = FakeServices()
    isolated_env.setattr(factory, "build_services", lambda settings: services)
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    app = run_app()
    next(b for b in app.tabs[0].button if b.key == "example_0").click().run()
    assert not app.exception and [r.message for r in services.workflow.requests] == ["What is compound interest?"]
    texts = [m.value for m in app.markdown]
    assert "What is compound interest?" in texts and "Compound interest is interest on interest." in texts
    assert not any(m.value.startswith("Hi, I'm Finnie.") for m in app.markdown)  # no welcome once chatting
    assert not [b for b in app.tabs[0].button if b.key and b.key.startswith("example_")]


def test_each_answer_shows_the_agent_that_wrote_it(isolated_env):
    app, _ = rich_app(isolated_env, RichWorkflow(AgentName.TAX))
    assert ":blue-badge[Tax Education]" in [m.value for m in app.markdown]


def test_finnies_own_replies_are_badged_finnie(isolated_env):
    app, _ = rich_app(isolated_env, RichWorkflow(agent=None))
    assert ":blue-badge[Finnie]" in [m.value for m in app.markdown]


def test_freshness_labels_sit_under_their_answer_with_colored_dots(isolated_env):
    app, _ = rich_app(isolated_env)
    labels = [c.value for c in app.caption if "●" in c.value]
    assert labels == [
        ":green[●] Live · as of Oct 14 close",
        ":orange[●] Cached · updated 12 min ago · as of Oct 14 close",
        ":gray[●] Sample data · not real prices",
    ]
    markdown = [m.value for m in app.markdown]
    assert markdown.index("VTI slipped yesterday.") < len(markdown)  # the answer is there; labels follow it as captions


def test_the_disclaimer_is_a_separate_callout_not_part_of_the_answer(isolated_env):
    app, _ = rich_app(isolated_env)
    assert [w.value for w in app.warning] == ["Not personalized advice."]
    assert "Not personalized advice." not in [m.value for m in app.markdown]


def test_sources_are_in_a_collapsed_section_under_the_answer(isolated_env):
    app, _ = rich_app(isolated_env)
    sources = [e for e in app.expander if e.label == "Sources"]
    assert len(sources) == 1 and sources[0].proto.expanded is False
    assert "[Index Funds](https://www.investor.gov/index)" in sources[0].markdown[0].value


def test_answers_without_sources_labels_or_disclaimer_show_none_of_them(isolated_env):
    class Bare(FakeWorkflow):
        async def run(self, request):
            return AgentResponse(agent=AgentName.FINANCE_QA, answer="Plain answer.")

    app, _ = rich_app(isolated_env, Bare(), "Hello")
    assert "Plain answer." in [m.value for m in app.markdown]
    assert not app.warning and not [e for e in app.expander if e.label == "Sources"]
    assert not [c for c in app.caption if "●" in c.value]


def test_a_loading_indicator_shows_while_the_answer_is_prepared(isolated_env, monkeypatch):
    shown = []
    real_spinner = st.spinner

    def recording_spinner(text="", **kwargs):
        shown.append(text)
        return real_spinner(text, **kwargs)

    monkeypatch.setattr(st, "spinner", recording_spinner)
    rich_app(isolated_env)
    assert "Finnie is thinking…" in shown  # while the answer is prepared
    assert set(shown) <= {"Finnie is thinking…", "Loading prices…"}  # the Markets tab has its own spinner


def test_new_conversation_is_available_in_the_chat_tab(isolated_env):
    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    app = run_app()
    assert chat_tab_button(app, "New conversation").disabled  # nothing to clear yet
    app, _ = rich_app(isolated_env)
    assert not chat_tab_button(app, "New conversation").disabled
    chat_tab_button(app, "New conversation").click().run()
    assert any("Start a new conversation?" in w.value for w in app.tabs[0].warning)
    chat_tab_button(app, "Yes, start over").click().run()
    assert "How is VTI doing?" not in [m.value for m in app.markdown]
    assert any(m.value.startswith("Hi, I'm Finnie.") for m in app.markdown)  # back to the first-visit state


def test_cancelling_in_the_chat_tab_keeps_the_conversation(isolated_env):
    app, _ = rich_app(isolated_env)
    chat_tab_button(app, "New conversation").click().run()
    chat_tab_button(app, "Cancel").click().run()
    assert "How is VTI doing?" in [m.value for m in app.markdown] and not app.tabs[0].warning[1:]


def test_the_app_finds_the_project_when_started_from_another_folder(isolated_env):
    """`streamlit run` puts the script's folder on the path, not the project root."""
    import sys

    root = str(Path(APP).parents[2])
    saved = list(sys.path)
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != Path(root)]
    try:
        for name, value in KEYS.items():
            isolated_env.setenv(name, value)
        app = run_app()
        assert not app.exception and root in sys.path
    finally:
        sys.path[:] = saved


def test_a_stale_index_is_logged_with_how_to_rebuild_it(isolated_env, caplog):
    import logging

    for name, value in KEYS.items():
        isolated_env.setenv(name, value)
    isolated_env.setattr(rag_index, "is_stale", lambda knowledge: True)
    with caplog.at_level(logging.WARNING, logger="src.web_app.app"):
        app = run_app()
    assert not app.exception and "index_stale" in caplog.text and "python -m src.rag.build_index" in caplog.text


def test_the_chat_tab_explains_when_the_services_are_not_available():
    app = AppTest.from_string("from src.web_app.tabs import chat\nchat.render(None, None)\n").run()
    assert "The chat isn't available right now. Please check the configuration message above." in [i.value for i in app.info]
