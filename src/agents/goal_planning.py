"""Goal Planning Agent (Story 4.1, FR4, FR14, architecture §11.3).

Gathers a target amount, a target date (or number of years) and current savings,
asking in the chat for whatever is missing. It needs the user's risk tolerance,
which BaseAgent asks for first when it isn't set (Story 5.5). The monthly saving
and the year-by-year projection are calculated in code; the LLM only explains
them. A plan is always advice, so it always carries the disclaimer (D-7).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

from pydantic import BaseModel, Field

from src.agents.base import BaseAgent, LLMAnswer
from src.core.calculators import (
    MAX_GOAL_AMOUNT,
    MAX_GOAL_YEARS,
    GoalPlan,
    months_until,
    plan_goal,
)
from src.core.models import AgentName, AgentRequest, AgentResponse
from src.utils.logging import get_logger, log_event

logger = get_logger(__name__)

NEEDS_DETAILS = "goal_details"
DEFAULT_RETURNS = {"conservative": 0.03, "moderate": 0.05, "aggressive": 0.07}
ESTIMATE_NOTE = "These figures are estimates, not guarantees: real returns vary from year to year and can be negative."

_MISSING = {
    "amount": "how much you want to save (the target amount)",
    "time": "when you need it by (a date, or a number of years)",
    "savings": "how much you've already saved toward it (it's fine if that's $0)",
}


class GoalExtraction(BaseModel):
    target_amount: float | None = Field(default=None, description="The amount to save, in US dollars. null if not given.")
    years: float | None = Field(default=None, description="How many years from now, e.g. 'in 4 years' = 4, 'in 18 months' = 1.5. null if the user gave a date or nothing.")
    target_date: str | None = Field(default=None, description="Only if the user named a specific date, month or year (YYYY-MM-DD; for just a year like 'by 2030' use December 31 of that year). null if they gave a number of years or nothing. Never use today's date as a placeholder.")
    current_savings: float | None = Field(default=None, description="What the user already has saved toward this goal, in dollars. 0 if they say they have nothing saved. null if not mentioned.")


@dataclass(frozen=True)
class GoalInput:
    target_amount: float
    current_savings: float
    months: int


def parse_date(text: str | None) -> date | None:
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


def field_problems(
    amount: float | None, current: float | None, months: int | None, today: date, years: float | None = None
) -> dict[str, str]:
    """Why a goal can't be planned, by field: "amount", "savings" and "time". Empty if it can.

    Details that are still missing (None) are skipped, so a problem with what the user has
    already said is reported at once instead of after they've answered every question. The
    Goals tab shows each message next to its own field (Story 7.4).
    """
    problems: dict[str, str] = {}
    if amount is not None and amount <= 0:
        problems["amount"] = "The target amount needs to be more than $0."
    elif amount is not None and amount > MAX_GOAL_AMOUNT:
        problems["amount"] = f"The target amount is too large for me to plan (the limit is ${MAX_GOAL_AMOUNT:,})."
    if current is not None and current < 0:
        problems["savings"] = "Your current savings can't be negative. If you have nothing saved yet, use $0."
    if years is not None and years <= 0:
        problems["time"] = "The number of years needs to be more than 0."
    elif months is not None and months < 1:
        problems["time"] = "The target date needs to be in the future."
    elif months is not None and months > MAX_GOAL_YEARS * 12:
        problems["time"] = f"That's further out than I can plan. Please choose a goal within {MAX_GOAL_YEARS} years."
    return problems


def validate(
    amount: float | None, current: float | None, months: int | None, today: date, years: float | None = None
) -> list[str]:
    """The same problems as a list of messages, for the chat."""
    return list(field_problems(amount, current, months, today, years).values())


def explain_problems(problems: list[str]) -> str:
    return "I couldn't make a plan from those numbers:\n" + "\n".join(f"- {p}" for p in problems)


def ask_for_details(missing: list[str]) -> str:
    wanted = [_MISSING[key] for key in missing]
    listed = wanted[0] if len(wanted) == 1 else ", ".join(wanted[:-1]) + f", and {wanted[-1]}"
    return (
        f"To work out a plan, I need {listed}. "
        'For example: "I want $20,000 in 4 years, and I have $3,000 saved so far."'
    )


def summarize(plan: GoalPlan, risk: str, today: date, goal_note: str | None) -> str:
    """The facts the LLM may use. It must not compute or invent any other numbers."""
    end = today + timedelta(days=round(plan.months * 30.4375))
    years, months = divmod(plan.months, 12)
    length = ", ".join(part for part in (f"{years} year{'s' if years != 1 else ''}" if years else "",
                                          f"{months} month{'s' if months != 1 else ''}" if months else "") if part)
    lines = [
        f"Goal: ${plan.target_amount:,.2f} by about {end:%B %Y} ({length} from now)",
        f"Already saved: ${plan.current_savings:,.2f}",
        f"Risk tolerance: {risk}, which assumes about {plan.annual_return * 100:g}% growth per year",
    ]
    if goal_note:
        lines.append(f"What it's for: {goal_note}")
    if plan.already_reached:
        lines.append("Status: the money already saved meets or beats the goal, so no monthly saving is needed.")
        lines.append(f"If left invested at the assumed return, ${plan.current_savings:,.2f} could grow to about ${plan.end_balance:,.2f}.")
    elif plan.growth_alone_reaches:
        lines.append("Status: the money already saved, left to grow at the assumed return, should reach the goal without adding more.")
        lines.append(f"Projected balance at the end: about ${plan.end_balance:,.2f}.")
    else:
        lines.append(f"Required saving: ${plan.required_monthly:,.2f} per month")
        lines.append(f"Over the whole period you'd put in about ${plan.total_contributions:,.2f}; growth would add about ${plan.growth:,.2f}.")
        lines.append(f"If returns turned out 2 points lower, the monthly saving would be about ${plan.required_monthly_if_lower:,.2f}.")
    return "\n".join(lines)


class GoalPlanningAgent(BaseAgent):
    name = AgentName.GOAL_PLANNING
    requires_risk_tolerance = True
    instructions = """Your job: explain the savings plan below in plain language.
