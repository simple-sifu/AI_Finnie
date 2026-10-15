"""Rebuild the knowledge-base index: `python -m src.rag.build_index` (Story 6.1).

Run this whenever articles, the glossary or the rag: chunk settings change.
It needs no API keys. The first run downloads the embedding model (about 90 MB).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from src.core.config import ConfigError, load_rag_settings
from src.rag.chunking import build_chunks
from src.rag.content import ContentError, load_articles, load_glossary
from src.rag.index import (
    INDEX_DIR,
    Embedder,
    build_index,
    make_manifest,
    save_index,
    sentence_transformer_embedder,
)


def rebuild(directory: Path = INDEX_DIR, embed: Embedder | None = None) -> dict:
    """Load and validate content, chunk it, embed it and save the index. Returns the manifest."""
    rag = load_rag_settings()
    chunks = build_chunks(load_articles(), load_glossary(), rag.chunk_chars, rag.chunk_overlap)
    index = build_index(chunks, embed or sentence_transformer_embedder())
    manifest = make_manifest(chunks, index, rag.chunk_chars, rag.chunk_overlap)
    save_index(index, chunks, manifest, directory)
    return manifest


def main() -> int:
    started = time.perf_counter()
    try:
        manifest = rebuild()
    except (ConfigError, ContentError) as exc:
        print(f"Index not built: {exc}", file=sys.stderr)
        return 1
    print(
        f"Built index: {manifest['chunk_count']} chunks "
        f"({manifest['article_chunks']} article, {manifest['glossary_chunks']} glossary), "
        f"{manifest['dimensions']} dimensions, in {time.perf_counter() - started:.1f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
