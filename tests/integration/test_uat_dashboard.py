"""UAT-PORT-02 and UAT-MKT-01: Portfolio and Markets tabs (docs/uat-script.md §2–3)."""

from tests.integration.conftest import upload_portfolio

LIVE_LABEL = "Live · as of Oct 14 close"


def portfolio_charts(app):
    return [c for c in app.get("plotly_chart") if "What you own" in c.proto.spec or "Your mix of investments" in c.proto.spec]


def test_uat_port_02_dashboard_metrics_and_labels(app):
    upload_portfolio(app)
    tab = app.tabs[1]
    assert not app.exception
    assert {m.label: m.value for m in tab.metric}["Total value"] == "$25,802.20"
    assert len(portfolio_charts(app)) == 2
    assert set(tab.dataframe[0].value["Data"]) == {LIVE_LABEL}


def test_uat_mkt_01_markets_tab_cards(app, stack):
    assert sorted(stack.alpha.requests_for("TIME_SERIES_DAILY")) == ["BND", "DIA", "QQQ", "SPY", "VTI"]
    markets = app.tabs[2]
    assert "### $769.60" in [m.value for m in markets.markdown]
    before = len(stack.alpha.calls)
    app.run()
    assert len(stack.alpha.calls) == before
