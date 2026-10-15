"""Split knowledge-base content into chunks for retrieval (Story 6.2, architecture §8.2).

Articles are split by Markdown section ("## ..."), then sections are packed
into chunks of up to `chunk_chars` characters. A section longer than that is
split at word boundaries with `chunk_overlap` characters of overlap. Each
glossary term is its own chunk. Every chunk carries the metadata needed to
cite its source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.rag.content import Article, GlossaryTerm

_HEADING = re.compile(r"^## +(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    """One searchable passage with the metadata needed for citations."""

    chunk_id: str
    text: str
    kind: str  # "article" or "glossary"
    slug: str  # the source article's slug
    title: str  # the source article's title
    category: str
    source_name: str
    source_url: str
    as_of: int | None = None


def _sections(body: str) -> list[str]:
    """Split an article body into its intro and "## " sections, dropping the H1."""
    body = re.sub(r"^# .+\n", "", body.strip(), count=1).strip()
    starts = [m.start() for m in _HEADING.finditer(body)]
    bounds = [0, *starts, len(body)]
    parts = [body[a:b].strip() for a, b in zip(bounds, bounds[1:])]
    return [part for part in parts if part]


def _split_long(text: str, size: int, overlap: int) -> list[str]:
    """Split text into pieces of at most `size` characters at word boundaries."""
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            space = text.rfind(" ", start, end)
            if space > start:
                end = space
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        next_start = max(end - overlap, start + 1)
        space = text.find(" ", next_start, end)  # begin the overlap on a whole word
        start = space + 1 if space != -1 else next_start
    return [piece for piece in pieces if piece]


def chunk_article(article: Article, chunk_chars: int, chunk_overlap: int) -> list[Chunk]:
    if chunk_overlap >= chunk_chars:
        raise ValueError("chunk_overlap must be smaller than chunk_chars")

    # The title is added to every chunk so each one makes sense on its own.
    header = f"{article.title}\n\n"
    room = chunk_chars - len(header)

    pieces: list[str] = []
    current = ""
    for section in _sections(article.body):
        if len(section) > room:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_split_long(section, room, chunk_overlap))
        elif current and len(current) + 2 + len(section) > room:
            pieces.append(current)
            current = section
        else:
            current = f"{current}\n\n{section}" if current else section
    if current:
        pieces.append(current)

    return [
        Chunk(
            chunk_id=f"{article.slug}#{i}",
            text=header + piece,
            kind="article",
            slug=article.slug,
            title=article.title,
            category=article.category,
            source_name=article.source_name,
            source_url=article.source_url,
            as_of=article.as_of,
        )
        for i, piece in enumerate(pieces)
    ]


def chunk_glossary_term(term: GlossaryTerm, articles: dict[str, Article]) -> Chunk:
    """One chunk per term. Its citation is the related article, which has the source."""
    if not term.related_article or term.related_article not in articles:
        raise ValueError(f"glossary term {term.term!r} needs a related article to cite")
    article = articles[term.related_article]
    return Chunk(
        chunk_id=f"glossary:{term.term}",
        text=term.text,
        kind="glossary",
        slug=article.slug,
        title=article.title,
        category=term.category,
        source_name=article.source_name,
        source_url=article.source_url,
        as_of=article.as_of,
    )


def build_chunks(
    articles: list[Article], glossary: list[GlossaryTerm], chunk_chars: int, chunk_overlap: int
) -> list[Chunk]:
    by_slug = {article.slug: article for article in articles}
    chunks = [c for a in articles for c in chunk_article(a, chunk_chars, chunk_overlap)]
    chunks += [chunk_glossary_term(term, by_slug) for term in glossary]
    return chunks
