"""Story 7.3: the Markets tab."""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.agents.base import LLMAnswer
from src.agents.market import MarketAgent
from src.core import config
from src.core.cache import DiskCache
from src.core.freshness import DataSource
from src.core.market_data import (
    MarketData,
    MarketResult,
    NotFound,
    PriceHistory,
    PricePoint,
    Quote,
    Unavailable,
)
from src.core.mock_data import SampleMarketData
from src.core.models import AgentName
from src.core.rate_limit import RequestBudget
from src.web_app import charts
from src.web_app.tabs import markets as tab
from src.workflow import factory

APP = str(Path(__file__).resolve().parents[2] / "src" / "web_app" / "app.py")
KEYS = {"OPENAI_API_KEY": "sk-test-openai-123456", "ALPHA_VANTAGE_API_KEY": "av-test-key-123456", "SERPAPI_API_KEY": "serp-test-key-123456"}
LAST_DAY = date(2026, 10, 14)
NOW = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)

# symbol -> (previous close, last close). The 63 days before are flat at the previous close.
CLOSES = {"SPY": (110.0, 121.0), "QQQ": (100.0, 90.0), "DIA": (50.0, 50.0), "VTI": (200.0, 210.0), "BND": (70.0, 70.7), "AAPL": (250.0, 255.0)}


def history(symbol, prev, last, days=65):
    closes = [prev] * (days - 1) + [last]
    points = [PricePoint(LAST_DAY - timedelta(days=days - 1 - i), c, 1000) for i, c in enumerate(closes)]
    return PriceHistory(symbol, points, NOW)


# --- cards and chart helpers (pure) -------------------------------------------------------------


def result(value, source=DataSource.LIVE):
    return MarketResult(value, NOW, source)


def test_card_price_and_change_come_from_the_last_two_closes():
    card = tab.card_from_result("SPY", result(history("SPY", 110.0, 121.0)))
    assert (card.price, card.change) == (121.0, 11.0) and card.change_percent == pytest.approx(10.0)
    assert card.label.text == "Live · as of Oct 14 close" and card.problem is None and len(card.points) == 65


@pytest.mark.parametrize(
    "prev, last, text",
    [(110.0, 121.0, ":green[▲ +11.00 (+10.00%)]"), (100.0, 90.0, ":red[▼ -10.00 (-10.00%)]"), (50.0, 50.0, ":gray[▬ +0.00 (+0.00%)]")],
)
def test_change_uses_an_arrow_and_a_sign_as_well_as_color(prev, last, text):
    assert tab.change_text(tab.card_from_result("X", result(history("X", prev, last)))) == text


def test_a_single_day_of_history_has_a_price_but_no_change():
    one = PriceHistory("X", [PricePoint(LAST_DAY, 10.0, 1)], NOW)
    card = tab.card_from_result("X", result(one))
    assert card.price == 10.0 and card.change is None and tab.change_text(card) == ":gray[— change not available]"


def test_unknown_and_unavailable_tickers_have_a_message_instead_of_numbers():
    assert tab.card_from_result("ZZZZ", result(NotFound("ZZZZ"))).problem == tab.NOT_FOUND_TEXT
    unavailable = tab.card_from_result("VTI", MarketResult(Unavailable("VTI"), None, DataSource.UNAVAILABLE))
    assert unavailable.problem == tab.PRICE_UNAVAILABLE and unavailable.price is None


def test_trend_chart_shows_about_three_months_with_a_title_and_labeled_axes():
    points = [(p.day.isoformat(), p.close) for p in history("SPY", 110.0, 121.0, days=100).points]
    fig = charts.price_trend("SPY", points)
    assert len(fig.data[0].x) == 63 and fig.data[0].y[-1] == 121.0 and fig.data[0].x[-1] == "2026-10-14"
    assert fig.layout.title.text == "SPY: last 3 months"
    assert fig.layout.xaxis.title.text == "Date" and fig.layout.yaxis.title.text == "Closing price ($)"


def test_trend_chart_needs_at_least_two_points():
    assert charts.price_trend("X", []) is None and charts.price_trend("X", [("2026-10-14", 1.0)]) is None


# --- the tab in the running app, on the REAL data layer (cache, budget, fallbacks) -----------------


