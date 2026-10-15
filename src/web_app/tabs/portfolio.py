"""Portfolio tab (Stories 7.2 and 3.3): upload holdings, see the metrics, charts and an explanation.

Layout follows front-end spec §4.2: upload area, four metric tiles, two charts, the agent's
explanation, then the holdings table. The tab calls the Portfolio Analysis Agent directly, since
the tab already says which agent is needed (architecture §2); there is no router call.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from src.agents.base import AGENT_FAILED
from src.core.calculators import PortfolioMetrics
from src.core.models import AgentName, AgentRequest, AgentResponse
from src.utils.logging import get_logger, log_event
from src.web_app import charts, components
from src.workflow.conversation import get_conversation

logger = get_logger(__name__)

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "data" / "samples"
SAMPLES = {
    "Diversified portfolio": "diversified.csv",
    "Concentrated in two stocks": "concentrated.csv",
    "Some expense ratios missing": "missing_expense_ratios.csv",
    "A file with problems (see how errors are shown)": "malformed_bad_values.csv",
}
FORMAT_HINT = "Columns: ticker, shares, and optional expense_ratio (as a percentage, e.g. 0.03 for 0.03%)."
EMPTY_TEXT = "Upload your holdings to see what you own, how spread out it is, what it costs in fees and how risky it is."
TEMPLATE_CSV = "ticker,shares,expense_ratio\nVTI,10,0.03\nBND,5,0.03\nAAPL,2,\n"

INPUT_KEY, RESULT_KEY, NONCE_KEY, UPLOAD_KEY = "portfolio_input", "portfolio_result", "portfolio_refresh", "portfolio_upload_n"


# --- formatting ------------------------------------------------------------------------------


def money(value: float | None) -> str:
    return "unavailable" if value is None else f"${value:,.2f}"


def percent(value: float | None, digits: int = 2) -> str:
    return "unknown" if value is None else f"{value:.{digits}f}%"


def expense_text(row: dict) -> str:
    if row["asset_type"] == "individual_stock":
        return "n/a (stock)"  # stocks have no fund fee
    return percent(row["expense_ratio"])  # a fund with no ratio anywhere is "unknown", never 0


def type_text(row: dict) -> str:
    name = row["asset_type_name"]
    return f"{name} (assumed)" if row.get("assumed_stock") else name


def holdings_table(rows: list[dict]) -> pd.DataFrame:
    """The holdings table (front-end spec §4.2 item 5)."""
    return pd.DataFrame([
        {
            "Ticker": row["ticker"],
            "Shares": f"{row['shares']:g}",
            "Price": money(row["price"]),
            "Value": money(row["value"]),
            "% of portfolio": "—" if row["value"] is None else f"{row['weight'] * 100:.1f}%",
            "Expense ratio": expense_text(row),
            "Type": type_text(row),
            "Data": row["label"],
        }
        for row in rows
    ])


# --- input -----------------------------------------------------------------------------------


def read_upload(uploaded) -> tuple[str, bytes] | None:
    """The (name, bytes) of an uploaded file, or None if nothing is uploaded."""
    return None if uploaded is None else (uploaded.name, uploaded.getvalue())


def apply_upload(session) -> None:
    """Store the file the user just uploaded as the portfolio input (a plain function so it can be tested)."""
    chosen = read_upload(session.get(f"portfolio_upload_{session.get(UPLOAD_KEY, 0)}"))
    if chosen:
        session[INPUT_KEY] = chosen


def _on_upload() -> None:
    apply_upload(st.session_state)


def _load_sample(label: str) -> None:
    st.session_state[INPUT_KEY] = (label, (SAMPLES_DIR / SAMPLES[label]).read_bytes())


def _clear() -> None:
    st.session_state[INPUT_KEY] = None
    st.session_state[RESULT_KEY] = None
    st.session_state[UPLOAD_KEY] = st.session_state.get(UPLOAD_KEY, 0) + 1  # a new key empties the uploader


def _refresh() -> None:
    st.session_state[NONCE_KEY] = st.session_state.get(NONCE_KEY, 0) + 1


def render_input_area() -> None:
    st.file_uploader(
        "Upload your holdings (CSV)", type=["csv"], help=FORMAT_HINT,
        key=f"portfolio_upload_{st.session_state.get(UPLOAD_KEY, 0)}", on_change=_on_upload,
    )
    st.caption(FORMAT_HINT)
    pick, load, template, clear = st.columns([3, 2, 2, 1], vertical_alignment="bottom")
    sample = pick.selectbox("Or try a sample portfolio", list(SAMPLES), key="portfolio_sample")
    load.button("Load sample portfolio", key="load_sample", on_click=_load_sample, args=(sample,), width="stretch")
    template.download_button("Download a template", TEMPLATE_CSV, "holdings_template.csv", "text/csv", width="stretch")
    clear.button("Clear", key="clear_portfolio", on_click=_clear, width="stretch")


# --- analysis --------------------------------------------------------------------------------


def analyze(services, runner, data: bytes, timeout: float) -> AgentResponse:
    """Run the Portfolio agent on the file, once per file, profile and refresh (not on every rerun)."""
    profile = get_conversation(st.session_state).profile
    key = (hashlib.sha256(data).hexdigest(), profile.knowledge_level, profile.risk_tolerance, st.session_state.get(NONCE_KEY, 0))
    cached = st.session_state.get(RESULT_KEY)
    if cached and cached["key"] == key:
        return cached["response"]

    agent = services.agents[AgentName.PORTFOLIO]
    request = AgentRequest(message="Explain my portfolio.", profile=profile, payload={"csv": data})
    with st.spinner("Analyzing your portfolio…"):
        try:
            response = runner.run(agent.run(request), timeout)
        except Exception as exc:  # the agent never raises, but the runner or loop might
            log_event(logger, "error", level=logging.ERROR, kind="portfolio_tab_failed", detail=type(exc).__name__)
            response = AgentResponse(agent=AgentName.PORTFOLIO, answer=AGENT_FAILED, error=True)
    st.session_state[RESULT_KEY] = {"key": key, "response": response}
    return response


# --- results ---------------------------------------------------------------------------------


def render_metrics(metrics: PortfolioMetrics) -> None:
    value, fee, diversification, risk = st.columns(4)
    value.metric("Total value", money(metrics.total_value))
    fee.metric(
        "Weighted expense ratio",
        percent(metrics.weighted_expense_ratio, 3),
        help="The yearly fee rate across your funds. Individual stocks have no fund fee.",
    )
    if metrics.weighted_expense_ratio is not None and metrics.expense_ratio_coverage < 0.995:
        fee.caption(f"Based on {metrics.expense_ratio_coverage * 100:.0f}% of your portfolio")
    diversification.metric(
        "Diversification score", f"{metrics.diversification_score} / 100",
        help="How spread out your money is. A single stock scores 0; broad funds score high.",
    )
    diversification.caption(metrics.diversification_label)
    risk.metric("Risk level", metrics.risk_level, help="Based on the types of investment you hold.")
    risk.caption(f"Score {metrics.risk_score} on a 1 to 5 scale")


def render_charts(response: AgentResponse) -> None:
    metrics: PortfolioMetrics = response.data["metrics"]
    pie = charts.holdings_pie(response.data["holdings"])
    bar = charts.allocation_bar(metrics.allocation_by_type)
    left, right = st.columns(2)
    if pie is not None:
        with left:
            components.chart_with_table(pie, charts.holdings_pie_table(response.data["holdings"]), "portfolio_pie")
    if bar is not None:
        with right:
            components.chart_with_table(bar, charts.allocation_table(metrics.allocation_by_type), "portfolio_bar")


def render_result(response: AgentResponse) -> None:
    data = response.data or {}
    if data.get("problems"):  # the file couldn't be read: list every problem, no analysis (Story 3.3 AC 1)
        st.error("I couldn't read this file. Please fix these and upload it again:\n\n" + "\n".join(f"- {p}" for p in data["problems"]))
        return
    if "metrics" not in data:  # no holdings data at all, e.g. the assistant was unavailable
        st.warning(response.answer)
        return

    metrics: PortfolioMetrics = data["metrics"]
    if data["notes"]:
        st.info("\n".join(f"- {note}" for note in data["notes"]))
    if metrics.total_value <= 0:
        st.warning(response.answer)
    else:
        render_metrics(metrics)
        components.freshness_labels(response.labels)
        render_charts(response)
        st.markdown(response.answer)
        if response.disclaimer:
            components.disclaimer_callout(response.disclaimer)

    st.dataframe(holdings_table(data["holdings"]), hide_index=True, width="stretch")
    if metrics.unpriced or any(row["label"].startswith("Sample data") for row in data["holdings"]):
        st.button("Refresh prices", key="refresh_prices", on_click=_refresh, help="Try again to get current prices.")


def render(services=None, runner=None, timeout: float = 120) -> None:
    st.subheader("Portfolio")
    if services is None or runner is None:
        st.info("The portfolio analysis isn't available right now. Please check the configuration message above.")
        return

    render_input_area()
    chosen = st.session_state.get(INPUT_KEY)
    if chosen is None:
        st.info(EMPTY_TEXT)
        return
    name, data = chosen
    st.caption(f"Showing: {name}")
    render_result(analyze(services, runner, data, timeout))
