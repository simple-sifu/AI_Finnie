"""Search the knowledge base (Story 6.3, architecture §8.3).

Agents call `Retriever.retrieve` only when they need grounded content (D-22);
it is never run automatically on every query. Embedding and FAISS search are
CPU-bound, so they run in a worker thread to keep the event loop free (D-17).
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from src.core.categories import CATEGORIES, is_category
from src.rag.chunking import Chunk
from src.rag.index import Embedder, KnowledgeIndex

# Shown by agents when nothing relevant is found (front-end spec §6).
NO_VERIFIED_CONTENT = "I don't have verified information on that topic yet, so I'd rather not guess."


class UnknownCategoryError(ValueError):
    """Raised when a retrieval filter names a category that doesn't exist."""


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float  # cosine similarity, higher is more relevant


class Retriever:
    def __init__(self, knowledge: KnowledgeIndex, embed: Embedder, top_k: int = 4, min_score: float = 0.35):
        self.knowledge = knowledge
        self.embed = embed
        self.top_k = top_k
        self.min_score = min_score

    def warm_up(self) -> None:
        """Run one embedding so the first real search isn't slowed by model start-up."""
        self.embed(["warm up"])

    def search(
        self, query: str, k: int | None = None, categories: Sequence[str] | None = None
    ) -> list[RetrievedChunk]:
        """Synchronous search: the top-k chunks scoring at least min_score, best first.

        With `categories`, only chunks in those categories are returned (Story 6.5).
        The filter is applied over every chunk, so a small category is never missed.
        """
        wanted = self._check_categories(categories)
        query = query.strip()
        k = k or self.top_k
        if not query or k < 1:
            return []
        vector = np.ascontiguousarray(self.embed([query]), dtype="float32")
        candidates = self.knowledge.size if wanted else min(k, self.knowledge.size)
        scores, ids = self.knowledge.index.search(vector, candidates)
        results = [
            RetrievedChunk(self.knowledge.chunks[i], float(score))
            for score, i in zip(scores[0], ids[0])
            if i != -1 and score >= self.min_score
            and (wanted is None or self.knowledge.chunks[i].category in wanted)
        ]
        return results[:k]

    async def retrieve(
        self, query: str, k: int | None = None, categories: Sequence[str] | None = None
    ) -> list[RetrievedChunk]:
        """Async search for agents. Returns an empty list when nothing is relevant enough."""
        return await asyncio.to_thread(self.search, query, k, categories)

    @staticmethod
    def _check_categories(categories: Sequence[str] | None) -> set[str] | None:
        if categories is None:
            return None
        if isinstance(categories, str):
            categories = [categories]
        unknown = [name for name in categories if not is_category(name)]
        if unknown:
            raise UnknownCategoryError(
                f"Unknown category {', '.join(map(repr, unknown))}. Use one of: {', '.join(CATEGORIES)}"
            )
        return set(categories)


def create_retriever(settings, warm_up: bool = True) -> Retriever:
    """Load the saved index and the embedding model, ready for agents (raises IndexLoadError)."""
    from src.rag.index import load_index, sentence_transformer_embedder

    retriever = Retriever(load_index(), sentence_transformer_embedder(), settings.rag.top_k, settings.rag.min_score)
    if warm_up:
        retriever.warm_up()
    return retriever
