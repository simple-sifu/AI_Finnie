"""Story 6.4: source attribution on responses."""

import pytest

from src.core.models import Source, format_sources, sources_from
from src.rag.chunking import Chunk
from src.rag.retriever import RetrievedChunk


def hit(slug, score, kind="article", n=0, as_of=None):
    chunk = Chunk(
        chunk_id=f"{slug}#{n}" if kind == "article" else f"glossary:{slug}-{n}",
        text="...",
        kind=kind,
        slug=slug,
        title=slug.replace("-", " ").title(),
        category="Bonds",
        source_name="Investor.gov (U.S. SEC)",
        source_url=f"https://www.investor.gov/{slug}",
        as_of=as_of,
    )
    return RetrievedChunk(chunk, score)


def test_response_with_retrieved_content_lists_title_and_link():
    sources = sources_from([hit("bonds-basics", 0.8)])
    assert sources == [
        Source(
            title="Bonds Basics",
            url="https://www.investor.gov/bonds-basics",
            source_name="Investor.gov (U.S. SEC)",
            category="Bonds",
        )
    ]


def test_each_article_is_listed_once():
    retrieved = [
        hit("bonds-basics", 0.80, n=0),
        hit("bonds-basics", 0.70, n=1),  # second chunk of the same article
        hit("bonds-basics", 0.75, kind="glossary"),  # glossary term citing that article
        hit("bond-yield", 0.60),
    ]
    assert [s.url for s in sources_from(retrieved)] == [
        "https://www.investor.gov/bonds-basics",
        "https://www.investor.gov/bond-yield",
    ]


def test_only_retrieved_articles_appear_best_match_first():
    sources = sources_from([hit("bond-yield", 0.5), hit("i-bonds", 0.9)])
    assert [s.title for s in sources] == ["I Bonds", "Bond Yield"]


def test_no_retrieved_content_means_no_sources():
    assert sources_from([]) == []
    assert format_sources([]) == ""


def test_format_lists_each_source_with_its_link_and_year():
    text = format_sources(sources_from([hit("contribution-limits-2026", 0.9, as_of=2026), hit("roth-ira", 0.8)]))
    assert text.splitlines() == [
        "**Sources**",
        "- [Contribution Limits 2026](https://www.investor.gov/contribution-limits-2026) (as of 2026), "
        "Investor.gov (U.S. SEC)",
        "- [Roth Ira](https://www.investor.gov/roth-ira), Investor.gov (U.S. SEC)",
    ]


@pytest.mark.parametrize("question, expected_title", [("How much can I put in a Roth IRA in 2026?", "Roth IRAs")])
def test_real_retrieval_produces_real_citations(question, expected_title):
    """End to end with the real index: retrieved chunks become clickable government sources."""
    from src.rag.index import load_index, sentence_transformer_embedder
    from src.rag.retriever import Retriever

    retriever = Retriever(load_index(), sentence_transformer_embedder())
    sources = sources_from(retriever.search(question))
    titles = [s.title for s in sources]
    assert expected_title in titles
    assert len(titles) == len(set(titles)), "each article listed once"
    assert all(s.url.startswith("https://www.irs.gov/") for s in sources)