Use ONLY the numbers given; never calculate new ones or make up figures.
Lead with the monthly amount (or the status, if no saving is needed). Then briefly explain how long it takes and how much is saved versus earned through growth.
Say what the assumed growth rate means in one plain sentence (we assume savings grow at a steady rate, but real returns vary).
If a "2 points lower" figure is given, mention it as a reminder that results are estimates.
Encourage the user, but don't recommend specific investments or promise results.
The exact assumption and an 'estimates, not guarantees' note are added automatically after your answer, so don't repeat them. Keep it to a few short sentences."""

    def __init__(
        self, llm, disclaimer_text: str, annual_returns: dict[str, float] | None = None,
        today: Callable[[], date] = date.today,
    ):
        super().__init__(llm, disclaimer_text)
        self.annual_returns = annual_returns or DEFAULT_RETURNS
        self.today = today

    async def _run(self, request: AgentRequest) -> AgentResponse:
        today = self.today()
        goal = (request.payload or {}).get("goal")
        details = goal if goal is not None else await self._extract(request, today)
        amount, current = details.get("target_amount"), details.get("current_savings")
        years, target_date = details.get("years"), parse_date(details.get("target_date"))
        if years is not None and target_date is not None and target_date <= today:
            target_date = None  # models sometimes put today's date here as a placeholder; trust the years

        months = months_until(target_date, today) if target_date else (round(years * 12) if years is not None else None)
        problems = validate(amount, current, months, today, years=None if target_date else years)
        if problems:
            return AgentResponse(agent=self.name, answer=explain_problems(problems), data={"problems": problems})

        missing = [key for key, value in (("amount", amount), ("time", months), ("savings", current)) if value is None]
        if missing:
            return AgentResponse(agent=self.name, answer=ask_for_details(missing), needs_input=NEEDS_DETAILS)

        risk = request.profile.risk_tolerance
        rate = self.annual_returns[risk]
        plan = plan_goal(amount, current, months, rate)
        log_event(logger, "goal_plan", months=months, risk=risk, monthly=plan.required_monthly)

        reply = await self.llm.structured(
            LLMAnswer,
            f"{self.system_prompt(request.profile)}\n\nSavings plan:\n{summarize(plan, risk, today, request.profile.goal_note)}",
            request.message or "Explain my savings plan.",
            request.history,
        )
        footer = f"_Assumed return: {rate * 100:g}% a year ({risk.capitalize()}). {ESTIMATE_NOTE}_"
        return AgentResponse(
            agent=self.name,
            answer=f"{reply.answer.strip()}\n\n{footer}",
            response_type="advice",  # every plan is advice (architecture §7.4), whatever the LLM says
            data={"plan": plan, "schedule": plan.schedule, "assumed_return": rate, "risk_tolerance": risk},
        )

    async def _extract(self, request: AgentRequest, today: date) -> dict:
        system = (
            "Extract the savings goal details the user has given, using the whole conversation. "
            f"Today's date is {today.isoformat()}. "
            "Never guess: leave a field null when the user hasn't said it. "
            "Amounts are US dollars ('$20k' = 20000)."
        )
        found = await self.llm.structured(GoalExtraction, system, request.message, request.history)
        return found.model_dump()
