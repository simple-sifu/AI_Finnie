"""Story 6.2: chunking articles and glossary terms."""

import pytest

from src.core.config import RAGSettings
from src.rag.chunking import build_chunks, chunk_article, chunk_glossary_term
from src.rag.content import Article, GlossaryTerm, load_articles, load_glossary

DEFAULTS = RAGSettings()


def article(body, slug="test", title="Test Article"):
    return Article(slug, title, "Stocks", "Investor.gov (U.S. SEC)", "https://www.investor.gov/", body)


@pytest.fixture(scope="module")
def real_chunks():
    return build_chunks(load_articles(), load_glossary(), DEFAULTS.chunk_chars, DEFAULTS.chunk_overlap)


def test_no_empty_chunks_and_complete_metadata(real_chunks):
    for chunk in real_chunks:
        assert chunk.text.strip()
        for field in ("chunk_id", "slug", "title", "category", "source_name", "source_url"):
            assert getattr(chunk, field), f"{chunk.chunk_id}: missing {field}"


def test_chunk_ids_are_unique(real_chunks):
    ids = [chunk.chunk_id for chunk in real_chunks]
    assert len(ids) == len(set(ids))


def test_article_chunks_respect_the_configured_size(real_chunks):
    assert all(len(c.text) <= DEFAULTS.chunk_chars for c in real_chunks if c.kind == "article")


def test_every_article_and_glossary_term_is_chunked(real_chunks):
    assert {c.slug for c in real_chunks if c.kind == "article"} == {a.slug for a in load_articles()}
    assert sum(c.kind == "glossary" for c in real_chunks) == len(load_glossary())


def test_each_chunk_starts_with_its_title_and_drops_the_h1():
    chunks = chunk_article(article("# Test Article\n\nIntro.\n\n## Part\n\nMore."), 800, 100)
    assert len(chunks) == 1
    assert chunks[0].text == "Test Article\n\nIntro.\n\n## Part\n\nMore."


def test_sections_are_packed_up_to_the_size_limit():
    sections = "\n\n".join(f"## Part {i}\n\n" + "word " * 30 for i in range(6))
    chunks = chunk_article(article(sections), 400, 50)
    assert len(chunks) > 1
    assert all(len(c.text) <= 400 for c in chunks)
    assert all(c.text.startswith("Test Article\n\n## Part") for c in chunks)


def test_long_section_is_split_with_overlap():
    words = " ".join(f"w{i}" for i in range(200))
    chunks = chunk_article(article(f"## Long\n\n{words}"), 300, 60)
    assert len(chunks) > 2 and all(len(c.text) <= 300 for c in chunks)
    first, second = chunks[0].text.split(), chunks[1].text.split()
    assert first[-1] in second, "consecutive pieces should share overlapping words"
    body_words = set(words.split())
    for chunk in chunks:  # pieces break between words, never inside one
        assert set(chunk.text.split("\n\n")[-1].split()) <= body_words | {"##", "Long"}


def test_smaller_chunk_size_gives_more_chunks():
    articles, glossary = load_articles(), load_glossary()
    assert len(build_chunks(articles, glossary, 400, 50)) > len(build_chunks(articles, glossary, 800, 100))


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError, match="smaller"):
        chunk_article(article("Text."), 100, 100)


def test_glossary_term_is_one_chunk_citing_its_related_article():
    source = article("Body.", slug="bonds-basics", title="What Is a Bond?")
    term = GlossaryTerm("Coupon", "The interest rate a bond pays.", "Bonds", "bonds-basics")
    chunk = chunk_glossary_term(term, {"bonds-basics": source})
    assert chunk.text == "Coupon: The interest rate a bond pays."
    assert chunk.kind == "glossary" and chunk.category == "Bonds"
    assert chunk.title == "What Is a Bond?" and chunk.source_url == source.source_url


def test_glossary_term_without_a_citable_article_fails():
    term = GlossaryTerm("Orphan", "No article.", "Bonds", None)
    with pytest.raises(ValueError, match="related article"):
        chunk_glossary_term(term, {})


def test_as_of_year_is_carried_to_chunks(real_chunks):
    limits = [c for c in real_chunks if c.slug == "contribution-limits-2026" and c.kind == "article"]
    assert limits and all(c.as_of == 2026 for c in limits)
