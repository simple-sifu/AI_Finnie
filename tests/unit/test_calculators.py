"""Story 3.3: portfolio formulas (architecture §11.1), checked by hand."""

import pytest

from src.core.calculators import Position, calculate, diversification_label, risk_level, risk_mismatch


def stock(t, value):
    return Position(t, 1, value, "individual_stock", None)


def fund(t, value, kind="stock_fund", er=0.03):
    return Position(t, 1, value, kind, er)


@pytest.mark.parametrize(
    "positions, score",
    [
        ([stock("A", 100)], 0),
        ([stock(t, 100) for t in "ABCDE"], 80),
        ([fund("F", 100)], 90),
        ([fund(t, 100) for t in "FGH"], 97),
    ],
)
def test_diversification_examples_from_the_architecture(positions, score):
    assert calculate(positions).diversification_score == score


def test_mixed_portfolio_metrics():
    # 60% stock fund (0.03%), 25% bond fund (0.05%), 15% one stock
    m = calculate([fund("VTI", 600), fund("BND", 250, "bond_fund", 0.05), stock("AAPL", 150)])
    assert m.total_value == 1000
    assert m.weights == pytest.approx({"VTI": 0.6, "BND": 0.25, "AAPL": 0.15})
    assert m.allocation_by_type == pytest.approx({"Stock funds": 0.6, "Bond funds": 0.25, "Individual stocks": 0.15})
    assert m.weighted_expense_ratio == pytest.approx(0.6 * 0.03 + 0.25 * 0.05 + 0)  # 0.0305%
    assert m.expense_ratio_coverage == pytest.approx(1.0)
    # 1/N_eff = 10*(0.06^2) + 10*(0.025^2) + 0.15^2 = 0.036 + 0.00625 + 0.0225 = 0.06475
    assert m.diversification_score == round(100 * (1 - 0.06475)) == 94
    # risk = 0.6*4 + 0.25*2 + 0.15*5 = 3.65
    assert m.risk_score == 3.65 and m.risk_level == "Moderate"
    assert m.concentrated == [] and m.unpriced == []


def test_fund_with_unknown_expense_ratio_is_left_out_and_coverage_reported():
    m = calculate([fund("VTI", 500, er=0.04), fund("VTSAX", 500, er=None)])
    assert m.weighted_expense_ratio == pytest.approx(0.04)
    assert m.expense_ratio_coverage == pytest.approx(0.5)


def test_unknown_fund_type_counts_as_a_stock_fund_for_risk():
    assert calculate([Position("FXAIX", 1, 100, None, 0.015)]).risk_score == 4


def test_unpriced_holdings_are_left_out_of_totals():
    m = calculate([fund("VTI", 300), Position("XYZ", 10, None, "individual_stock", None)])
    assert m.total_value == 300 and m.unpriced == ["XYZ"] and m.weights == {"VTI": 1.0}


def test_single_stock_over_20_percent_is_flagged():
    m = calculate([stock("TSLA", 300), fund("VOO", 700)])
    assert m.concentrated == ["TSLA"]
    assert calculate([stock("TSLA", 200), fund("VOO", 800)]).concentrated == []  # exactly 20% is fine


def test_nothing_priced():
    m = calculate([Position("XYZ", 1, None, "individual_stock", None)])
    assert m.total_value == 0 and m.unpriced == ["XYZ"] and m.weighted_expense_ratio is None


@pytest.mark.parametrize(
    "score, label",
    [(0, "Low"), (53, "Low"), (59, "Low"), (60, "Medium"), (80, "Medium"), (84, "Medium"), (85, "High"), (90, "High")],
)
def test_diversification_labels(score, label):
    assert diversification_label(score) == label


@pytest.mark.parametrize("score, level", [(1.0, "Low"), (2.49, "Low"), (2.5, "Moderate"), (3.75, "Moderate"), (3.76, "High")])
def test_risk_levels(score, level):
    assert risk_level(score) == level


def test_risk_mismatch():
    assert risk_mismatch("High", None) is None
    assert risk_mismatch("Moderate", "moderate") is None
    note = risk_mismatch("High", "conservative")
    assert "risk level is High" in note and "Conservative" in note


# --- Story 3.4: market trends ---


def test_price_changes_over_1_week_1_month_3_months():
    from src.core.calculators import price_changes

    closes = [100.0] * 30 + [110.0] * 33 + [120.0] * 4 + [125.0]  # 68 closes, last is today
    changes = price_changes(closes)
    assert changes["1 week"] == round((125 / 110 - 1) * 100, 2)  # 5 trading days ago
    assert changes["1 month"] == round((125 / 110 - 1) * 100, 2)  # 21 trading days ago
    assert changes["3 months"] == 25.0  # 63 trading days ago: 100 -> 125


