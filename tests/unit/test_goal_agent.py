"""Story 4.1: Goal Planning Agent with a fake LLM and a fixed 'today'."""

import asyncio
from datetime import date

import pytest

from src.agents.base import RISK_QUESTION, LLMAnswer
from src.agents.goal_planning import ESTIMATE_NOTE, NEEDS_DETAILS, GoalExtraction, GoalPlanningAgent, validate
from src.core.calculators import GoalPlan, required_monthly_saving
from src.core.config import load_settings
from src.core.models import AgentName, AgentRequest, SessionProfile

TODAY = date(2026, 10, 15)
RETURNS = {"conservative": 0.03, "moderate": 0.05, "aggressive": 0.07}


class FakeLLM:
    """Returns a scripted extraction, then a scripted explanation; records every prompt."""

    def __init__(self, extraction=None, kind="education"):
        self.extraction, self.kind, self.calls = extraction or GoalExtraction(), kind, []

    async def structured(self, schema, system, user, history=None):
        self.calls.append({"schema": schema, "system": system, "user": user, "history": history})
        if schema is GoalExtraction:
            return self.extraction
        return LLMAnswer(answer="Save about this much each month.", response_type=self.kind)


def ask(message="Plan my savings", llm=None, risk="moderate", payload=None):
    agent = GoalPlanningAgent(llm or FakeLLM(), "Not personalized advice.", RETURNS, today=lambda: TODAY)
    request = AgentRequest(message=message, profile=SessionProfile(risk_tolerance=risk), payload=payload)
    return asyncio.run(agent.run(request))


def extraction(amount=20000, years=4, date_=None, savings=3000):
    return GoalExtraction(target_amount=amount, years=years, target_date=date_, current_savings=savings)


# --- AC 2: risk tolerance ---


def test_without_a_risk_tolerance_it_asks_for_one_first():
    llm = FakeLLM(extraction())
    response = ask(llm=llm, risk=None)
    assert response.answer == RISK_QUESTION and response.needs_input == "risk_tolerance" and llm.calls == []


# --- AC 1: gathering what's missing ---


@pytest.mark.parametrize(
    "found, expected",
    [
        (GoalExtraction(), ["how much you want to save", "when you need it by", "how much you've already saved"]),
        (GoalExtraction(years=4, current_savings=0), ["how much you want to save"]),
        (GoalExtraction(target_amount=20000, current_savings=0), ["when you need it by"]),
        (GoalExtraction(target_amount=20000, years=4), ["how much you've already saved"]),
    ],
)
def test_missing_details_are_asked_for_in_the_chat(found, expected):
    response = ask(llm=FakeLLM(found))
    assert response.needs_input == NEEDS_DETAILS and not response.error
    for phrase in expected:
        assert phrase in response.answer
    assert "For example" in response.answer
    assert len([c for c in ("how much you want", "when you need it", "already saved") if c in response.answer]) == len(expected)


def test_an_unreadable_date_counts_as_missing():
    response = ask(llm=FakeLLM(extraction(years=None, date_="next spring")))
    assert response.needs_input == NEEDS_DETAILS and "when you need it by" in response.answer


def test_the_extraction_sees_todays_date_the_history_and_is_told_not_to_guess():
    llm = FakeLLM(extraction())
    ask("I want $20,000 in 4 years", llm=llm)
    call = llm.calls[0]
    assert "2026-10-15" in call["system"] and "Never guess" in call["system"] and call["user"] == "I want $20,000 in 4 years"


def test_the_goals_tab_can_pass_the_details_without_any_extraction():
    llm = FakeLLM()
    goal = {"target_amount": 20000, "years": 4, "current_savings": 3000}
    response = ask(llm=llm, payload={"goal": goal})
    assert [c["schema"] for c in llm.calls] == [LLMAnswer] and response.data["plan"].months == 48


# --- AC 3 and AC 4: the plan is calculated in code ---


@pytest.mark.parametrize("risk, rate", [("conservative", 0.03), ("moderate", 0.05), ("aggressive", 0.07)])
def test_each_risk_level_uses_its_own_assumed_return(risk, rate):
    response = ask(llm=FakeLLM(extraction()), risk=risk)
    plan = response.data["plan"]
    assert isinstance(plan, GoalPlan) and plan.annual_return == rate and response.data["assumed_return"] == rate
    assert plan.required_monthly == required_monthly_saving(20000, 3000, 48, rate)


def test_the_numbers_go_to_the_llm_which_only_explains_them():
    llm = FakeLLM(extraction())
    response = ask(llm=llm)
    system = llm.calls[-1]["system"]
    monthly = response.data["plan"].required_monthly
    assert f"Required saving: ${monthly:,.2f} per month" in system
    assert "Goal: $20,000.00 by about October 2030 (4 years from now)" in system and "Already saved: $3,000.00" in system
    assert "assumes about 5% growth per year" in system and "2 points lower" in system
    assert "Use ONLY the numbers given" in system


def test_a_target_date_is_turned_into_months():
    response = ask(llm=FakeLLM(extraction(years=None, date_="2028-10-15")))
    assert response.data["plan"].months == 24


