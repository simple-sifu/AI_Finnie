"""Search the knowledge base (Story 6.3, architecture §8.3).

Agents call `Retriever.retrieve` only when they need grounded content (D-22);
it is never run automatically on every query. Embedding and FAISS search are
CPU-bound, so they run in a worker thread to keep the event loop free (D-17).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import numpy as np

from src.rag.chunking import Chunk
from src.rag.index import Embedder, KnowledgeIndex

# Shown by agents when nothing relevant is found (front-end spec §6).
NO_VERIFIED_CONTENT = "I don't have verified information on that topic yet, so I'd rather not guess."


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

    def search(self, query: str, k: int | None = None) -> list[RetrievedChunk]:
        """Synchronous search: the top-k chunks scoring at least min_score, best first."""
        query = query.strip()
        k = k or self.top_k
        if not query or k < 1:
            return []
        vector = np.ascontiguousarray(self.embed([query]), dtype="float32")
        scores, ids = self.knowledge.index.search(vector, min(k, self.knowledge.size))
        return [
            RetrievedChunk(self.knowledge.chunks[i], float(score))
            for score, i in zip(scores[0], ids[0])
            if i != -1 and score >= self.min_score
        ]

    async def retrieve(self, query: str, k: int | None = None) -> list[RetrievedChunk]:
        """Async search for agents. Returns an empty list when nothing is relevant enough."""
        return await asyncio.to_thread(self.search, query, k)