def test_price_changes_with_short_history():
    from src.core.calculators import price_changes

    assert price_changes([100.0, 101.0]) == {"1 week": None, "1 month": None, "3 months": None}
    assert price_changes([100.0] * 10 + [90.0])["1 week"] == -10.0


# --- Story 4.1: goal planning, checked against known values and an independent simulation ---

from datetime import date  # noqa: E402

from src.core.calculators import (  # noqa: E402
    balance_after,
    monthly_rate,
    months_until,
    plan_goal,
    required_monthly_saving,
)


def simulate(current, monthly, months, annual_return):
    """Month by month, the slow way: grow, then add the deposit at the end of the month."""
    r = (1 + annual_return) ** (1 / 12) - 1
    balance = current
    for _ in range(months):
        balance = balance * (1 + r) + monthly
    return balance


def test_no_growth_is_plain_division():
    assert required_monthly_saving(12000, 0, 12, 0.0) == 1000.00
    assert required_monthly_saving(12000, 3000, 12, 0.0) == 750.00


def test_known_value_ten_thousand_in_ten_years_at_six_percent():
    # (1.06)^(1/12) - 1 = 0.0048675506; PMT = 10000 * r / (1.06^10 - 1) = 61.5471... -> 61.55
    assert monthly_rate(0.06) == pytest.approx(0.0048675506, abs=1e-10)
    assert required_monthly_saving(10000, 0, 120, 0.06) == 61.55


@pytest.mark.parametrize(
    "target, current, months, rate",
    [(10000, 0, 120, 0.06), (20000, 5000, 48, 0.05), (1_000_000, 25000, 360, 0.07), (5000, 0, 6, 0.03), (50000, 1000, 1, 0.05)],
)
def test_saving_the_required_amount_really_reaches_the_target(target, current, months, rate):
    monthly = required_monthly_saving(target, current, months, rate)
    final = simulate(current, monthly, months, rate)
    assert target <= final < target + monthly + 0.01  # reached, and by no more than one cent of rounding per deposit
    assert balance_after(current, monthly, months, rate) == pytest.approx(final)


def test_zero_when_current_savings_alone_reach_the_goal():
    assert required_monthly_saving(10000, 10000, 24, 0.05) == 0.0  # already there
    assert required_monthly_saving(10000, 9000, 120, 0.07) == 0.0  # 9000 * 1.07^10 = 17,704


def test_plan_fields_for_a_typical_goal():
    plan = plan_goal(20000, 5000, 48, 0.05)
    assert plan.required_monthly == required_monthly_saving(20000, 5000, 48, 0.05)
    assert plan.total_contributions == pytest.approx(plan.required_monthly * 48, abs=0.01)
    assert plan.end_balance >= 20000 and plan.end_balance == pytest.approx(simulate(5000, plan.required_monthly, 48, 0.05), abs=0.01)
    assert plan.growth == pytest.approx(plan.end_balance - 5000 - plan.total_contributions, abs=0.01)
    assert not plan.already_reached and not plan.growth_alone_reaches


def test_schedule_has_a_point_at_month_zero_each_year_end_and_the_final_month():
    plan = plan_goal(20000, 5000, 30, 0.05)  # 2.5 years
    assert [m for m, _ in plan.schedule] == [0, 12, 24, 30]
    assert plan.schedule[0][1] == 5000
    balances = [b for _, b in plan.schedule]
    assert balances == sorted(balances) and balances[-1] == plan.end_balance
    assert [m for m, _ in plan_goal(12000, 0, 24, 0.0).schedule] == [0, 12, 24]  # exact years: no duplicate end point


def test_already_reached_and_growth_alone_statuses():
    reached = plan_goal(10000, 12000, 24, 0.05)
    assert reached.already_reached and reached.required_monthly == 0 and not reached.growth_alone_reaches
    on_track = plan_goal(10000, 9000, 120, 0.07)
    assert on_track.growth_alone_reaches and on_track.required_monthly == 0 and not on_track.already_reached
    assert on_track.end_balance == pytest.approx(9000 * 1.07**10, abs=0.01)


def test_lower_returns_need_a_higher_monthly_saving():
    plan = plan_goal(20000, 5000, 120, 0.05)
    assert plan.required_monthly_if_lower == required_monthly_saving(20000, 5000, 120, 0.03)
    assert plan.required_monthly_if_lower > plan.required_monthly
    assert plan_goal(20000, 0, 120, 0.01).required_monthly_if_lower == required_monthly_saving(20000, 0, 120, 0.0)  # never below 0%


@pytest.mark.parametrize(
    "target_date, months",
    [(date(2030, 10, 15), 48), (date(2026, 11, 15), 1), (date(2026, 10, 16), 1), (date(2026, 10, 15), 0), (date(2025, 1, 1), 0), (date(2027, 10, 15), 12)],
)
def test_months_until(target_date, months):
    assert months_until(target_date, date(2026, 10, 15)) == months
