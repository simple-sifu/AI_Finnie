"""Request budgets for free API tiers (Story 8.3, architecture §9.1).

Alpha Vantage's free tier allows 25 requests a day and 5 a minute, and rejects
requests sent faster than about 1 per second. The budget is saved to disk so
restarting the app doesn't reset it.

Only the short per-second spacing ever waits. When the per-minute or daily
budget is used up, `acquire` returns False immediately and the caller falls
back to cached or sample data instead of making the user wait.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from src.core.cache import Clock, utc_now

US_EASTERN = ZoneInfo("America/New_York")
Sleep = Callable[[float], Awaitable[None]]


class RequestBudget:
    def __init__(
        self,
        state_file: Path,
        per_day: int,
        per_minute: int,
        min_interval_seconds: float = 1.0,
        clock: Clock = utc_now,
        sleep: Sleep = asyncio.sleep,
        day_zone: ZoneInfo = US_EASTERN,
    ):
        self.state_file = state_file
        self.per_day = per_day
        self.per_minute = per_minute
        self.min_interval = timedelta(seconds=min_interval_seconds)
        self.clock = clock
        self.sleep = sleep
        self.day_zone = day_zone
        self._lock = asyncio.Lock()

    # -- persistence -------------------------------------------------------

    def _load(self) -> dict:
        try:
            return json.loads(self.state_file.read_text())
        except (OSError, ValueError):
            return {}

    def _save(self, state: dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.state_file.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        os.replace(tmp, self.state_file)

    def _today(self, now: datetime) -> str:
        return now.astimezone(self.day_zone).date().isoformat()

    def _current(self, now: datetime) -> dict:
        """Load state, starting a new day's count after midnight US Eastern."""
        state = self._load()
        if state.get("day") != self._today(now):
            state = {"day": self._today(now), "day_count": 0, "recent": [], "last": None, "blocked_until": None}
        cutoff = now - timedelta(minutes=1)
        state["recent"] = [t for t in state.get("recent", []) if datetime.fromisoformat(t) > cutoff]
        return state

    # -- public API ----------------------------------------------------------

    def remaining_today(self) -> int:
        state = self._current(self.clock())
        return max(0, self.per_day - state["day_count"])

    async def acquire(self) -> bool:
        """Reserve one request. Returns False, without waiting, if a budget is used up."""
        async with self._lock:
            now = self.clock()
            state = self._current(now)
            blocked = state.get("blocked_until")
            if blocked and datetime.fromisoformat(blocked) > now:
                return False
            if state["day_count"] >= self.per_day or len(state["recent"]) >= self.per_minute:
                return False

            if state.get("last"):
                wait = (datetime.fromisoformat(state["last"]) + self.min_interval - now).total_seconds()
                if wait > 0:
                    await self.sleep(wait)
                    now = self.clock()

            state["day_count"] += 1
            state["recent"].append(now.isoformat())
            state["last"] = now.isoformat()
            self._save(state)
            return True

    def note_rejection(self, message: str) -> None:
        """Record a limit refusal from the API so we stop asking for a while.

        A daily-limit message blocks until the next day; anything else blocks for a minute.
        """
        now = self.clock()
        state = self._current(now)
        if "per day" in message.lower() or "daily" in message.lower():
            state["day_count"] = self.per_day
        else:
            state["blocked_until"] = (now + timedelta(minutes=1)).isoformat()
        self._save(state)


def eastern_midnight_after(now: datetime) -> datetime:
    """When the daily budget resets (shown to users as "until tomorrow")."""
    local = now.astimezone(US_EASTERN)
    tomorrow = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return tomorrow.astimezone(timezone.utc)


class MonthlyBudget:
    """A per-calendar-month request budget, saved to disk (SerpApi news, Story 8.5).

    Months are counted in US Eastern time. SerpApi's own month may start on a
    different day (it follows the plan cycle), so the cap is kept below the
    plan's allowance and an "out of searches" reply also blocks the month.
    """

    def __init__(self, state_file: Path, per_month: int, clock: Clock = utc_now, zone: ZoneInfo = US_EASTERN):
        self.state_file = state_file
        self.per_month = per_month
        self.clock = clock
        self.zone = zone
        self._lock = asyncio.Lock()

    def _month(self) -> str:
        return self.clock().astimezone(self.zone).strftime("%Y-%m")

    def _load(self) -> dict:
        try:
            state = json.loads(self.state_file.read_text())
        except (OSError, ValueError):
            state = {}
        if state.get("month") != self._month():
            state = {"month": self._month(), "count": 0}
        return state

    def _save(self, state: dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.state_file.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        os.replace(tmp, self.state_file)

    def remaining(self) -> int:
        return max(0, self.per_month - self._load()["count"])

    async def acquire(self) -> bool:
        """Reserve one request. Returns False if this month's budget is used up."""
        async with self._lock:
            state = self._load()
            if state["count"] >= self.per_month:
                return False
            state["count"] += 1
            self._save(state)
            return True

    def mark_exhausted(self) -> None:
        state = self._load()
        state["count"] = self.per_month
        self._save(state)
