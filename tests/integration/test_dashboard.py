"""Story 9.2 AC 2: a portfolio upload through to the dashboard, in the running app, on the real stack.

The app gets Finnie's real services (see conftest.py), so the numbers on screen come from the real
agent, calculators, data clients and cache. Only the outside services' responses are faked.
"""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.workflow import factory
from tests.integration.support import PRICES

ROOT = Path(__file__).resolve().parents[2]
APP = str(ROOT / "src" / "web_app" / "app.py")
DIVERSIFIED = (ROOT / "src" / "data" / "samples" / "diversified.csv").read_bytes()
LIVE_LABEL = "Live · as of Oct 14 close"


@pytest.fixture
def app(stack, monkeypatch):
    monkeypatch.setattr(factory, "build_services", lambda settings: stack.services)  # the app builds its services once
    st.cache_resource.clear()
    running = AppTest.from_file(APP, default_timeout=60)
    running.run()
    yield running
    st.cache_resource.clear()


def upload(app, data=DIVERSIFIED):
    app.session_state["portfolio_input"] = ("mine.csv", data)  # what the uploader's callback stores
    app.run()
    return app


def portfolio_charts(app):
    return [c for c in app.get("plotly_chart") if "What you own" in c.proto.spec or "Your mix of investments" in c.proto.spec]


def test_an_uploaded_portfolio_becomes_metrics_charts_a_table_and_an_explanation(app):
    upload(app)
    tab = app.tabs[1]
    assert not app.exception
    assert {m.label: m.value for m in tab.metric}["Total value"] == "$25,802.20"
    assert {m.label: m.value for m in tab.metric}["Weighted expense ratio"] == "0.037%"  # (VTI .03, VXUS .05, BND .03, VNQ .13, stock 0) by value
    assert len(portfolio_charts(app)) == 2
    table = tab.dataframe[0].value
    assert list(table["Ticker"]) == ["VTI", "VXUS", "BND", "VNQ", "AAPL"]
    assert list(table["Price"]) == [f"${PRICES[t][1]:,.2f}" for t in table["Ticker"]]  # the prices the data client fetched
    assert set(table["Data"]) == {LIVE_LABEL}
    assert "Your portfolio is worth $25,802.20." in [m.value for m in tab.markdown]


def test_the_dashboard_tells_the_user_when_prices_are_not_live(app, stack):
    stack.alpha.limit_after = 0  # Alpha Vantage says the daily limit is reached
    upload(app)
    tab = app.tabs[1]
    assert not app.exception and "Sample data · not real prices" in set(tab.dataframe[0].value["Data"])
    assert [b for b in tab.button if b.key == "refresh_prices"]  # and offers to try again later


def test_a_bad_file_shows_every_problem_and_no_analysis(app, stack):
    upload(app, (ROOT / "src" / "data" / "samples" / "malformed_bad_values.csv").read_bytes())
    tab = app.tabs[1]
    assert "Row 2: shares is not a number ('forty')." in tab.error[0].value
    assert not [m for m in tab.metric] and not portfolio_charts(app)


def test_the_markets_tab_loads_its_cards_from_one_request_per_ticker_and_reruns_cost_nothing(app, stack):
    assert sorted(stack.alpha.requests_for("TIME_SERIES_DAILY")) == ["BND", "DIA", "QQQ", "SPY", "VTI"]
    assert stack.alpha.requests_for("GLOBAL_QUOTE") == []
    markets = app.tabs[2]
    assert "### $769.60" in [m.value for m in markets.markdown] and ":red[▼ -8.41 (-1.08%)]" in [m.value for m in markets.markdown]
    before = len(stack.alpha.calls)
    app.run()
    app.run()
    assert len(stack.alpha.calls) == before  # the cache answered
