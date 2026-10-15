"""Market Analysis Agent (Story 3.4, FR3, FR16).

Looks up a quote and price history through MarketData (cache, limits and
fallbacks apply), calculates 1-week, 1-month and 3-month changes in code, and
has the LLM explain what the numbers mean for a beginner. Every figure carries
its freshness label.
"""

from __future__ import annotations

import re
from typing import Protocol

from pydantic import BaseModel, Field

from src.agents.base import BaseAgent, LLMAnswer
from src.core.calculators import price_changes
from src.core.freshness import DataLabel, DataSource
from src.core.market_data import MarketResult, NotFound, PriceHistory, Quote, normalize_ticker
from src.core.models import AgentName, AgentRequest, AgentResponse

MAX_TICKERS = 3  # protects the 25-requests-a-day budget
MARKET_PROXY = "SPY"  # tracks the S&P 500, used for "how's the market?" questions
ASK_FOR_TICKER = (
    "Which stock or fund would you like to look at? You can give me a ticker symbol, like VTI or AAPL."
)
# All-caps words that look like tickers but aren't, in ordinary questions.
NOT_TICKERS = {
    "A", "I", "AN", "AND", "ARE", "AT", "BE", "BUY", "CAN", "DO", "ETF", "ETFS", "FOR", "HOW", "IN", "IRA", "IS",
    "IT", "ME", "MY", "NOW", "OF", "OK", "ON", "OR", "SELL", "SO", "THE", "TO", "US", "USA", "VS", "WHAT", "WHY",
    "S", "P", "SP", "AI", "CEO", "IPO", "GDP", "CPI", "FED", "PE", "EPS", "YTD",
}
_EXPLICIT = re.compile(r"\$([A-Za-z][A-Za-z.\-]{0,9})\b|\b([A-Z]{1,5})\b")


class QuoteSource(Protocol):
    """Async quote and history access used by the market and portfolio agents."""

    async def get_quote(self, ticker: str) -> MarketResult: ...

    async def get_daily_history(self, ticker: str) -> MarketResult: ...


class TickerRequest(BaseModel):
    """Structured output when the router needs help finding ticker symbols in the question."""

    tickers: list[str] = Field(description="US ticker symbols the user asks about, e.g. AAPL for Apple. Empty if none.")
    overall_market: bool = Field(description="True if the user asks about the stock market in general.")


def explicit_tickers(message: str) -> list[str]:
    """Tickers written as $AAPL or as an all-caps word like VTI; no LLM call needed."""
    found: list[str] = []
    for dollar, caps in _EXPLICIT.findall(message):
        symbol = normalize_ticker(dollar or caps)
        if symbol and (dollar or symbol not in NOT_TICKERS) and symbol not in found:
            found.append(symbol)
    return found[:MAX_TICKERS]


SAMPLE_PREFIX = "SAMPLE DATA, NOT REAL PRICES (say so to the user): "


def describe(symbol: str, quote: Quote | None, quote_label: DataLabel | None, changes: dict, history_label, sample: bool) -> str:
    if quote is None:
        return f"{symbol}: no price available right now."
    prefix = SAMPLE_PREFIX if sample else ""
    lines = [
        f"{prefix}{symbol}: price ${quote.price:,.2f}, change {quote.change:+.2f} ({quote.change_percent:+.2f}%) "
        f"from the previous close of ${quote.previous_close:,.2f} [{quote_label.text if quote_label else ''}]"
    ]
    trend = ", ".join(f"{period} {value:+.2f}%" for period, value in changes.items() if value is not None)
    if trend:
        lines.append(f"  {prefix}Trend: {trend} [{history_label.text if history_label else ''}]")
    else:
        lines.append("  Trend: not available right now.")
    return "\n".join(lines)


class MarketAgent(BaseAgent):
    """Looks up quotes and trends, then explains them for beginners."""

    name = AgentName.MARKET
    instructions = """Your job: explain current prices and recent trends for the stocks and funds below.
Use ONLY the numbers given; never calculate new ones or make up figures.
Explain what the numbers mean for a beginner, e.g. what a 2% daily drop means and whether it's unusual.
Mention that prices are from the latest market close when the data says "close".
If prices are sample data, say they are examples, not real prices.
Don't predict future prices. If asked whether to buy or sell, explain the considerations instead of giving a yes/no."""

    def __init__(self, llm, disclaimer_text: str, market: QuoteSource):
        super().__init__(llm, disclaimer_text)
        self.market = market

    async def _tickers(self, request: AgentRequest) -> list[str]:
        payload = (request.payload or {}).get("ticker")
        if payload:
            symbol = normalize_ticker(payload)
            return [symbol] if symbol else []
        found = explicit_tickers(request.message)
        if found:
            return found
        extracted = await self.llm.structured(
            TickerRequest,
            "Identify which US stocks or funds the user is asking about. Map company or fund names to their "
            "ticker symbols (Apple -> AAPL). If the message refers back to something from earlier in the "
            "conversation (\"it\", \"that fund\", \"how about over 3 months?\"), use the earlier messages to "
            "work out which ticker is meant. Set overall_market if they ask about the market in general.",
            request.message,
            request.history,
        )
        tickers = [s for t in extracted.tickers if (s := normalize_ticker(t))][:MAX_TICKERS]
        return tickers or ([MARKET_PROXY] if extracted.overall_market else [])

    async def _run(self, request: AgentRequest) -> AgentResponse:
        tickers = await self._tickers(request)
        if not tickers:
            return AgentResponse(agent=self.name, answer=ASK_FOR_TICKER, needs_input="ticker")

        facts, rows, labels, missing = [], [], {}, []
        for symbol in tickers:
            quote_result = await self.market.get_quote(symbol)
            if isinstance(quote_result.value, NotFound):
                missing.append(symbol)
                continue
            quote = quote_result.value if isinstance(quote_result.value, Quote) else None
            history_result = await self.market.get_daily_history(symbol) if quote else None
            history = history_result.value if history_result and isinstance(history_result.value, PriceHistory) else None
            sample_quote = quote_result.source is DataSource.SAMPLE
            if history and history_result.source is DataSource.SAMPLE and not sample_quote:
                history = None  # never pair a sample trend with a real price; it would mislead
            changes = price_changes([p.close for p in history.points]) if history else {}

            quote_label = quote_result.label()
            history_label = history_result.label() if history_result and history else None
            for label in (quote_label, history_label):
                if label:
                    labels.setdefault(label.text, label)
            facts.append(describe(symbol, quote, quote_label, changes, history_label, sample_quote))
            rows.append({
                "symbol": symbol,
                "quote": quote,
                "changes": changes,
                "history": [(p.day.isoformat(), p.close) for p in history.points] if history else [],
                "label": quote_label.text if quote_label else "Price unavailable",
            })

        if not rows:
            answer = NotFound(missing[0]).message if missing else ASK_FOR_TICKER
            return AgentResponse(agent=self.name, answer=answer, data={"not_found": missing})
        if missing:
            facts.append("Not found (tell the user to check these symbols): " + ", ".join(missing))

        reply = await self.llm.structured(
            LLMAnswer,
            f"{self.system_prompt(request.profile)}\n\nMarket data:\n" + "\n".join(facts),
            request.message,
            request.history,
        )
        return AgentResponse(
            agent=self.name, answer=reply.answer, response_type=reply.response_type,
            labels=list(labels.values()), data={"tickers": rows, "not_found": missing},
        )
