"""Story 7.4: the Goals tab."""

import asyncio
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.agents.goal_planning import GoalPlanningAgent, field_problems, validate
from src.core import config
from src.core.calculators import plan_goal
from src.core.models import AgentRequest, SessionProfile
from src.web_app import charts
from src.web_app.tabs import goals as tab
from src.workflow import factory

APP = str(Path(__file__).resolve().parents[2] / "src" / "web_app" / "app.py")
KEYS = {"OPENAI_API_KEY": "sk-test-openai-123456", "ALPHA_VANTAGE_API_KEY": "av-test-key-123456", "SERPAPI_API_KEY": "serp-test-key-123456"}
TODAY = date(2026, 10, 15)
RATES = {"conservative": 0.03, "moderate": 0.05, "aggressive": 0.07}


# --- per-field validation, shared with the agent (AC 4) ---------------------------------------------


def test_field_problems_name_the_field_each_message_belongs_to():
    assert field_problems(0, -5, 0, TODAY) == {
        "amount": "The target amount needs to be more than $0.",
        "savings": "Your current savings can't be negative. If you have nothing saved yet, use $0.",
        "time": "The target date needs to be in the future.",
    }
    assert field_problems(20000, 0, 48, TODAY) == {}
    assert field_problems(None, None, None, TODAY) == {}  # nothing entered yet: no complaints
    assert list(field_problems(5_000_000_000, 0, 800, TODAY)) == ["amount", "time"]  # 800 months is over the 60-year limit


def test_the_agents_list_of_messages_is_the_same_problems_in_the_same_order():
    assert validate(0, -5, 0, TODAY) == list(field_problems(0, -5, 0, TODAY).values())


# --- the projection chart (front-end spec §5) --------------------------------------------------------


def test_projection_chart_has_the_year_by_year_balance_and_a_dashed_goal_line():
    plan = plan_goal(20000, 3000, 48, 0.05)
    fig = charts.goal_projection(plan)
    line = fig.data[0]
    assert list(line.x) == [0, 1, 2, 3, 4] and list(line.y) == [balance for _, balance in plan.schedule]
    assert fig.layout.title.text == "Your path to $20,000"
    assert fig.layout.xaxis.title.text == "Years from now" and fig.layout.yaxis.title.text == "Balance ($)"
    goal = fig.layout.shapes[0]
    assert goal.y0 == goal.y1 == 20000 and goal.line.dash == "dash"
    assert "Goal: $20,000" in fig.layout.annotations[0].text


def test_a_goal_that_is_not_a_whole_number_of_years_ends_part_way_along_the_axis():
    assert list(charts.goal_projection(plan_goal(20000, 5000, 30, 0.05)).data[0].x) == [0, 1, 2, 2.5]


# --- the tab in the running app ----------------------------------------------------------------------


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(tab, "today", lambda: TODAY)
    monkeypatch.setattr(factory, "build_services", lambda settings: SimpleNamespace(workflow=SimpleNamespace(), agents={}, settings=None))
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def run_app():
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    return app


def goals(app):
    return app.tabs[3]


def set_risk(app, level):
    next(b for b in app.sidebar.selectbox if b.label == "Risk tolerance").select(level).run()


def fill(app, amount=None, when=None, savings=None):
    if amount is not None:
        goals(app).number_input(key="goal_amount").set_value(amount).run()
    if when is not None:
        goals(app).date_input(key="goal_date").set_value(when).run()
    if savings is not None:
        goals(app).number_input(key="goal_savings").set_value(savings).run()


def metrics(app):
    return {m.label: m.value for m in goals(app).metric}


def markdown(app):
    return [m.value for m in goals(app).markdown]


def planned(app, risk="Moderate", amount=20000.0, when=date(2030, 10, 15), savings=3000.0):
    set_risk(app, risk)
    fill(app, amount, when, savings)
    return app


# --- AC 1: the fields and the sidebar risk tolerance ---------------------------------------------------