class CountingClient:
    """Stands in for Alpha Vantage and counts every request that would use up the free allowance."""

    def __init__(self):
        self.history_calls, self.quote_calls = [], []

    async def get_daily_history(self, symbol):
        self.history_calls.append(symbol)
        if symbol not in CLOSES:
            return NotFound(symbol)
        return history(symbol, *CLOSES[symbol])

    async def get_quote(self, symbol):
        self.quote_calls.append(symbol)
        prev, last = CLOSES[symbol]
        return Quote(symbol, last, last - prev, (last / prev - 1) * 100, 1000, prev, LAST_DAY, NOW)


class AnswerLLM:
    def __init__(self, kind="education"):
        self.kind, self.calls = kind, 0

    async def structured(self, schema, system, user, history=None):
        self.calls += 1
        return LLMAnswer(answer="This fund rose over the last three months.", response_type=self.kind)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)

    def build(per_day=25, per_minute=50, mock=True, kind="education"):
        client, llm = CountingClient(), AnswerLLM(kind)
        budget = RequestBudget(tmp_path / "limits.json", per_day, per_minute, 0)
        market = MarketData(client, DiskCache(tmp_path, "market"), budget, 1800, 86400, max_retries=0,
                            mock=SampleMarketData() if mock else None)
        services = SimpleNamespace(
            market=market, workflow=SimpleNamespace(), settings=None,
            agents={AgentName.MARKET: MarketAgent(llm, "Not personalized advice.", market)},
        )
        monkeypatch.setattr(factory, "build_services", lambda settings: services)
        st.cache_resource.clear()
        return SimpleNamespace(client=client, llm=llm, market=market)

    yield build
    st.cache_resource.clear()


def run_app():
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    return app


def markets(app):
    return app.tabs[2]


def button(app, key):
    return next(b for b in markets(app).button if b.key == key)


def texts(app):
    return [m.value for m in markets(app).markdown]


def test_a_card_for_each_configured_ticker_with_price_change_and_label(env):
    env()
    app = run_app()
    assert not app.exception
    text = texts(app)
    for symbol in ("SPY", "QQQ", "DIA", "VTI", "BND"):  # the configured tickers (D-18)
        assert f"**{symbol}**" in text
    assert "### $121.00" in text and ":green[▲ +11.00 (+10.00%)]" in text  # SPY, up
    assert ":red[▼ -10.00 (-10.00%)]" in text and ":gray[▬ +0.00 (+0.00%)]" in text  # QQQ down, DIA flat
    labels = [c.value for c in markets(app).caption if "●" in c.value]
    assert labels.count(":green[●] Live · as of Oct 14 close") >= 5  # every card carries its freshness label


def test_the_first_ticker_is_charted_and_another_can_be_chosen(env):
    env()
    app = run_app()
    assert [c.proto.id for c in app.get("plotly_chart")] and len(app.get("plotly_chart")) == 1
    assert button(app, "show_chart_SPY").disabled and button(app, "show_chart_SPY").label == "Showing chart"
    button(app, "show_chart_QQQ").click().run()
    assert button(app, "show_chart_QQQ").disabled and not button(app, "show_chart_SPY").disabled
    chart = app.get("plotly_chart")[0]
    assert "QQQ: last 3 months" in chart.proto.spec and len(app.get("plotly_chart")) == 1


def test_the_chart_has_its_own_freshness_label_under_it(env):
    env()
    app = run_app()
    labels = [c.value for c in markets(app).caption if "●" in c.value]
    assert len(labels) == 6  # five cards plus the chart


# --- AC 5: refreshing uses the cache and never exceeds the limits ---------------------------------


def test_a_cold_start_costs_one_request_per_ticker_and_no_quote_requests(env):
    e = env()
    run_app()
    assert sorted(e.client.history_calls) == ["BND", "DIA", "QQQ", "SPY", "VTI"] and e.client.quote_calls == []


def test_refreshing_the_tab_reuses_the_cache_and_makes_no_new_requests(env):
    e = env()
    app = run_app()
    app.run()
    app.run()
    button(app, "show_chart_QQQ").click().run()
    assert len(e.client.history_calls) == 5


