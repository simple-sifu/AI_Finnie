"""Story 7.2: the Portfolio tab (charts, table, and the tab in the running app)."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.agents.portfolio import PortfolioAgent, PortfolioExplanation
from src.core import config
from src.core.models import AgentName
from src.web_app import charts
from src.web_app.tabs import portfolio as tab
from src.workflow import factory
from tests.unit.test_portfolio_agent import PRICES, FixedMarket

APP = str(Path(__file__).resolve().parents[2] / "src" / "web_app" / "app.py")
KEYS = {"OPENAI_API_KEY": "sk-test-openai-123456", "ALPHA_VANTAGE_API_KEY": "av-test-key-123456", "SERPAPI_API_KEY": "serp-test-key-123456"}


# --- charts (front-end spec §5) ---------------------------------------------------------------


def rows(*pairs):
    return [{"ticker": t, "value": v} for t, v in pairs]


def test_pie_shows_each_holding_with_its_value_and_a_title():
    fig = charts.holdings_pie(rows(("VTI", 600), ("BND", 300), ("AAPL", 100)))
    pie = fig.data[0]
    assert fig.layout.title.text == "What you own" and fig.layout.legend.title.text == "Holding"
    assert list(pie.labels) == ["VTI", "BND", "AAPL"] and list(pie.values) == [600, 300, 100]
    assert pie.textinfo == "label+percent"


def test_pie_has_at_most_eight_slices_and_groups_the_rest_as_other():
    many = rows(*[(f"T{i}", 1000 - i * 10) for i in range(12)])
    pie = charts.holdings_pie(many).data[0]
    assert len(pie.labels) == 8 and pie.labels[-1] == "Other (5 holdings)"
    assert sum(pie.values) == sum(r["value"] for r in many)  # nothing is lost in "Other"
    assert list(pie.values[:7]) == sorted(pie.values[:7], reverse=True)


def test_pie_with_exactly_eight_holdings_has_no_other_and_ignores_unpriced_ones():
    pie = charts.holdings_pie(rows(*[(f"T{i}", 100 - i) for i in range(8)], ("XYZ", None))).data[0]
    assert len(pie.labels) == 8 and "XYZ" not in pie.labels and not any("Other" in label for label in pie.labels)


def test_pie_is_none_when_nothing_is_priced():
    assert charts.holdings_pie(rows(("XYZ", None))) is None and charts.holdings_pie([]) is None


def test_bar_is_sorted_largest_first_with_percentages_axes_and_a_title():
    fig = charts.allocation_bar({"Bond funds": 0.25, "Stock funds": 0.6, "Individual stocks": 0.15})
    bar = fig.data[0]
    assert fig.layout.title.text == "Your mix of investments" and bar.orientation == "h"
    assert list(bar.y) == ["Stock funds", "Bond funds", "Individual stocks"] and list(bar.x) == [60.0, 25.0, 15.0]
    assert list(bar.text) == ["60%", "25%", "15%"]  # the number is on the bar, not only its color
    assert fig.layout.xaxis.title.text == "Share of your portfolio (%)" and fig.layout.yaxis.title.text == "Type of investment"
    assert fig.layout.yaxis.autorange == "reversed"  # largest at the top


def test_bar_is_none_without_an_allocation():
    assert charts.allocation_bar({}) is None


# --- formatting and the holdings table ---------------------------------------------------------


def row(**kw):
    base = {"ticker": "VTI", "shares": 40.0, "price": 300.0, "value": 12000.0, "weight": 0.5598, "expense_ratio": 0.03,
            "asset_type": "stock_fund", "asset_type_name": "Stock funds", "assumed_stock": False, "label": "Live · as of Oct 14 close"}
    return {**base, **kw}


def test_table_columns_and_normal_row():
    table = tab.holdings_table([row()])
    assert list(table.columns) == ["Ticker", "Shares", "Price", "Value", "% of portfolio", "Expense ratio", "Type", "Data"]
    assert table.iloc[0].to_dict() == {
        "Ticker": "VTI", "Shares": "40", "Price": "$300.00", "Value": "$12,000.00", "% of portfolio": "56.0%",
        "Expense ratio": "0.03%", "Type": "Stock funds", "Data": "Live · as of Oct 14 close",
    }


def test_a_holding_without_a_price_says_unavailable():
    cells = tab.holdings_table([row(price=None, value=None, weight=0.0, label="Price unavailable")]).iloc[0]
    assert (cells["Price"], cells["Value"], cells["% of portfolio"], cells["Data"]) == ("unavailable", "unavailable", "—", "Price unavailable")


def test_unknown_expense_ratio_is_unknown_never_zero_and_stocks_are_not_applicable():
    unknown = tab.holdings_table([row(expense_ratio=None, asset_type=None, asset_type_name="Funds (type unknown)")]).iloc[0]
    assert unknown["Expense ratio"] == "unknown" and "0" not in unknown["Expense ratio"]
    stock = tab.holdings_table([row(asset_type="individual_stock", asset_type_name="Individual stocks", expense_ratio=None)]).iloc[0]
    assert stock["Expense ratio"] == "n/a (stock)"


def test_a_guessed_stock_is_marked_assumed():
    cells = tab.holdings_table([row(asset_type="individual_stock", asset_type_name="Individual stocks", assumed_stock=True)]).iloc[0]
    assert cells["Type"] == "Individual stocks (assumed)"


def test_fractional_shares_are_shown_plainly():
    assert tab.holdings_table([row(shares=2.5)]).iloc[0]["Shares"] == "2.5"


def test_read_upload():
    assert tab.read_upload(None) is None
    upload = SimpleNamespace(name="mine.csv", getvalue=lambda: b"ticker,shares\nVTI,1\n")
    assert tab.read_upload(upload) == ("mine.csv", b"ticker,shares\nVTI,1\n")


def test_every_sample_file_exists():
    for filename in tab.SAMPLES.values():
        assert (tab.SAMPLES_DIR / filename).is_file()


# --- the tab in the running app ---------------------------------------------------------------


class CountingAgent(PortfolioAgent):
    runs = 0

    async def run(self, request):
        type(self).runs += 1
        return await super().run(request)


class ExplainLLM:
    def __init__(self, recommends=True):
        self.recommends = recommends

    async def structured(self, schema, system, user, history=None):
        return PortfolioExplanation(answer="Your portfolio is well spread out.", response_type="education", includes_recommendation=self.recommends)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)
    market = FixedMarket(PRICES)
    CountingAgent.runs = 0
    agent = CountingAgent(ExplainLLM(), "Not personalized advice.", market)
    services = SimpleNamespace(agents={AgentName.PORTFOLIO: agent}, workflow=SimpleNamespace(), settings=None)
    monkeypatch.setattr(factory, "build_services", lambda settings: services)
    st.cache_resource.clear()
    yield SimpleNamespace(market=market, agent=agent, monkeypatch=monkeypatch)
    st.cache_resource.clear()


def run_app():
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    return app


def portfolio_tab(app):
    return app.tabs[1]


def button(app, key):
    return next(b for b in portfolio_tab(app).button if b.key == key)


def load(app, sample="Diversified portfolio"):
    portfolio_tab(app).selectbox[0].select(sample).run()
    button(app, "load_sample").click().run()
    return app


def metrics(app):
    return {m.label: m.value for m in portfolio_tab(app).metric}


def test_empty_state_shows_the_upload_area_and_what_the_analysis_shows(env):
    app = run_app()
    assert not app.exception
    assert tab.EMPTY_TEXT in [i.value for i in portfolio_tab(app).info]
    assert tab.FORMAT_HINT in [c.value for c in portfolio_tab(app).caption]
    assert button(app, "load_sample") and not metrics(app) and env.agent.runs == 0


def test_loading_a_sample_shows_the_four_metrics(env):
    app = load(run_app())
    assert not app.exception
    # 40 VTI @300 + 60 VXUS @60 + 50 BND @70 + 15 VNQ @90 + 5 AAPL @200 = 21,450
    assert metrics(app) == {
        "Total value": "$21,450.00", "Weighted expense ratio": "0.038%",  # (12000*.03 + 3600*.05 + 3500*.03 + 1350*.13) / 21450
        "Diversification score": "96 / 100", "Risk level": "Moderate",
    }


def test_two_charts_and_the_holdings_table_are_shown(env):
    app = load(run_app())
    assert len(app.get("plotly_chart")) == 2
    table = portfolio_tab(app).dataframe[0].value
    assert list(table["Ticker"]) == ["VTI", "VXUS", "BND", "VNQ", "AAPL"]
    assert set(table["Data"]) == {"Live · as of Oct 14 close"}  # each price carries its freshness label


def test_the_explanation_and_a_disclaimer_on_recommendations_appear_with_the_metrics(env):
    app = load(run_app())
    assert "Your portfolio is well spread out." in [m.value for m in portfolio_tab(app).markdown]
    assert [w.value for w in portfolio_tab(app).warning] == ["Not personalized advice."]
    assert ":green[●] Live · as of Oct 14 close" in [c.value for c in portfolio_tab(app).caption]


def test_no_disclaimer_when_the_explanation_recommends_nothing(env):
    env.agent.llm = ExplainLLM(recommends=False)
    app = load(run_app())
    assert not portfolio_tab(app).warning


def test_a_file_with_problems_lists_each_one_and_shows_no_analysis(env):
    app = load(run_app(), "A file with problems (see how errors are shown)")
    errors = [e.value for e in portfolio_tab(app).error]
    assert len(errors) == 1 and "Row 2: shares is not a number ('forty')." in errors[0] and "Row 3: the ticker is missing." in errors[0]
    assert not metrics(app) and not app.get("plotly_chart") and not portfolio_tab(app).dataframe


def test_missing_prices_are_noted_left_out_and_can_be_refreshed(env):
    env.market.unavailable = {"VNQ"}
    app = load(run_app())
    notes = " ".join(i.value for i in portfolio_tab(app).info)
    assert "VNQ: price unavailable, so it's left out of the totals." in notes
    assert metrics(app)["Total value"] == "$20,100.00"
    table = portfolio_tab(app).dataframe[0].value
    assert table[table["Ticker"] == "VNQ"].iloc[0]["Price"] == "unavailable"
    env.market.unavailable = set()  # the data service recovers
    button(app, "refresh_prices").click().run()
    assert metrics(app)["Total value"] == "$21,450.00" and not [b for b in portfolio_tab(app).button if b.key == "refresh_prices"]


def test_no_prices_at_all_gives_a_friendly_message_and_a_refresh_button(env):
    env.market.prices = {}
    app = load(run_app())
    assert not metrics(app) and any("couldn't get prices" in w.value for w in portfolio_tab(app).warning)
    assert [b for b in portfolio_tab(app).button if b.key == "refresh_prices"]


def test_the_analysis_runs_once_not_on_every_rerun(env):
    app = load(run_app())
    assert env.agent.runs == 1
    app.run()
    app.run()
    assert env.agent.runs == 1  # a rerun reuses the result


def test_changing_the_risk_tolerance_in_the_sidebar_updates_the_analysis(env):
    app = load(run_app(), "Concentrated in two stocks")
    assert not any("risk tolerance" in n.value for n in portfolio_tab(app).info)
    next(b for b in app.sidebar.selectbox if b.label == "Risk tolerance").select("Conservative").run()
    assert env.agent.runs == 2
    assert any("risk level is High, but you set your risk tolerance to Conservative" in n.value for n in portfolio_tab(app).info)


def test_clear_returns_to_the_empty_state(env):
    app = load(run_app())
    button(app, "clear_portfolio").click().run()
    assert tab.EMPTY_TEXT in [i.value for i in portfolio_tab(app).info] and not metrics(app)


def test_a_failing_runner_gives_a_friendly_message_not_a_crash(env):
    async def boom(request):
        raise RuntimeError("agent exploded")

    env.agent.run = boom
    app = load(run_app())
    assert not app.exception and any("something went wrong" in w.value for w in portfolio_tab(app).warning)


def test_the_tab_explains_when_the_services_are_not_available(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    for name in KEYS:
        monkeypatch.delenv(name, raising=False)
    st.cache_resource.clear()
    app = run_app()
    assert not app.exception and not app.tabs  # a missing key stops the app before any tab renders
