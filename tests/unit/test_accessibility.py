"""Story 7.5: accessibility, branding and responsive design (front-end spec §5 and §7)."""

import re
from datetime import date, timedelta
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.core import config
from src.core.calculators import plan_goal
from src.web_app import charts, components

ROOT = Path(__file__).resolve().parents[2]
APP = str(ROOT / "src" / "web_app" / "app.py")
KEYS = {"OPENAI_API_KEY": "sk-test-openai-123456", "ALPHA_VANTAGE_API_KEY": "av-test-key-123456", "SERPAPI_API_KEY": "serp-test-key-123456"}

ROWS = [{"ticker": f"T{i}", "value": 1000.0 - i * 50} for i in range(12)]  # more than 8 holdings, so there is an "Other" slice
ALLOCATION = {"Stock funds": 0.6, "Bond funds": 0.25, "Individual stocks": 0.15}
POINTS = [((date(2026, 10, 14) - timedelta(days=99 - i)).isoformat(), 100.0 + i) for i in range(100)]
PLAN = plan_goal(20000, 3000, 30, 0.05)  # 2.5 years: the last point is part way along the axis

FIGURES = {
    "pie": charts.holdings_pie(ROWS),
    "bar": charts.allocation_bar(ALLOCATION),
    "trend": charts.price_trend("VTI", POINTS),
    "goal": charts.goal_projection(PLAN),
}


# --- AC 2: every chart has a title, labeled axes or a legend, and plain-language labels -----------------


@pytest.mark.parametrize("name", FIGURES)
def test_every_chart_has_a_title(name):
    assert FIGURES[name].layout.title.text.strip()


@pytest.mark.parametrize("name", ["bar", "trend", "goal"])
def test_every_line_and_bar_chart_has_both_axes_labeled(name):
    layout = FIGURES[name].layout
    assert layout.xaxis.title.text.strip() and layout.yaxis.title.text.strip()


def test_the_pie_has_a_legend_with_a_title_and_labels_on_the_slices():
    fig = FIGURES["pie"]
    assert fig.layout.legend.title.text == "Holding" and fig.layout.showlegend is not False
    assert fig.data[0].textinfo == "label+percent"


@pytest.mark.parametrize("name", FIGURES)
def test_labels_are_plain_language_not_code(name):
    fig = FIGURES[name]
    labels = [fig.layout.title.text, fig.layout.xaxis.title.text, fig.layout.yaxis.title.text, fig.layout.legend.title.text]
    labels += [str(label) for trace in fig.data for label in (getattr(trace, "labels", None) or getattr(trace, "y", None) or []) if isinstance(label, str)]
    for label in filter(None, labels):
        assert "_" not in label and label == label.strip() and not re.search(r"\bNone\b|\bnan\b", label)


def test_no_chart_relies_on_color_alone():
    assert FIGURES["pie"].data[0].textinfo == "label+percent"  # each slice is named and has its percentage
    assert all("%" in text for text in FIGURES["bar"].data[0].text)  # each bar has its number
    goal = FIGURES["goal"]
    assert goal.layout.shapes[0].line.dash == "dash" and "Goal:" in goal.layout.annotations[0].text  # dashed AND named
    assert FIGURES["trend"].layout.title.text.startswith("VTI")  # one line, identified by the title


# --- AC 3: the same data as a table --------------------------------------------------------------------------


def test_pie_table_matches_the_pie_including_the_other_slice():
    table = charts.holdings_pie_table(ROWS)
    pie = FIGURES["pie"].data[0]
    assert list(table["Holding"]) == list(pie.labels) and len(table) == 8 and table["Holding"].iloc[-1] == "Other (5 holdings)"
    assert list(table["Value"]) == [f"${v:,.2f}" for v in pie.values]
    assert sum(float(s.rstrip("%")) for s in table["Share of portfolio"]) == pytest.approx(100, abs=0.5)