def test_the_daily_limit_is_never_exceeded_and_the_tab_says_so(env):
    e = env(per_day=3)
    app = run_app()
    assert len(e.client.history_calls) == 3  # never more than the budget allows
    app.run()
    app.run()
    assert len(e.client.history_calls) == 3 and tab.LIMIT_NOTE in [i.value for i in markets(app).info]
    labels = [c.value for c in markets(app).caption if "●" in c.value]
    assert any(label.startswith(":gray[●] Sample data") for label in labels)  # the rest fall back to labeled sample data


def test_no_limit_note_while_the_limit_has_not_been_reached(env):
    env()
    assert tab.LIMIT_NOTE not in [i.value for i in markets(run_app()).info]


def test_with_no_data_at_all_cards_say_unavailable_and_nothing_crashes(env):
    env(per_day=0, mock=False)
    app = run_app()
    assert not app.exception and [c.value for c in markets(app).caption].count(tab.PRICE_UNAVAILABLE) == 5
    assert not app.get("plotly_chart")


# --- search: any US ticker (AC 3) -------------------------------------------------------------------


def search(app, text):
    markets(app).text_input[0].input(text).run()


def test_searching_a_ticker_shows_its_card_and_chart(env):
    e = env()
    app = run_app()
    search(app, "aapl")
    assert "Search result" in [c.value for c in markets(app).caption] and "**AAPL**" in texts(app)
    assert "### $255.00" in texts(app) and e.client.history_calls.count("AAPL") == 1
    assert "AAPL: last 3 months" in app.get("plotly_chart")[0].proto.spec


def test_an_unknown_ticker_gets_the_friendly_message(env):
    app = run_app() if env() else None
    search(app, "zzzz")
    assert [w.value for w in markets(app).warning] == [tab.NOT_FOUND_TEXT] and "Search result" not in [c.value for c in markets(app).caption]


def test_an_invalid_symbol_gets_the_same_message_without_any_request(env):
    e = env()
    app = run_app()
    before = len(e.client.history_calls)
    search(app, "$$$")
    assert [w.value for w in markets(app).warning] == [tab.NOT_FOUND_TEXT] and len(e.client.history_calls) == before


def test_choosing_a_card_ends_the_search(env):
    app = run_app() if env() else None
    search(app, "aapl")
    button(app, "show_chart_VTI").click().run()
    assert markets(app).text_input[0].value == "" and "Search result" not in [c.value for c in markets(app).caption]
    assert "VTI: last 3 months" in app.get("plotly_chart")[0].proto.spec


# --- Explain this (approved addition) ----------------------------------------------------------------


def test_explain_this_shows_the_agents_explanation_below_the_chart(env):
    e = env()
    app = run_app()
    button(app, "explain_this").click().run()
    assert "This fund rose over the last three months." in texts(app) and e.llm.calls == 1
    assert not markets(app).warning  # an education answer has no disclaimer


def test_an_advice_style_explanation_carries_the_disclaimer(env):
    env(kind="advice")
    app = run_app()
    button(app, "explain_this").click().run()
    assert [w.value for w in markets(app).warning] == ["Not personalized advice."]


def test_the_explanation_is_not_requested_again_on_rerun_and_belongs_to_one_ticker(env):
    e = env()
    app = run_app()
    button(app, "explain_this").click().run()
    app.run()
    assert e.llm.calls == 1 and "This fund rose over the last three months." in texts(app)
    button(app, "show_chart_QQQ").click().run()
    assert "This fund rose over the last three months." not in texts(app)  # that explanation was about SPY


def test_explain_this_stays_on_the_markets_tab(env):
    env()
    app = run_app()
    button(app, "explain_this").click().run()
    assert not app.exception and "This fund rose over the last three months." not in [m.value for m in app.tabs[0].markdown]


# --- refresh -----------------------------------------------------------------------------------------


def test_no_refresh_button_when_every_price_is_current(env):
    env()
    assert not [b for b in markets(run_app()).button if b.key == "refresh_markets"]


def test_refresh_prices_appears_when_some_prices_are_sample_data(env):
    env(per_day=3)
    assert [b for b in markets(run_app()).button if b.key == "refresh_markets"]


def test_the_tab_explains_itself_when_services_are_missing(monkeypatch):
    messages = []
    monkeypatch.setattr(st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(st, "info", lambda text, **k: messages.append(text))
    tab.render(None, None, None)
    assert messages == ["The markets overview isn't available right now. Please check the configuration message above."]
