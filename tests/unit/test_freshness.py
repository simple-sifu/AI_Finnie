"""Story 8.4: Live / Cached / Sample data labels."""

from datetime import date, datetime, timedelta, timezone

import pytest

from src.core.freshness import DataSource, Freshness, describe_age, describe_as_of, make_label
from src.core.market_data import MarketResult, NotFound, PriceHistory, PricePoint, Quote, Unavailable

NOW = datetime(2026, 10, 15, 14, 30, tzinfo=timezone.utc)
TRADING_DAY = date(2026, 10, 14)
QUOTE = Quote("VTI", 376.88, -4.44, -1.16, 3262690, 381.32, TRADING_DAY, NOW)


def test_live_label_shows_the_trading_day_close():
    label = make_label(DataSource.LIVE, NOW, TRADING_DAY, NOW)
    assert label.text == "Live · as of Oct 14 close"
    assert label.freshness is Freshness.LIVE and label.color == "green"


def test_cached_label_shows_age_and_trading_day():
    label = make_label(DataSource.CACHE, NOW - timedelta(minutes=12), TRADING_DAY, NOW)
    assert label.text == "Cached · updated 12 min ago · as of Oct 14 close"
    assert label.freshness is Freshness.CACHED and label.color == "amber"


def test_stale_data_is_labeled_cached_with_its_real_age():
    label = make_label(DataSource.STALE, NOW - timedelta(hours=3, minutes=5), TRADING_DAY, NOW)
    assert label.text == "Cached · updated 3 hr ago · as of Oct 14 close"


def test_sample_label_says_not_real_prices():
    label = make_label(DataSource.SAMPLE, None, TRADING_DAY, NOW)
    assert label.text == "Sample data · not real prices"
    assert label.freshness is Freshness.SAMPLE and label.color == "grey" and label.as_of is None


def test_unavailable_has_no_label():
    assert make_label(DataSource.UNAVAILABLE, None, None, NOW) is None


def test_every_source_with_data_gets_one_of_three_labels():
    for source in DataSource:
        label = make_label(source, NOW, TRADING_DAY, NOW)
        if source is DataSource.UNAVAILABLE:
            assert label is None
        else:
            assert label.freshness in set(Freshness)
            assert label.text.split(" · ")[0] in {"Live", "Cached", "Sample data"}


def test_news_dates_are_not_described_as_a_market_close():
    label = make_label(DataSource.LIVE, NOW, NOW, NOW, closing=False)
    assert label.text == "Live · as of Oct 15"


def test_missing_as_of_is_simply_omitted():
    assert make_label(DataSource.LIVE, NOW, None, NOW).text == "Live"


@pytest.mark.parametrize(
    "age, text",
    [
        (timedelta(seconds=0), "just now"),
        (timedelta(seconds=59), "just now"),
        (timedelta(minutes=12), "12 min ago"),
        (timedelta(minutes=59), "59 min ago"),
        (timedelta(minutes=61), "1 hr ago"),
        (timedelta(hours=23, minutes=59), "23 hr ago"),
        (timedelta(hours=25), "1 day ago"),
        (timedelta(days=3, hours=2), "3 days ago"),
    ],
)
def test_describe_age(age, text):
    assert describe_age(age) == text


def test_describe_as_of_formats_single_digit_days_without_padding():
    assert describe_as_of(date(2026, 11, 3)) == "as of Nov 3 close"


# --- labels on real market results ---


def test_market_result_labels_for_each_source():
    live = MarketResult(QUOTE, NOW, DataSource.LIVE)
    cached = MarketResult(QUOTE, NOW - timedelta(minutes=12), DataSource.CACHE)
    sample = MarketResult(QUOTE, None, DataSource.SAMPLE)
    assert live.label(NOW).text == "Live · as of Oct 14 close"
    assert cached.label(NOW).text == "Cached · updated 12 min ago · as of Oct 14 close"
    assert sample.label(NOW).text == "Sample data · not real prices"


def test_history_is_labeled_with_its_last_trading_day():
    history = PriceHistory("VTI", [PricePoint(date(2026, 10, 10), 1, 1), PricePoint(TRADING_DAY, 2, 2)], NOW)
    assert MarketResult(history, NOW, DataSource.LIVE).label(NOW).text == "Live · as of Oct 14 close"


def test_unavailable_and_not_found_results():
    assert MarketResult(Unavailable("MSFT"), None, DataSource.UNAVAILABLE).label(NOW) is None
    assert MarketResult(NotFound("ZZZZ"), NOW, DataSource.LIVE).label(NOW) is None


def test_label_defaults_to_the_current_time():
    result = MarketResult(QUOTE, datetime.now(timezone.utc) - timedelta(minutes=5), DataSource.CACHE)
    assert result.label().text.startswith("Cached · updated 5 min ago")


def test_sample_label_wording_depends_on_what_is_sampled():
    assert make_label(DataSource.SAMPLE, None, None, NOW).text == "Sample data · not real prices"
    assert make_label(DataSource.SAMPLE, None, None, NOW, kind="headlines").text == "Sample data · not real headlines"
    assert make_label(DataSource.LIVE, NOW, None, NOW, kind="headlines").text == "Live"  # kind only affects samples
