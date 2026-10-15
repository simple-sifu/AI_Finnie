"""Portfolio metrics, calculated in code (Story 3.3, architecture §11.1).

The LLM never does arithmetic; it only explains these results.

- Only holdings with a price count toward totals (D-41).
- Weighted expense ratio: weights of holdings with a known ratio, re-normalized;
  individual stocks count as 0% (no fund fee); funds with an unknown ratio are
  left out and the covered share of the portfolio is reported.
- Diversification score: each fund counts as 10 equal positions, each stock as
  1; N_eff = 1 / sum(p^2); score = round(100 * (1 - 1 / N_eff)).
- Risk: asset-type weights (cash 1, bond fund 2, balanced fund 3, stock fund 4,
  individual stock 5), weighted by value; below 2.5 Low, up to 3.75 Moderate,
  above that High. Any single stock over 20% is flagged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

FUND_POSITIONS = 10
RISK_WEIGHTS = {"cash": 1, "bond_fund": 2, "balanced_fund": 3, "stock_fund": 4, "individual_stock": 5}
UNKNOWN_FUND_RISK = 4  # a fund of unknown type is treated like a stock fund (the cautious choice)
CONCENTRATION_LIMIT = 0.20
TOLERANCE_LEVEL = {"conservative": "Low", "moderate": "Moderate", "aggressive": "High"}
ASSET_TYPE_NAMES = {
    "cash": "Cash & money market",
    "bond_fund": "Bond funds",
    "balanced_fund": "Balanced funds",
    "stock_fund": "Stock funds",
    "individual_stock": "Individual stocks",
    None: "Funds (type unknown)",
}


@dataclass(frozen=True)
class Position:
    """One holding, ready for the math."""

    ticker: str
    shares: float
    price: float | None  # None when no live, cached or sample price exists
    asset_type: str | None  # None for a fund whose type is unknown
    expense_ratio: float | None  # percent; None if unknown; stocks have None and is_stock=True

    @property
    def is_stock(self) -> bool:
        return self.asset_type == "individual_stock"

    @property
    def value(self) -> float | None:
        return None if self.price is None else self.shares * self.price


@dataclass(frozen=True)
class PortfolioMetrics:
    total_value: float
    weights: dict[str, float]  # ticker -> share of priced total (0-1)
    allocation_by_type: dict[str, float]  # asset type name -> share (0-1)
    weighted_expense_ratio: float | None  # percent
    expense_ratio_coverage: float  # share of the portfolio the ratio is based on (0-1)
    diversification_score: int
    diversification_label: str
    risk_score: float
    risk_level: str
    concentrated: list[str] = field(default_factory=list)  # stocks over 20%
    unpriced: list[str] = field(default_factory=list)  # left out of totals (D-41)


def diversification_score(weights: dict[str, float], is_fund: dict[str, bool]) -> int:
    squares = 0.0
    for ticker, weight in weights.items():
        if is_fund[ticker]:
            squares += FUND_POSITIONS * (weight / FUND_POSITIONS) ** 2
        else:
            squares += weight**2
    if squares == 0:
        return 0
    return round(100 * (1 - squares))  # 1 / N_eff is exactly sum(p^2)


def diversification_label(score: int) -> str:
    # Thresholds raised by the PM in Story 3.3 so that a portfolio split between two
    # stocks (score ~50) reads as Low: below 60 Low, 60-84 Medium, 85 and up High.
    return "Low" if score < 60 else "Medium" if score < 85 else "High"


def risk_level(score: float) -> str:
    return "Low" if score < 2.5 else "Moderate" if score <= 3.75 else "High"


def risk_mismatch(level: str, tolerance: str | None) -> str | None:
    """A plain note when the portfolio's risk differs from the user's stated tolerance."""
    if tolerance is None or TOLERANCE_LEVEL[tolerance] == level:
        return None
    return (
        f"Your portfolio's risk level is {level}, but you set your risk tolerance to "
        f"{tolerance.capitalize()} (which usually matches a {TOLERANCE_LEVEL[tolerance]} risk level)."
    )


def calculate(positions: list[Position]) -> PortfolioMetrics:
    priced = [p for p in positions if p.value is not None and p.value > 0]
    unpriced = [p.ticker for p in positions if p.value is None]
    total = sum(p.value for p in priced)
    if total <= 0:
        return PortfolioMetrics(0.0, {}, {}, None, 0.0, 0, "Low", 0.0, "Low", [], unpriced)

    weights = {p.ticker: p.value / total for p in priced}

    allocation: dict[str, float] = {}
    for p in priced:
        name = ASSET_TYPE_NAMES[p.asset_type]
        allocation[name] = allocation.get(name, 0.0) + weights[p.ticker]

    known = [p for p in priced if p.is_stock or p.expense_ratio is not None]
    coverage = sum(weights[p.ticker] for p in known)
    weighted_er = None
    if coverage > 0:
        weighted_er = sum(weights[p.ticker] * (0.0 if p.is_stock else p.expense_ratio) for p in known) / coverage

    score = diversification_score(weights, {p.ticker: not p.is_stock for p in priced})
    risk = sum(weights[p.ticker] * RISK_WEIGHTS.get(p.asset_type, UNKNOWN_FUND_RISK) for p in priced)
    concentrated = [p.ticker for p in priced if p.is_stock and weights[p.ticker] > CONCENTRATION_LIMIT]

    return PortfolioMetrics(
        total_value=total,
        weights=weights,
        allocation_by_type=dict(sorted(allocation.items(), key=lambda kv: -kv[1])),
        weighted_expense_ratio=weighted_er,
        expense_ratio_coverage=coverage,
        diversification_score=score,
        diversification_label=diversification_label(score),
        risk_score=round(risk, 2),
        risk_level=risk_level(risk),
        concentrated=concentrated,
        unpriced=unpriced,
    )
