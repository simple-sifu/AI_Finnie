"""Shared data models (architecture §5). More models are added as agents are built."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel

from src.rag.retriever import RetrievedChunk


class Source(BaseModel):
    """A citation shown under an answer (Story 6.4)."""

    title: str  # the article's title
    url: str  # the article's source link
    source_name: str
    category: str
    as_of: int | None = None  # year for year-specific figures, e.g. 2026


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
        year = f" (as of {source.as_of})" if source.as_of else ""
        lines.append(f"- [{source.title}]({source.url}){year}, {source.source_name}")
    return "\n".join(lines)
