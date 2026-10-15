"""Portfolio Analysis Agent (Story 3.3, FR2, FR13).

Flow: parse the uploaded CSV, price each holding through MarketData (cache,
limits and fallbacks apply), look up expense ratios and asset types, calculate
every metric in code, then ask the LLM only to explain the results. Any answer
with a recommendation is advice and gets the disclaimer (D-3, D-7).
"""

from __future__ import annotations

from typing import Protocol

from pydantic import Field

from src.agents.base import BaseAgent, LLMAnswer
from src.core.calculators import ASSET_TYPE_NAMES, Position, PortfolioMetrics, calculate, risk_mismatch
from src.core.freshness import DataLabel
from src.core.funds import ExpenseSource, lookup_expense_ratio
from src.core.holdings import ParseResult, parse_holdings
from src.core.market_data import MarketResult, Quote
from src.core.models import AgentName, AgentRequest, AgentResponse

UPLOAD_PROMPT = (
    "To analyze your portfolio, upload your holdings in the Portfolio tab: a CSV file with the "
    "columns ticker, shares and (optionally) expense_ratio."
)


class QuoteSource(Protocol):
    """Minimal market client interface for pricing uploaded holdings."""

    async def get_quote(self, ticker: str) -> MarketResult: ...


class PortfolioExplanation(LLMAnswer):
    """Structured portfolio narrative; flags whether the answer recommends a change."""

    includes_recommendation: bool = Field(
        description="True if the answer suggests any change or action for this portfolio."
    )


def _pct(share: float) -> str:
    return f"{share * 100:.1f}%"


def summarize(metrics: PortfolioMetrics, rows: list[dict], notes: list[str]) -> str:
    """The facts the LLM may use. It must not compute or invent any other numbers."""
    lines = [
        f"Total value: ${metrics.total_value:,.2f}",
        "Holdings (ticker, type, value, share of portfolio, expense ratio):",
    ]
    for row in rows:
        if row["value"] is None:
            continue
        er = "n/a (stock)" if row["asset_type"] == "individual_stock" else (
            f"{row['expense_ratio']:.2f}%" if row["expense_ratio"] is not None else "unknown")
        lines.append(f"- {row['ticker']}, {row['asset_type_name']}, ${row['value']:,.2f}, {_pct(row['weight'])}, {er}")
    lines.append("By type: " + ", ".join(f"{name} {_pct(share)}" for name, share in metrics.allocation_by_type.items()))
    if metrics.weighted_expense_ratio is not None:
        lines.append(
            f"Weighted average expense ratio: {metrics.weighted_expense_ratio:.3f}% "
            f"(based on {_pct(metrics.expense_ratio_coverage)} of the portfolio)"
        )
    lines.append(f"Diversification score: {metrics.diversification_score}/100 ({metrics.diversification_label})")
    lines.append(f"Risk level: {metrics.risk_level} (score {metrics.risk_score} on a 1-5 scale)")
    if metrics.concentrated:
        lines.append("Single stocks over 20% of the portfolio: " + ", ".join(metrics.concentrated))
    lines.extend(f"Note: {note}" for note in notes)
    return "\n".join(lines)


class PortfolioAgent(BaseAgent):
    """Parses holdings CSVs, computes metrics in code and explains the results."""

    name = AgentName.PORTFOLIO
    instructions = """Your job: explain the user's portfolio analysis below.
Use ONLY the numbers given; never calculate new ones or make up figures.
Cover: what they own, how diversified it is, its risk level, what they pay in fees, and anything flagged.
You may suggest general, conservative improvements, such as spreading money more widely or choosing lower-cost funds.
Keep it to a few short paragraphs."""

    def __init__(self, llm, disclaimer_text: str, market: QuoteSource, max_rows: int = 200, max_file_mb: float = 1.0):
        super().__init__(llm, disclaimer_text)
        self.market = market
        self.max_rows = max_rows
        self.max_file_mb = max_file_mb

    async def _run(self, request: AgentRequest) -> AgentResponse:
        upload = (request.payload or {}).get("csv")
        if upload is None:
            return AgentResponse(agent=self.name, answer=UPLOAD_PROMPT, needs_input="holdings")

        parsed: ParseResult = parse_holdings(upload, self.max_rows, self.max_file_mb)
        if not parsed.ok:
            answer = "I couldn't read your holdings file:\n" + "\n".join(f"- {p}" for p in parsed.problems)
            return AgentResponse(agent=self.name, answer=answer + "\n\nFix these and upload it again.",
                                 data={"problems": parsed.problems})

        positions, rows, labels, notes = await self._price(parsed)
        notes = parsed.notes + notes
        metrics = calculate(positions)
        mismatch = risk_mismatch(metrics.risk_level, request.profile.risk_tolerance)
        if mismatch:
            notes.append(mismatch)
        for row in rows:
            row["weight"] = metrics.weights.get(row["ticker"], 0.0)

        data = {"metrics": metrics, "holdings": rows, "notes": notes}
        if metrics.total_value <= 0:
            return AgentResponse(
                agent=self.name, labels=labels, data=data,
                answer="I couldn't get prices for any of your holdings right now, so I can't analyze them yet. "
                       "Please try again later.",
            )

        reply = await self.llm.structured(
            PortfolioExplanation,
            f"{self.system_prompt(request.profile)}\n\nPortfolio analysis:\n{summarize(metrics, rows, notes)}",
            request.message or "Explain my portfolio.",
            request.history,
        )
        kind = "advice" if reply.includes_recommendation else reply.response_type  # architecture §7.4
        return AgentResponse(agent=self.name, answer=reply.answer, response_type=kind, labels=labels, data=data)

    async def _price(self, parsed: ParseResult):
        positions, rows, notes = [], [], []
        labels: dict[str, DataLabel] = {}
        for holding in parsed.holdings:
            result = await self.market.get_quote(holding.ticker)
            price = result.value.price if isinstance(result.value, Quote) else None
            label = result.label()
            if label:
                labels.setdefault(label.text, label)
            if price is None:
                notes.append(f"{holding.ticker}: price unavailable, so it's left out of the totals.")

            lookup = lookup_expense_ratio(holding.ticker, holding.expense_ratio)
            if lookup.assumed_stock:
                notes.append(f"{holding.ticker} is treated as an individual stock. If it's a fund, add its expense ratio to your file.")
            if lookup.source is ExpenseSource.UNKNOWN:
                notes.append(f"{holding.ticker}'s expense ratio is unknown, so it's left out of the fee average.")

            positions.append(Position(holding.ticker, holding.shares, price, lookup.asset_type, lookup.expense_ratio))
            rows.append({
                "ticker": holding.ticker,
                "shares": holding.shares,
                "price": price,
                "value": None if price is None else holding.shares * price,
                "expense_ratio": lookup.expense_ratio,
                "expense_ratio_source": lookup.source.value,
                "asset_type": lookup.asset_type,
                "asset_type_name": ASSET_TYPE_NAMES[lookup.asset_type],
                "assumed_stock": lookup.assumed_stock,
                "label": label.text if label else "Price unavailable",
            })
        return positions, rows, list(labels.values()), notes
