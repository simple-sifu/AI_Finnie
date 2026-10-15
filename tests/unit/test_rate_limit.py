"""Story 8.3: request budgets (25/day, 5/minute, 1 second apart)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.core.rate_limit import RequestBudget, eastern_midnight_after

T0 = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)  # 10:00 US Eastern


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def slept(clock):
    waits = []

    async def sleep(seconds):
        waits.append(seconds)
        clock.now += timedelta(seconds=seconds)

    return waits, sleep


def budget(tmp_path, clock, sleep, per_day=25, per_minute=5, interval=1.0):
    return RequestBudget(tmp_path / "av.json", per_day, per_minute, interval, clock=clock, sleep=sleep)


async def test_requests_are_spaced_one_second_apart(tmp_path, clock, slept):
    waits, sleep = slept
    b = budget(tmp_path, clock, sleep)
    assert await b.acquire() and await b.acquire()
    assert waits == [1.0]


async def test_no_wait_when_calls_are_already_spaced(tmp_path, clock, slept):
    waits, sleep = slept
    b = budget(tmp_path, clock, sleep)
    await b.acquire()
    clock.now += timedelta(seconds=5)
    await b.acquire()
    assert waits == []


async def test_per_minute_budget_refuses_without_waiting(tmp_path, clock, slept):
    waits, sleep = slept
    b = budget(tmp_path, clock, sleep, interval=0)
    assert all([await b.acquire() for _ in range(5)])
    assert await b.acquire() is False
    assert waits == []
    clock.now += timedelta(seconds=61)
    assert await b.acquire()


async def test_daily_budget_resets_at_midnight_us_eastern(tmp_path, clock, slept):
    _, sleep = slept
    b = budget(tmp_path, clock, sleep, per_day=3, interval=0)
    for _ in range(3):
        assert await b.acquire()
        clock.now += timedelta(minutes=2)
    assert await b.acquire() is False and b.remaining_today() == 0
    clock.now = datetime(2026, 10, 16, 3, 59, tzinfo=timezone.utc)  # 23:59 Eastern, same day
    assert await b.acquire() is False
    clock.now = datetime(2026, 10, 16, 4, 0, tzinfo=timezone.utc)  # midnight Eastern
    assert await b.acquire() and b.remaining_today() == 2


async def test_budget_survives_a_restart(tmp_path, clock, slept):
    _, sleep = slept
    for _ in range(2):
        await budget(tmp_path, clock, sleep, interval=0).acquire()
    assert budget(tmp_path, clock, sleep).remaining_today() == 23


async def test_burst_rejection_blocks_for_a_minute(tmp_path, clock, slept):
    _, sleep = slept
    b = budget(tmp_path, clock, sleep, interval=0)
    b.note_rejection("Please consider spreading out your free API requests more sparingly (1 request per second).")
    assert await b.acquire() is False
    clock.now += timedelta(seconds=61)
    assert await b.acquire()


async def test_daily_rejection_blocks_until_tomorrow(tmp_path, clock, slept):
    _, sleep = slept
    b = budget(tmp_path, clock, sleep, interval=0)
    b.note_rejection("Our standard API rate limit is 25 requests per day.")
    clock.now += timedelta(hours=5)
    assert await b.acquire() is False and b.remaining_today() == 0


def test_corrupt_state_file_starts_fresh(tmp_path, clock):
    path = tmp_path / "av.json"
    path.write_text("{oops")
    assert RequestBudget(path, 25, 5, clock=clock).remaining_today() == 25


def test_eastern_midnight_after():
    assert eastern_midnight_after(T0) == datetime(2026, 10, 16, 4, 0, tzinfo=timezone.utc)


# --- MonthlyBudget (Story 8.5) ---


async def test_monthly_budget_counts_and_refuses(tmp_path, clock):
    from src.core.rate_limit import MonthlyBudget

    b = MonthlyBudget(tmp_path / "serp.json", per_month=2, clock=clock)
    assert await b.acquire() and await b.acquire()
    assert await b.acquire() is False and b.remaining() == 0


async def test_monthly_budget_resets_in_a_new_month_and_survives_restart(tmp_path, clock):
    from src.core.rate_limit import MonthlyBudget

    path = tmp_path / "serp.json"
    await MonthlyBudget(path, 100, clock=clock).acquire()
    assert MonthlyBudget(path, 100, clock=clock).remaining() == 99
    clock.now = datetime(2026, 11, 1, 4, 0, tzinfo=timezone.utc)  # Nov 1, midnight US Eastern
    assert MonthlyBudget(path, 100, clock=clock).remaining() == 100


def test_monthly_budget_mark_exhausted(tmp_path, clock):
    from src.core.rate_limit import MonthlyBudget

    b = MonthlyBudget(tmp_path / "serp.json", 100, clock=clock)
    b.mark_exhausted()
    assert b.remaining() == 0
