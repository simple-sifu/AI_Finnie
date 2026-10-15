"""Story 6.3: the retrieval pipeline with relevance scoring."""

import asyncio
import threading

import numpy as np
import pytest

from src.rag.chunking import Chunk
from src.rag.index import build_index
from src.rag.retriever import NO_VERIFIED_CONTENT, Retriever

TEXTS = ["alpha", "beta", "gamma", "delta", "epsilon"]


def unit(i, dims=8):
    v = np.zeros(dims, dtype="float32")
    v[i] = 1.0
    return v


def fake_embed(texts):
    """Each known word maps to its own axis; a query like 'alpha+beta' mixes two."""
    out = []
    for text in texts:
        parts = [TEXTS.index(p) for p in text.split("+") if p in TEXTS]
        v = sum((unit(i) for i in parts), np.zeros(8, dtype="float32")) if parts else unit(7)
        out.append(v / np.linalg.norm(v))
    return np.array(out, dtype="float32")


@pytest.fixture
def retriever():
    from src.rag.index import KnowledgeIndex

    chunks = [Chunk(f"c{i}", t, "article", t, t.title(), "Stocks", "Src", "https://x/") for i, t in enumerate(TEXTS)]
    knowledge = KnowledgeIndex(build_index(chunks, fake_embed), chunks, {"chunk_count": len(chunks)})
    return Retriever(knowledge, fake_embed, top_k=3, min_score=0.35)


def test_best_match_comes_first_with_its_score(retriever):
    results = retriever.search("gamma")
    assert results[0].chunk.slug == "gamma" and results[0].score == pytest.approx(1.0)


def test_low_scores_are_dropped(retriever):
    results = retriever.search("alpha+beta")  # these two tie at ~0.71; the rest score 0
    assert {r.chunk.slug for r in results} == {"alpha", "beta"}


def test_nothing_relevant_returns_empty(retriever):
    assert retriever.search("unrelated question") == []
    assert NO_VERIFIED_CONTENT.startswith("I don't have verified information")


def test_k_comes_from_settings_and_can_be_overridden():
    from src.rag.index import KnowledgeIndex

    chunks = [Chunk(f"c{i}", t, "article", t, t, "Stocks", "S", "https://x/") for i, t in enumerate(TEXTS)]
    knowledge = KnowledgeIndex(build_index(chunks, fake_embed), chunks, {})
    r = Retriever(knowledge, fake_embed, top_k=2, min_score=-1)
    assert len(r.search("alpha")) == 2
    assert len(r.search("alpha", k=4)) == 4
    assert len(r.search("alpha", k=50)) == 5  # never more than the index holds


@pytest.mark.parametrize("query", ["", "   "])
def test_empty_query_returns_empty(retriever, query):
    assert retriever.search(query) == []


def test_retrieve_is_async_and_runs_off_the_event_loop(retriever):
    seen = {}
    original = retriever.search

    def spy(query, k=None, categories=None):
        seen["thread"] = threading.current_thread()
        return original(query, k, categories)

    retriever.search = spy

    async def run():
        seen["loop_thread"] = threading.current_thread()
        return await retriever.retrieve("delta")

    results = asyncio.run(run())
    assert results[0].chunk.slug == "delta"
    assert seen["thread"] is not seen["loop_thread"]


def test_warm_up_calls_the_embedder_once():
    calls = []
    r = Retriever(None, lambda texts: calls.append(texts) or np.zeros((1, 8), dtype="float32"))
    r.warm_up()
    assert calls == [["warm up"]]


# Story 6.5: category filtering


@pytest.fixture
def mixed():
    """Five chunks: alpha/beta/gamma are Stocks, delta/epsilon are Bonds."""
    from src.rag.index import KnowledgeIndex

    categories = ["Stocks", "Stocks", "Stocks", "Bonds", "Bonds"]
    chunks = [Chunk(f"c{i}", t, "article", t, t, c, "S", "https://x/") for i, (t, c) in enumerate(zip(TEXTS, categories))]
    knowledge = KnowledgeIndex(build_index(chunks, fake_embed), chunks, {})
    return Retriever(knowledge, fake_embed, top_k=3, min_score=0.35)


def test_unfiltered_search_covers_all_categories(mixed):
    assert {r.chunk.slug for r in mixed.search("alpha+delta")} == {"alpha", "delta"}


def test_filter_keeps_only_listed_categories(mixed):
    assert [r.chunk.slug for r in mixed.search("alpha+delta", categories=["Bonds"])] == ["delta"]
    assert {r.chunk.slug for r in mixed.search("alpha+delta", categories=["Stocks", "Bonds"])} == {"alpha", "delta"}


def test_filter_finds_matches_outside_the_unfiltered_top_k(mixed):
    mixed.top_k = 1  # unfiltered, only "alpha" would make the cut
    assert [r.chunk.slug for r in mixed.search("alpha+delta", categories=["Bonds"])] == ["delta"]


def test_filter_with_no_match_returns_empty(mixed):
    assert mixed.search("alpha", categories=["Bonds"]) == []


def test_a_single_category_string_is_accepted(mixed):
    assert [r.chunk.slug for r in mixed.search("delta", categories="Bonds")] == ["delta"]


@pytest.mark.parametrize("bad", [["Crypto"], ["Bonds", "bonds"], "Real Estate"])
def test_unknown_category_raises_a_clear_error(mixed, bad):
    from src.rag.retriever import UnknownCategoryError

    with pytest.raises(UnknownCategoryError, match="Unknown category.*Use one of: Investing Basics"):
        mixed.search("alpha", categories=bad)


def test_async_retrieve_passes_the_filter(mixed):
    results = asyncio.run(mixed.retrieve("alpha+delta", categories=["Bonds"]))
    assert [r.chunk.slug for r in results] == ["delta"]