def test_the_form_has_the_three_fields_and_starts_empty(env):
    app = run_app()
    assert not app.exception
    assert goals(app).number_input(key="goal_amount").label == "Target amount ($)" and goals(app).number_input(key="goal_amount").value is None
    assert goals(app).date_input(key="goal_date").label == "Target date" and goals(app).date_input(key="goal_date").value is None
    savings = goals(app).number_input(key="goal_savings")
    assert savings.label == "Already saved toward it ($)" and savings.value == 0.0  # it's fine if that's $0


def test_without_a_risk_tolerance_the_tab_says_to_set_it_and_shows_no_plan(env):
    app = run_app()
    fill(app, 20000.0, date(2030, 10, 15), 3000.0)
    assert tab.NEEDS_RISK in [i.value for i in goals(app).info] and not metrics(app) and not app.get("plotly_chart")
    assert "**Risk tolerance:** not set yet" in markdown(app)


def test_the_sidebar_risk_tolerance_is_shown_read_only(env):
    app = run_app()
    set_risk(app, "Aggressive")
    assert "**Risk tolerance:** Aggressive  \n:gray[Change it in the sidebar.]" in markdown(app)
    assert not [s for s in goals(app).selectbox]  # nothing to change here


def test_with_a_risk_tolerance_but_empty_fields_it_asks_for_them(env):
    app = run_app()
    set_risk(app, "Moderate")
    assert tab.NEEDS_FIELDS in [c.value for c in goals(app).caption] and not metrics(app)


# --- AC 2 and AC 3: the monthly saving, the chart, the assumed return, estimates and the disclaimer -----


def test_the_plan_shows_the_monthly_saving_the_assumed_return_and_the_estimate_line(env):
    app = planned(run_app())
    assert metrics(app) == {"Save each month": "$309.17", "Assumed return": "5% a year"}
    assert tab.ESTIMATE_LINE in [c.value for c in goals(app).caption]  # "This is an estimate, not a guarantee."


def test_the_projection_chart_and_the_disclaimer_are_shown(env):
    app = planned(run_app())
    charts_ = app.get("plotly_chart")
    assert len(charts_) == 1 and "Your path to $20,000" in charts_[0].proto.spec
    assert [w.value for w in goals(app).warning] == [config.load_settings(environ=KEYS).disclaimer.text]


def test_the_tab_uses_the_same_calculation_as_the_goal_planning_agent(env):
    app = planned(run_app(), "Aggressive")
    shown = float(metrics(app)["Save each month"].replace("$", "").replace(",", ""))

    class SilentLLM:
        async def structured(self, schema, system, user, history=None):
            from src.agents.base import LLMAnswer

            return LLMAnswer(answer="ok", response_type="advice")

    agent = GoalPlanningAgent(SilentLLM(), "d", RATES, today=lambda: TODAY)
    request = AgentRequest(message="plan", profile=SessionProfile(risk_tolerance="aggressive"),
                           payload={"goal": {"target_amount": 20000, "target_date": "2030-10-15", "current_savings": 3000}})
    plan = asyncio.run(agent.run(request)).data["plan"]
    assert shown == plan.required_monthly and metrics(app)["Assumed return"] == "7% a year"
    assert plan.schedule == plan_goal(20000, 3000, plan.months, 0.07).schedule


def test_each_risk_level_gives_its_own_assumed_return_and_amount(env):
    app = planned(run_app(), "Conservative")
    conservative = metrics(app)
    set_risk(app, "Aggressive")
    aggressive = metrics(app)
    assert conservative["Assumed return"] == "3% a year" and aggressive["Assumed return"] == "7% a year"
    assert float(aggressive["Save each month"][1:]) < float(conservative["Save each month"][1:])  # more growth, less to save


def test_totals_and_the_lower_returns_reminder_are_shown(env):
    app = planned(run_app())
    caption = next(c.value for c in goals(app).caption if c.value.startswith("Over "))
    plan = plan_goal(20000, 3000, 48, 0.05)
    assert f"${plan.total_contributions:,.2f}" in caption and f"${plan.growth:,.2f}" in caption
    assert f"If returns were 2 points lower, you'd need about ${plan.required_monthly_if_lower:,.2f} a month." in caption


