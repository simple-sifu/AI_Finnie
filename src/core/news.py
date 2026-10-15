"""Financial news search via SerpApi (Story 8.5, architecture §9.2).

Google News results through SerpApi, US English (D-21). Each search uses one of
the free plan's monthly searches, so results are cached (6 hours by default,
D-8) and counted against a monthly budget. When a search fails or the budget is
used up, the fallback is cached news, then sample news, never Tavily (D-9).
Tavily is optional in v1 (D-14) and not implemented.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import httpx

from src.core.cache import DEFAULT_CACHE_DIR, DiskCache, utc_now
from src.core.config import ConfigError
from src.core.freshness import DataLabel, DataSource, make_label
from src.core.rate_limit import MonthlyBudget
from src.utils.logging import get_logger, log_event

logger = get_logger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"
MAX_ITEMS = 10
_OUT_OF_SEARCHES = re.compile(r"run out of searches|searches? (limit|left)|exceeded", re.I)


class NewsError(Exception):
    """A news search failed (network, server error or unexpected response)."""


class NewsLimitError(NewsError):
    """SerpApi says the account has no searches left."""


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str  # publisher, e.g. "Bloomberg.com"
    link: str
    published_at: datetime | None


@dataclass(frozen=True)
class NewsResult:
    query: str
    items: list[NewsItem]
    fetched_at: datetime | None
    source: DataSource

    def label(self, now: datetime | None = None) -> DataLabel | None:
        """Freshness label (Story 8.4). The date shown is the newest article's publication date."""
        if not self.items:
            return None
        dates = [item.published_at for item in self.items if item.published_at]
        return make_label(
            self.source, self.fetched_at, max(dates) if dates else None, now or utc_now(), closing=False, kind="headlines"
        )


class MockNews(Protocol):
    """Sample news for when nothing else is available (Story 8.6)."""

    def search(self, query: str) -> list[NewsItem] | None: ...


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip().lower())


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_results(data: dict, limit: int = MAX_ITEMS) -> list[NewsItem]:
    """Flatten SerpApi news results, including topic clusters ("stories"), into articles."""
    items: list[NewsItem] = []
    seen: set[str] = set()
    for result in data.get("news_results") or []:
        for article in result.get("stories") or [result]:
            link, title = article.get("link"), article.get("title")
            if not link or not title or link in seen:
                continue
            seen.add(link)
            source = article.get("source") or {}
            items.append(
                NewsItem(
                    title=title.strip(),
                    source=(source.get("name") if isinstance(source, dict) else str(source)) or "Unknown source",
                    link=link,
                    published_at=_parse_date(article.get("iso_date")),
                )
            )
            if len(items) >= limit:
                return items
    return items


class SerpApiClient:
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None, timeout: float = 30.0):
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def search(self, query: str) -> list[NewsItem]:
        params = {"engine": "google_news", "q": query, "gl": "us", "hl": "en", "api_key": self._api_key}
        try:
            response = await self._client.get(SERPAPI_URL, params=params)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise NewsError(f"SerpApi request failed: {type(exc).__name__}") from None
        if not isinstance(data, dict):
            raise NewsError("SerpApi returned an unexpected response")
        error = data.get("error")
        if error:
            if _OUT_OF_SEARCHES.search(str(error)):
                raise NewsLimitError("SerpApi has no searches left this month")
            if "hasn't returned any results" in str(error):
                return []
            raise NewsError(f"SerpApi error (HTTP {response.status_code})")
        if response.status_code >= 400:
            raise NewsError(f"SerpApi returned HTTP {response.status_code}")
        return parse_results(data)


class NewsService:
    """News with caching, a monthly budget and fallbacks; never raises to the caller."""

    def __init__(
        self,
        client: SerpApiClient,
        cache: DiskCache,
        budget: MonthlyBudget,
        ttl_seconds: int,
        mock: MockNews | None = None,
        mock_mode: bool = False,
    ):
        self.client = client
        self.cache = cache
        self.budget = budget
        self.ttl_seconds = ttl_seconds
        self.mock = mock
        self.mock_mode = mock_mode

    @classmethod
    def from_settings(cls, settings, cache_dir: Path | None = None, mock: MockNews | None = None) -> NewsService:
        if settings.news.provider != "serpapi":
            raise ConfigError("Only news.provider: serpapi is available in v1 (Tavily is optional and not built, D-14).")
        directory = cache_dir or DEFAULT_CACHE_DIR
        if mock is None:
            from src.core.mock_data import sample_news  # imported here to avoid a cycle

            mock = sample_news()
        return cls(
            SerpApiClient(settings.secrets.serpapi_api_key.get_secret_value()),
            DiskCache(directory, namespace="news"),
            MonthlyBudget(directory / "limits" / "serpapi.json", settings.news.monthly_limit),
            settings.news.ttl_seconds,
            mock=mock,
            mock_mode=settings.market.mode == "mock",
        )

    async def search(self, query: str) -> NewsResult:
        query = normalize_query(query)
        if not query:
            return NewsResult(query, [], None, DataSource.UNAVAILABLE)
        key = f"news:{query}"

        entry = self.cache.get_fresh(key)
        if entry is not None:
            log_event(logger, "cache", result="hit", key=key)
            return NewsResult(query, [_item_from_dict(d) for d in entry.value], entry.fetched_at, DataSource.CACHE)
        if self.mock_mode:
            return self._fallback(query, key, reason="mock_mode")

        log_event(logger, "cache", result="miss", key=key)
        if not await self.budget.acquire():
            return self._fallback(query, key, reason="budget")
        try:
            log_event(logger, "api_call", service="serpapi", query=query)
            items = await self.client.search(query)
        except NewsLimitError:
            self.budget.mark_exhausted()
            return self._fallback(query, key, reason="rate_limited")
        except NewsError as exc:
            return self._fallback(query, key, reason="error", detail=str(exc))

        stored = self.cache.set(key, [_item_to_dict(item) for item in items], self.ttl_seconds)
        return NewsResult(query, items, stored.fetched_at, DataSource.LIVE)

    def _fallback(self, query: str, key: str, reason: str, detail: str = "") -> NewsResult:
        stale = None if reason == "mock_mode" else self.cache.get(key)
        if stale is not None:
            log_event(logger, "fallback", level=logging.WARNING, to="stale_cache", key=key, reason=reason, detail=detail)
            return NewsResult(query, [_item_from_dict(d) for d in stale.value], stale.fetched_at, DataSource.STALE)
        sample = self.mock.search(query) if self.mock is not None else None
        if sample:
            log_event(logger, "fallback", level=logging.WARNING, to="sample", key=key, reason=reason, detail=detail)
            return NewsResult(query, sample, None, DataSource.SAMPLE)
        log_event(logger, "fallback", level=logging.WARNING, to="unavailable", key=key, reason=reason, detail=detail)
        return NewsResult(query, [], None, DataSource.UNAVAILABLE)


def _item_to_dict(item: NewsItem) -> dict:
    return {**asdict(item), "published_at": item.published_at.isoformat() if item.published_at else None}


def _item_from_dict(d: dict) -> NewsItem:
    return NewsItem(d["title"], d["source"], d["link"], _parse_date(d.get("published_at")))