def test_bar_table_matches_the_bars():
    table, bar = charts.allocation_table(ALLOCATION), FIGURES["bar"].data[0]
    assert list(table["Type of investment"]) == list(bar.y)
    assert list(table["Share of portfolio"]) == [f"{x:g}%" for x in bar.x]


def test_trend_table_matches_the_line():
    table, line = charts.price_trend_table(POINTS), FIGURES["trend"].data[0]
    assert list(table["Date"]) == list(line.x) and len(table) == 63
    assert list(table["Closing price"]) == [f"${y:,.2f}" for y in line.y]


def test_goal_table_matches_the_projection_and_the_goal_line():
    table, line = charts.goal_projection_table(PLAN), FIGURES["goal"].data[0]
    assert list(table["Years from now"]) == [f"{x:g}" for x in line.x] and list(table["Years from now"])[-1] == "2.5"
    assert list(table["Projected balance"]) == [f"${y:,.2f}" for y in line.y]
    assert set(table["Goal"]) == {"$20,000.00"}


# --- AC 4: laptop and tablet widths ---------------------------------------------------------------------------


def test_no_chart_has_a_fixed_width_so_all_resize_with_the_page():
    assert all(fig.layout.width is None for fig in FIGURES.values())


def test_the_code_never_sets_fixed_widths_or_uses_the_deprecated_option():
    for path in (ROOT / "src" / "web_app").rglob("*.py"):
        text = path.read_text()
        assert "use_container_width" not in text, path.name
        assert not re.search(r"\bwidth\s*=\s*\d", text), f"{path.name} sets a fixed pixel width"


def test_columns_wrap_two_to_a_row_on_narrow_screens():
    css = components.RESPONSIVE_CSS
    assert "@media (max-width: 900px)" in css and "flex-wrap: wrap" in css
    assert "calc(50% - 1rem)" in css  # two per row, so four metric tiles become 2x2
    assert '[data-testid="stHorizontalBlock"]' in css and '[data-testid="stColumn"]' in css


def test_no_row_has_more_than_five_columns():
    sources = "".join(p.read_text() for p in (ROOT / "src" / "web_app").rglob("*.py"))
    counts = [int(m) for m in re.findall(r"st\.columns\((\d+)\)", sources)]
    assert counts and max(counts) <= 5  # the four metric tiles are the widest fixed row; market cards are capped by D-18


# --- AC 1 and AC 5: branding, default theme, no formal standard ------------------------------------------------------


@pytest.fixture
def env(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from src.workflow import factory

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(factory, "build_services", lambda settings: SimpleNamespace(workflow=SimpleNamespace(), agents={}, settings=None))
    st.cache_resource.clear()
    yield monkeypatch
    st.cache_resource.clear()


def test_the_app_is_branded_finnie(env):
    configs = []
    real = st.set_page_config
    env.setattr(st, "set_page_config", lambda **kw: (configs.append(kw), real(**kw))[1])
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    assert configs and configs[0]["page_title"] == "Finnie"
    assert app.sidebar.title[0].value == "Finnie" and "AI Finance Assistant" in [c.value for c in app.sidebar.caption]


def test_the_app_injects_the_responsive_css(env):
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    assert any(components.RESPONSIVE_CSS in m.value for m in app.markdown)


def test_streamlits_default_theme_is_used():
    settings = ROOT / ".streamlit" / "config.toml"
    assert not settings.exists() or "[theme]" not in settings.read_text()
    assert not list((ROOT / "src" / "web_app").rglob("*.css")) and not list((ROOT / "src").rglob("*.png"))  # no custom styling or logos


def test_the_readme_states_the_accessibility_position():
    readme = (ROOT / "README.md").read_text()
    assert "## Accessibility and design" in readme
    assert "No formal accessibility standard (such as WCAG) is targeted in v1" in readme
    assert "Color is never the only signal" in readme and "Show as table" in readme
