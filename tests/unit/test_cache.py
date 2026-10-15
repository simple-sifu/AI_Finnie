"""Story 8.2: the JSON disk cache."""

from datetime import datetime, timedelta, timezone

import pytest

from src.core.cache import DiskCache

T0 = datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def cache(tmp_path, clock):
    return DiskCache(tmp_path, namespace="test", clock=clock)


def test_round_trip_keeps_value_and_fetch_time(cache):
    cache.set("quote:VTI", {"price": 376.88}, ttl_seconds=1800)
    entry = cache.get("quote:VTI")
    assert entry.value == {"price": 376.88} and entry.fetched_at == T0 and entry.ttl_seconds == 1800


def test_entry_is_fresh_until_the_ttl_passes(cache, clock):
    cache.set("k", 1, ttl_seconds=1800)
    clock.advance(minutes=29, seconds=59)
    assert cache.get_fresh("k") is not None
    clock.advance(seconds=1)
    assert cache.get_fresh("k") is None


def test_expired_entries_are_kept_for_fallback(cache, clock):
    cache.set("k", "old", ttl_seconds=60)
    clock.advance(days=3)
    entry = cache.get("k")
    assert entry.value == "old" and not entry.is_fresh and entry.age == timedelta(days=3)


def test_missing_key_returns_none(cache):
    assert cache.get("nope") is None and cache.get_fresh("nope") is None


def test_cache_survives_a_new_instance(tmp_path, clock):
    DiskCache(tmp_path, "test", clock).set("k", [1, 2], ttl_seconds=60)
    assert DiskCache(tmp_path, "test", clock).get("k").value == [1, 2]


def test_namespaces_are_separate(tmp_path, clock):
    DiskCache(tmp_path, "market", clock).set("k", "m", 60)
    assert DiskCache(tmp_path, "news", clock).get("k") is None


def test_unreadable_file_is_treated_as_missing(cache):
    cache.set("k", 1, 60)
    cache._path("k").write_text("{not json")
    assert cache.get("k") is None


def test_keys_with_any_characters_work_and_leave_no_temp_files(cache):
    key = "news:what's happening with rates? / Fed"
    cache.set(key, "ok", 60)
    assert cache.get(key).value == "ok"
    assert [p.suffix for p in cache.directory.iterdir()] == [".json"]


def test_overwriting_updates_the_fetch_time(cache, clock):
    cache.set("k", "v1", 60)
    clock.advance(minutes=5)
    cache.set("k", "v2", 60)
    entry = cache.get("k")
    assert entry.value == "v2" and entry.fetched_at == T0 + timedelta(minutes=5)


def test_a_file_that_belongs_to_a_different_key_is_ignored(cache):
    cache.set("quote:VTI", 1, 60)
    path = cache._path("quote:VTI")
    path.write_text(path.read_text().replace('"key": "quote:VTI"', '"key": "quote:SPY"'))  # e.g. a hash collision
    assert cache.get("quote:VTI") is None


def test_a_value_that_cannot_be_saved_raises_and_leaves_no_partial_file(cache):
    cache.set("k", "good", 60)
    with pytest.raises(TypeError):
        cache.set("k", object(), 60)  # not JSON serializable
    assert cache.get("k").value == "good"  # the earlier value is untouched
    assert [p.suffix for p in cache.directory.iterdir()] == [".json"]  # and no temporary file is left behind
