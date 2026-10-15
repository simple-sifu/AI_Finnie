"""Story 6.4 end to end: real index and embedding model, so retrieved chunks become real citations.

An integration test (not a unit test) because it loads the real embedding model.
"""

import pytest

from src.core.models import sources_from
from src.rag.index import load_index, sentence_transformer_embedder
from src.rag.retriever import Retriever


@pytest.mark.parametrize("question, expected_title", [("How much can I put in a Roth IRA in 2026?", "Roth IRAs")])
def test_real_retrieval_produces_real_citations(question, expected_title):
    retriever = Retriever(load_index(), sentence_transformer_embedder())
    titles = [s.title for s in sources_from(retriever.search(question))]
    assert expected_title in titles
    assert len(titles) == len(set(titles)), "each article listed once"
