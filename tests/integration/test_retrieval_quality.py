"""Story 6.3 AC 4: retrieval quality on the real index with the real embedding model.

Loads all-MiniLM-L6-v2 (downloaded on first use), so it takes a few seconds.
"""

from pathlib import Path

import pytest
import yaml

from src.core.config import RAGSettings
from src.rag.index import load_index, sentence_transformer_embedder
from src.rag.retriever import Retriever

EVAL = yaml.safe_load((Path(__file__).parents[1] / "fixtures" / "retrieval_eval.yaml").read_text())
SETTINGS = RAGSettings()  # the configured defaults: top_k 4, min_score 0.35


@pytest.fixture(scope="module")
def retriever():
    return Retriever(load_index(), sentence_transformer_embedder(), SETTINGS.top_k, SETTINGS.min_score)


def test_test_set_has_at_least_20_questions():
    assert len(EVAL["questions"]) >= 20


def test_expected_article_is_in_top_k_for_at_least_80_percent(retriever):
    misses = []
    for item in EVAL["questions"]:
        slugs = [r.chunk.slug for r in retriever.search(item["question"])]
        if item["expected"] not in slugs:
            misses.append(f"{item['question']} -> {slugs}")
    hit_rate = 1 - len(misses) / len(EVAL["questions"])
    assert hit_rate >= 0.8, f"hit rate {hit_rate:.0%}; misses: {misses}"


@pytest.mark.parametrize("question", EVAL["off_topic"])
def test_off_topic_questions_find_nothing(retriever, question):
    assert retriever.search(question) == []


def test_tax_filter_returns_only_retirement_and_tax_content(retriever):
    """Story 6.5 example: the Tax Education Agent searches only its category."""
    results = retriever.search("How are my investments taxed?", categories=["Retirement & Tax Accounts"])
    assert results
    assert {r.chunk.category for r in results} == {"Retirement & Tax Accounts"}
