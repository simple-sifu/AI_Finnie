"""Shared data models (architecture §5). More models are added as agents are built."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel

from src.rag.retriever import RetrievedChunk


class Source(BaseModel):
    """A citation shown under an answer (Story 6.4)."""

    title: str  # the article's title
    url: str  # the article's source link
    source_name: str
    category: str
    as_of: int | None = None  # year for year-specific figures, e.g. 2026
    published: date | None = None  # publication date of a news article (Story 4.2)


def sources_from(retrieved: Iterable[RetrievedChunk]) -> list[Source]:
    """Citations for the chunks a response used: one per article, best match first.

    A glossary term cites its related article, so a term and an article chunk
    from the same article produce a single source. No retrieved chunks, no sources.
    """
    sources: dict[str, Source] = {}
    for item in sorted(retrieved, key=lambda r: r.score, reverse=True):
        chunk = item.chunk
        if chunk.slug not in sources:
            sources[chunk.slug] = Source(
                title=chunk.title,
                url=chunk.source_url,
                source_name=chunk.source_name,
                category=chunk.category,
                as_of=chunk.as_of,
            )
    return list(sources.values())


def format_sources(sources: list[Source]) -> str:
    """Markdown list of sources, or "" when there are none (so nothing is shown)."""
    if not sources:
        return ""
    lines = ["**Sources**"]
    for source in sources:
        when = ""
        if source.published:
            when = f" ({source.published:%b} {source.published.day})"
        elif source.as_of:
            when = f" (as of {source.as_of})"
        lines.append(f"- [{source.title}]({source.url}){when}, {source.source_name}")
    return "\n".join(lines)


# --- Agent contracts (Story 3.1, architecture §5 and §7.1) -------------------

from enum import Enum  # noqa: E402
from typing import Any, Literal  # noqa: E402

from pydantic import Field  # noqa: E402

from src.core.freshness import DataLabel  # noqa: E402

ResponseType = Literal["advice", "education", "uncertain"]


class AgentName(str, Enum):
    FINANCE_QA = "finance_qa"
    PORTFOLIO = "portfolio"
    MARKET = "market"
    GOAL_PLANNING = "goal_planning"
    NEWS = "news"
    TAX = "tax"

    @property
    def display_name(self) -> str:
        """The badge shown above each answer (front-end spec §3.4)."""
        return {
            "finance_qa": "Finance Q&A",
            "portfolio": "Portfolio Analysis",
            "market": "Market Analysis",
            "goal_planning": "Goal Planning",
            "news": "News",
            "tax": "Tax Education",
        }[self.value]


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    agent: AgentName | None = None


class SessionProfile(BaseModel):
    """Session-only personalization (Story 5.5, D-15)."""

    knowledge_level: Literal["beginner", "intermediate"] = "beginner"
    risk_tolerance: Literal["conservative", "moderate", "aggressive"] | None = None
    goal_note: str | None = None


class AgentRequest(BaseModel):
    message: str
    history: list[ChatTurn] = Field(default_factory=list)
    profile: SessionProfile = Field(default_factory=SessionProfile)
    payload: dict[str, Any] | None = None  # tab input, e.g. parsed holdings or a goal form


class AgentResponse(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    agent: AgentName | None  # None when Finnie itself answers (clarifying or off-topic)
    answer: str
    response_type: ResponseType = "education"
    sources: list[Source] = Field(default_factory=list)
    labels: list[DataLabel] = Field(default_factory=list)
    disclaimer: str | None = None  # set by the disclaimer policy, shown as a separate callout
    needs_input: str | None = None  # e.g. "risk_tolerance"
    data: dict[str, Any] | None = None  # structured results for the UI
    error: bool = False  # True when this is a friendly failure message

    @property
    def is_advice(self) -> bool:
        return self.response_type != "education"  # uncertain counts as advice (D-43)