def test_the_schedule_feeds_the_projection_chart():
    response = ask(llm=FakeLLM(extraction()))
    schedule = response.data["schedule"]
    assert [m for m, _ in schedule] == [0, 12, 24, 36, 48] and schedule[0][1] == 3000
    assert schedule[-1][1] >= 20000


# --- AC 5: stating the assumption, and the disclaimer ---


@pytest.mark.parametrize("kind", ["education", "advice", "uncertain"])
def test_every_plan_is_advice_with_the_disclaimer_whatever_the_llm_says(kind):
    response = ask(llm=FakeLLM(extraction(), kind=kind))
    assert response.response_type == "advice" and response.disclaimer == "Not personalized advice."


def test_the_assumed_return_and_the_estimate_note_are_always_in_the_answer():
    response = ask(llm=FakeLLM(extraction()), risk="aggressive")
    assert response.answer.startswith("Save about this much each month.")
    assert "Assumed return: 7% a year (Aggressive)" in response.answer and ESTIMATE_NOTE in response.answer


# --- AC 6: impossible inputs get a clear explanation, not an error ---


@pytest.mark.parametrize(
    "found, problem",
    [
        (extraction(amount=0), "target amount needs to be more than $0"),
        (extraction(amount=-500), "target amount needs to be more than $0"),
        (extraction(amount=5_000_000_000), "too large for me to plan"),
        (extraction(savings=-100), "current savings can't be negative"),
        (extraction(years=None, date_="2025-01-01"), "target date needs to be in the future"),
        (extraction(years=None, date_="2026-10-15"), "target date needs to be in the future"),
        (extraction(years=0), "number of years needs to be more than 0"),
        (extraction(years=-2), "number of years needs to be more than 0"),
        (extraction(years=80), "further out than I can plan"),
    ],
)
def test_impossible_inputs_are_explained(found, problem):
    llm = FakeLLM(found)
    response = ask(llm=llm)
    assert problem in response.answer and response.answer.startswith("I couldn't make a plan from those numbers:")
    assert not response.error and response.data["problems"] and [c["schema"] for c in llm.calls] == [GoalExtraction]


def test_every_problem_is_listed_at_once():
    problems = validate(-1, -5, 0, TODAY)
    assert len(problems) == 3


def test_savings_that_already_meet_the_goal_are_celebrated_not_rejected():
    llm = FakeLLM(extraction(amount=10000, savings=12000))
    response = ask(llm=llm)
    plan = response.data["plan"]
    assert plan.already_reached and plan.required_monthly == 0 and not response.error
    assert "already saved meets or beats the goal" in llm.calls[-1]["system"]


def test_savings_that_will_grow_to_the_goal_are_explained():
    llm = FakeLLM(extraction(amount=10000, years=10, savings=9000))
    response = ask(llm=llm, risk="aggressive")
    assert response.data["plan"].growth_alone_reaches and "without adding more" in llm.calls[-1]["system"]


# --- wiring ---


def test_default_returns_match_the_configuration(tmp_path):
    keys = {"OPENAI_API_KEY": "sk-x-123456", "ALPHA_VANTAGE_API_KEY": "a", "SERPAPI_API_KEY": "s"}
    configured = load_settings(config_path=tmp_path / "none.yaml", environ=keys).goals.annual_return
    assert configured == {"conservative": 0.03, "moderate": 0.05, "aggressive": 0.07}
    from src.agents.goal_planning import DEFAULT_RETURNS

    assert DEFAULT_RETURNS == configured


def test_it_is_registered_in_the_workflow(tmp_path, monkeypatch):
    from src.workflow import factory

    monkeypatch.setattr(factory, "create_retriever", lambda settings: None)  # skip loading the embedding model
    keys = {"OPENAI_API_KEY": "sk-x-123456", "ALPHA_VANTAGE_API_KEY": "a", "SERPAPI_API_KEY": "s"}
    services = factory.build_services(load_settings(config_path=tmp_path / "none.yaml", environ=keys), cache_dir=tmp_path)
    agent = services.agents[AgentName.GOAL_PLANNING]
    assert isinstance(agent, GoalPlanningAgent) and agent.annual_returns == RETURNS and agent.requires_risk_tolerance


# --- found in the live test: models put today's date in target_date even when the user said "in 4 years" ---


def test_todays_date_as_a_placeholder_is_ignored_when_years_are_given():
    response = ask(llm=FakeLLM(extraction(years=4, date_="2026-10-15")))
    assert response.data["plan"].months == 48 and "problems" not in response.data


def test_a_real_future_date_wins_over_years():
    response = ask(llm=FakeLLM(extraction(years=4, date_="2028-10-15")))
    assert response.data["plan"].months == 24


def test_a_problem_with_what_was_said_is_reported_before_asking_for_the_rest():
    response = ask(llm=FakeLLM(GoalExtraction(target_amount=5000, target_date="2020-12-31")))  # savings still missing
    assert "target date needs to be in the future" in response.answer and response.needs_input is None


def test_validation_skips_details_that_are_still_missing():
    assert validate(None, None, None, TODAY) == []
    assert validate(None, -5, None, TODAY) == ["Your current savings can't be negative. If you have nothing saved yet, use $0."]
