"""A small JSON disk cache with time-to-live (Story 8.2, architecture §9.3).

One file per key under .cache/. Each entry records when the value was fetched
and how long it stays fresh. Expired entries are kept, not deleted, because the
fallback chain (Story 8.3) uses them as stale data when an API is unavailable.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = PROJECT_ROOT / ".cache"

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class CacheEntry:
    key: str
    value: Any
    fetched_at: datetime
    ttl_seconds: int
    now: datetime

    @property
    def age(self) -> timedelta:
        return self.now - self.fetched_at

    @property
    def is_fresh(self) -> bool:
        return self.age < timedelta(seconds=self.ttl_seconds)


class DiskCache:
    def __init__(self, directory: Path = DEFAULT_CACHE_DIR, namespace: str = "default", clock: Clock = utc_now):
        self.directory = directory / namespace
        self.clock = clock

    def _path(self, key: str) -> Path:
        # Keys can contain any characters; hash them into a safe file name.
        return self.directory / f"{hashlib.sha256(key.encode()).hexdigest()[:32]}.json"

    def get(self, key: str) -> CacheEntry | None:
        """Return the entry, fresh or stale, or None if missing or unreadable."""
        path = self._path(key)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data["key"] != key:
                return None
            fetched_at = datetime.fromisoformat(data["fetched_at"])
            return CacheEntry(key, data["value"], fetched_at, int(data["ttl_seconds"]), self.clock())
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def get_fresh(self, key: str) -> CacheEntry | None:
        entry = self.get(key)
        return entry if entry and entry.is_fresh else None

    def set(self, key: str, value: Any, ttl_seconds: int, fetched_at: datetime | None = None) -> CacheEntry:
        """Store a JSON-serializable value. The write is atomic, so a crash never leaves half a file."""
        fetched_at = fetched_at or self.clock()
        self.directory.mkdir(parents=True, exist_ok=True)
        record = {"key": key, "value": value, "fetched_at": fetched_at.isoformat(), "ttl_seconds": ttl_seconds}
        fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(record, f)
            os.replace(tmp, self._path(key))
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return CacheEntry(key, value, fetched_at, ttl_seconds, self.clock())