def test_changing_the_amount_updates_the_plan_at_once(env):
    app = planned(run_app())
    before = metrics(app)["Save each month"]
    fill(app, amount=40000.0)
    assert metrics(app)["Save each month"] != before and "Your path to $40,000" in app.get("plotly_chart")[0].proto.spec


# --- AC 4: invalid inputs get a clear message next to the field -------------------------------------------


@pytest.mark.parametrize(
    "amount, when, savings, message",
    [
        (0.0, date(2030, 10, 15), 0.0, "The target amount needs to be more than $0."),
        (-500.0, date(2030, 10, 15), 0.0, "The target amount needs to be more than $0."),
        (20000.0, date(2030, 10, 15), -100.0, "Your current savings can't be negative. If you have nothing saved yet, use $0."),
        (20000.0, date(2025, 1, 1), 0.0, "The target date needs to be in the future."),
        (20000.0, TODAY, 0.0, "The target date needs to be in the future."),
        (20000.0, date(2090, 1, 1), 0.0, "That's further out than I can plan. Please choose a goal within 60 years."),
    ],
)
def test_invalid_inputs_show_a_red_message_and_no_plan(env, amount, when, savings, message):
    app = planned(run_app(), "Moderate", amount, when, savings)
    assert not app.exception and f":red[{message}]" in markdown(app)
    assert not metrics(app) and not app.get("plotly_chart")


def test_each_message_sits_under_its_own_field(env):
    app = planned(run_app(), "Moderate", 0.0, date(2025, 1, 1), -1.0)
    shown = [m for m in markdown(app) if m.startswith(":red[")]
    assert shown == [
        ":red[The target amount needs to be more than $0.]",
        ":red[The target date needs to be in the future.]",
        ":red[Your current savings can't be negative. If you have nothing saved yet, use $0.]",
    ]  # amount, then date, then savings: the order of the fields on the page


def test_fixing_the_input_removes_the_message_and_shows_the_plan(env):
    app = planned(run_app(), "Moderate", 20000.0, date(2025, 1, 1), 3000.0)
    assert not metrics(app)
    fill(app, when=date(2030, 10, 15))
    assert metrics(app)["Save each month"] == "$309.17" and not [m for m in markdown(app) if m.startswith(":red[")]


# --- states from the spec -------------------------------------------------------------------------------------


def test_savings_that_already_meet_the_goal(env):
    app = planned(run_app(), "Moderate", 10000.0, date(2028, 10, 15), 12000.0)
    assert [s.value for s in goals(app).success] == [tab.ALREADY_REACHED] and metrics(app)["Save each month"] == "$0.00"
    assert len(app.get("plotly_chart")) == 1  # the chart still shows the savings growing


def test_savings_that_will_grow_to_the_goal_without_more_saving(env):
    app = planned(run_app(), "Aggressive", 10000.0, date(2036, 10, 15), 9000.0)
    assert tab.GROWTH_ALONE in [i.value for i in goals(app).info] and metrics(app)["Save each month"] == "$0.00"


def test_the_tab_needs_no_ai_service(env):
    app = planned(run_app())  # the fake services have no agents or workflow, yet the plan appears
    assert metrics(app)["Save each month"] == "$309.17" and not app.exception


def test_a_retirement_length_goal_can_be_entered(env):
    """Streamlit's date picker allows only 10 years by default, which would rule out a 35-year goal."""
    app = planned(run_app(), "Moderate", 1_000_000.0, date(2061, 10, 15), 25000.0)
    assert not app.exception and metrics(app)["Save each month"].startswith("$")
    assert "Your path to $1,000,000" in app.get("plotly_chart")[0].proto.spec


def test_the_projection_chart_has_a_show_as_table_switch_with_the_same_data(env):
    app = planned(run_app())
    toggle = next(t for t in goals(app).toggle if t.key == "goal_projection_table")
    assert toggle.label == "Show as table" and not toggle.value and not goals(app).dataframe
    toggle.set_value(True).run()
    table = goals(app).dataframe[0].value
    plan = plan_goal(20000, 3000, 48, 0.05)
    assert list(table["Projected balance"]) == [f"${b:,.2f}" for _, b in plan.schedule] and set(table["Goal"]) == {"$20,000.00"}
