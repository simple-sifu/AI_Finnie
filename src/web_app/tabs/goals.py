"""Goals tab (Story 7.4): a savings-goal form that shows the monthly saving and a projection chart.

Layout follows front-end spec §4.4. It uses the same calculations and the same validation as the
Goal Planning Agent (Story 4.1), so the tab and the chat always agree. No AI call is needed, so the
plan updates as soon as a field changes.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import streamlit as st

from src.agents.goal_planning import DEFAULT_RETURNS, field_problems
from src.core.calculators import GoalPlan, months_until, plan_goal
from src.web_app import charts, components
from src.workflow.conversation import get_conversation

NEEDS_RISK = "Set your risk tolerance in the sidebar to see your plan."
NEEDS_FIELDS = "Enter a target amount and a target date to see your plan."
ESTIMATE_LINE = "This is an estimate, not a guarantee."
ALREADY_REACHED = "Your current savings already meet this goal."
GROWTH_ALONE = "Your current savings, left to grow at the assumed return, should reach this goal without adding more."

today: Callable[[], date] = date.today  # replaced in tests


def _problem(message: str | None) -> None:
    """A message right under its field, in red."""
    if message:
        st.markdown(f":red[{message}]")


def render_form() -> tuple[float | None, date | None, float | None, dict]:
    amount = st.number_input("Target amount ($)", value=None, step=100.0, format="%.2f", placeholder="e.g. 20000", key="goal_amount")
    amount_problem_slot = st.container()
    # Streamlit only allows dates within 10 years by default, which rules out retirement-length goals.
    # Past dates stay selectable so the "needs to be in the future" message can be shown.
    now = today()
    target_date = st.date_input(
        "Target date", value=None, format="MM/DD/YYYY", key="goal_date",
        min_value=date(now.year - 10, 1, 1), max_value=date(now.year + 100, 12, 31),
    )
    date_problem_slot = st.container()
    savings = st.number_input("Already saved toward it ($)", value=0.0, step=100.0, format="%.2f", key="goal_savings",
                              help="It's fine if that's $0.")
    savings_problem_slot = st.container()
    return amount, target_date, savings, {"amount": amount_problem_slot, "time": date_problem_slot, "savings": savings_problem_slot}


def render_risk(risk: str | None) -> None:
    if risk:
        st.markdown(f"**Risk tolerance:** {risk.capitalize()}  \n:gray[Change it in the sidebar.]")
    else:
        st.markdown("**Risk tolerance:** not set yet")


def render_plan(plan: GoalPlan, risk: str, disclaimer: str) -> None:
    saving, assumed = st.columns(2)
    saving.metric("Save each month", f"${plan.required_monthly:,.2f}")
    assumed.metric("Assumed return", f"{plan.annual_return * 100:g}% a year", help=f"Used for the {risk.capitalize()} risk level. Real returns vary.")
    st.caption(ESTIMATE_LINE)

    if plan.already_reached:
        st.success(ALREADY_REACHED)
    elif plan.growth_alone_reaches:
        st.info(GROWTH_ALONE)
    else:
        st.caption(
            f"Over {plan.months / 12:.1f} years you'd put in about ${plan.total_contributions:,.2f}, "
            f"and growth would add about ${plan.growth:,.2f}. "
            f"If returns were 2 points lower, you'd need about ${plan.required_monthly_if_lower:,.2f} a month."
        )
    figure = charts.goal_projection(plan)
    if figure is not None:
        st.plotly_chart(figure, width="stretch", key="goal_projection")
    components.disclaimer_callout(disclaimer)


def render(annual_returns: dict[str, float] | None = None, disclaimer: str = "") -> None:
    st.subheader("Goals")
    annual_returns = annual_returns or DEFAULT_RETURNS
    risk = get_conversation(st.session_state).profile.risk_tolerance

    amount, target_date, savings, slots = render_form()
    now = today()
    months = months_until(target_date, now) if target_date else None
    problems = field_problems(amount, savings, months, now)
    for field, slot in slots.items():
        with slot:
            _problem(problems.get(field))
    render_risk(risk)

    if risk is None:
        st.info(NEEDS_RISK)
    elif problems:
        return  # each problem is already shown next to its field
    elif amount is None or target_date is None:
        st.caption(NEEDS_FIELDS)
    else:
        render_plan(plan_goal(amount, savings, months, annual_returns[risk]), risk, disclaimer)
