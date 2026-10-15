"""Markets tab (Story 7.3): ticker cards, a trend chart, a ticker lookup and an explanation.

Layout follows front-end spec §4.3. Each ticker needs only ONE data request: its daily price
history holds the latest close and the day before, which gives the card's price and change as
well as the chart. That keeps a cold start to one request per ticker, and history is cached for
24 hours, so refreshing the tab stays inside the free API limits (Stories 8.2 and 8.3).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import streamlit as st

from src.agents.base import AGENT_FAILED
from src.core.freshness import DataLabel, DataSource
from src.core.market_data import MarketResult, NotFound, PriceHistory, Unavailable, normalize_ticker
from src.core.models import AgentName, AgentRequest, AgentResponse
from src.utils.logging import get_logger, log_event
from src.web_app import charts, components
from src.workflow.conversation import get_conversation

logger = get_logger(__name__)

NOT_FOUND_TEXT = "We couldn't find that ticker. Check the symbol and try again."
LIMIT_NOTE = "Live data is paused until tomorrow to stay within our free data limit."
PRICE_UNAVAILABLE = "Price unavailable right now. Try again later."
SEARCH_KEY, SELECTED_KEY, EXPLAIN_REQUEST, EXPLAIN_RESULT = "markets_search", "markets_selected", "markets_explain_request", "markets_explain"


@dataclass(frozen=True)
class Card:
    symbol: str
    price: float | None
    change: float | None  # versus the previous close
    change_percent: float | None
    label: DataLabel | None
    source: DataSource
    points: list[tuple[str, float]]  # (ISO date, close), oldest first
    problem: str | None = None  # set when there is nothing to show


def card_from_result(symbol: str, result: MarketResult) -> Card:
    value = result.value
    if isinstance(value, NotFound):
        return Card(symbol, None, None, None, None, result.source, [], NOT_FOUND_TEXT)
    if isinstance(value, Unavailable) or not isinstance(value, PriceHistory) or not value.points:
        return Card(symbol, None, None, None, None, result.source, [], PRICE_UNAVAILABLE)
    points = [(p.day.isoformat(), p.close) for p in value.points]
    price = value.points[-1].close
    if len(value.points) < 2 or value.points[-2].close <= 0:
        return Card(symbol, price, None, None, result.label(), result.source, points)
    previous = value.points[-2].close
    return Card(symbol, price, price - previous, (price / previous - 1) * 100, result.label(), result.source, points)


def change_text(card: Card) -> str:
    """`:green[▲ +4.44 (+1.20%)]`. The arrow and the sign carry the meaning, so color is never the only signal."""
    if card.change is None:
        return ":gray[— change not available]"
    if card.change > 0:
        arrow, color = "▲", "green"
    elif card.change < 0:
        arrow, color = "▼", "red"
    else:
        arrow, color = "▬", "gray"
    return f":{color}[{arrow} {card.change:+,.2f} ({card.change_percent:+.2f}%)]"


# --- data --------------------------------------------------------------------------------------


async def _fetch_all(market, symbols: list[str]) -> list[MarketResult]:
    return list(await asyncio.gather(*(market.get_daily_history(symbol) for symbol in symbols)))


def fetch_cards(services, runner, symbols: list[str], timeout: float) -> list[Card]:
    with st.spinner("Loading prices…"):
        try:
            results = runner.run(_fetch_all(services.market, symbols), timeout)
        except Exception as exc:  # the data layer never raises, but the runner or loop might
            log_event(logger, "error", level=logging.ERROR, kind="markets_tab_failed", detail=type(exc).__name__)
            return [Card(s, None, None, None, None, DataSource.UNAVAILABLE, [], PRICE_UNAVAILABLE) for s in symbols]
    return [card_from_result(symbol, result) for symbol, result in zip(symbols, results)]


def daily_limit_reached(services) -> bool:
    budget = getattr(getattr(services, "market", None), "budget", None)
    return budget is not None and budget.remaining_today() <= 0


# --- display -----------------------------------------------------------------------------------


def _select(symbol: str) -> None:
    st.session_state[SELECTED_KEY] = symbol
    st.session_state[SEARCH_KEY] = ""  # picking a card ends the search


def _request_explanation(symbol: str) -> None:
    st.session_state[EXPLAIN_REQUEST] = symbol


def render_card(card: Card, selected: bool, key: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{card.symbol}**")
        if card.problem:
            st.caption(card.problem)
            return
        st.markdown(f"### ${card.price:,.2f}")
        st.markdown(change_text(card))
        if card.label:
            components.freshness_label(card.label)
        st.button(
            "Showing chart" if selected else "Show chart", key=f"show_chart_{key}", disabled=selected,
            on_click=_select, args=(card.symbol,), width="stretch",
        )


def explain(services, runner, symbol: str, timeout: float) -> AgentResponse:
    profile = get_conversation(st.session_state).profile
    request = AgentRequest(message=f"Explain how {symbol} has been doing.", profile=profile, payload={"ticker": symbol})
    with st.spinner(f"Finnie is looking at {symbol}…"):
        try:
            return runner.run(services.agents[AgentName.MARKET].run(request), timeout)
        except Exception as exc:
            log_event(logger, "error", level=logging.ERROR, kind="markets_explain_failed", detail=type(exc).__name__)
            return AgentResponse(agent=AgentName.MARKET, answer=AGENT_FAILED, error=True)


def render_selected(card: Card, services, runner, timeout: float) -> None:
    figure = charts.price_trend(card.symbol, card.points)
    if figure is not None:
        components.chart_with_table(figure, charts.price_trend_table(card.points), f"trend_{card.symbol}")
    if card.label:
        components.freshness_label(card.label)

    st.button("Explain this", key="explain_this", on_click=_request_explanation, args=(card.symbol,),
              help="Finnie explains what these numbers mean in plain language.")
    if st.session_state.pop(EXPLAIN_REQUEST, None) == card.symbol:
        st.session_state[EXPLAIN_RESULT] = {"symbol": card.symbol, "response": explain(services, runner, card.symbol, timeout)}
    shown = st.session_state.get(EXPLAIN_RESULT)
    if shown and shown["symbol"] == card.symbol:  # an explanation belongs to one ticker
        response: AgentResponse = shown["response"]
        components.render_answer(response.answer)
        components.freshness_labels(response.labels)
        if response.disclaimer:
            components.disclaimer_callout(response.disclaimer)


def render(services=None, runner=None, tickers: list[str] | None = None, timeout: float = 120) -> None:
    st.subheader("Markets")
    if services is None or runner is None or not tickers:
        st.info("The markets overview isn't available right now. Please check the configuration message above.")
        return

    raw = st.text_input("Look up any US ticker", key=SEARCH_KEY, placeholder="e.g. AAPL or VOO").strip()
    searched: Card | None = None
    if raw:
        symbol = normalize_ticker(raw)
        if symbol is None:
            st.warning(NOT_FOUND_TEXT)
        else:
            searched = fetch_cards(services, runner, [symbol], timeout)[0]
            if searched.problem == NOT_FOUND_TEXT:
                st.warning(NOT_FOUND_TEXT)
                searched = None

    cards = fetch_cards(services, runner, tickers, timeout)
    if daily_limit_reached(services) and any(c.source in (DataSource.STALE, DataSource.SAMPLE, DataSource.UNAVAILABLE) for c in cards):
        st.info(LIMIT_NOTE)

    selected = searched.symbol if searched else st.session_state.get(SELECTED_KEY) or tickers[0]
    if searched:
        st.caption("Search result")
        render_card(searched, selected == searched.symbol, key=f"search_{searched.symbol}")
    for column, card in zip(st.columns(len(cards)), cards):
        with column:
            render_card(card, selected == card.symbol and not searched, key=card.symbol)

    chosen = searched or next((c for c in cards if c.symbol == selected), cards[0])
    if not chosen.problem:
        render_selected(chosen, services, runner, timeout)
    if any(c.source in (DataSource.STALE, DataSource.SAMPLE, DataSource.UNAVAILABLE) for c in [*cards, *([searched] if searched else [])]):
        st.button("Refresh prices", key="refresh_markets", help="Try again to get current prices.")
