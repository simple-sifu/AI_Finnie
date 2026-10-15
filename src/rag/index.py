"""Build, save and load the FAISS knowledge-base index (Story 6.1, architecture §8.2).

Files in src/data/index/:
- faiss.index: the vectors (normalized all-MiniLM-L6-v2 embeddings, inner product)
- chunks.json: chunk text and citation metadata, in the same order as the vectors
- manifest.json: model, settings, counts and a hash of the content used

Loading never re-embeds anything. If the content has changed since the build,
the index still loads, and `is_stale` tells the app to suggest a rebuild.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np

from src.rag.chunking import Chunk
from src.rag.content import ARTICLES_DIR, GLOSSARY_PATH

INDEX_DIR = Path(__file__).resolve().parents[1] / "data" / "index"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_FILE, CHUNKS_FILE, MANIFEST_FILE = "faiss.index", "chunks.json", "manifest.json"
REBUILD_HINT = "Run `python -m src.rag.build_index` to build it."

Embedder = Callable[[Sequence[str]], np.ndarray]


class IndexLoadError(Exception):
    """Raised when the saved index is missing or unreadable. The message is safe to show."""


@dataclass
class KnowledgeIndex:
    """Loaded FAISS index, chunk list and build manifest."""

    index: faiss.Index
    chunks: list[Chunk]
    manifest: dict

    @property
    def size(self) -> int:
        return self.index.ntotal


def content_hash(
    chunk_chars: int,
    chunk_overlap: int,
    articles_dir: Path = ARTICLES_DIR,
    glossary_path: Path = GLOSSARY_PATH,
    model: str = EMBEDDING_MODEL,
) -> str:
    """A fingerprint of everything that affects the index, used to detect a stale build."""
    digest = hashlib.sha256(f"{model}|{chunk_chars}|{chunk_overlap}".encode())
    for path in [*sorted(articles_dir.glob("*.md")), glossary_path]:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def sentence_transformer_embedder(model_name: str = EMBEDDING_MODEL) -> Embedder:
    """The real embedder: normalized vectors, so inner product equals cosine similarity."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)

    def embed(texts: Sequence[str]) -> np.ndarray:
        vectors = model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vectors, dtype="float32")

    return embed


def build_index(chunks: list[Chunk], embed: Embedder) -> faiss.Index:
    if not chunks:
        raise ValueError("cannot build an index from zero chunks")
    vectors = embed([chunk.text for chunk in chunks])
    if vectors.ndim != 2 or len(vectors) != len(chunks):
        raise ValueError("the embedder must return one vector per chunk")
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(np.ascontiguousarray(vectors, dtype="float32"))
    return index


def save_index(
    index: faiss.Index, chunks: list[Chunk], manifest: dict, directory: Path = INDEX_DIR
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(directory / INDEX_FILE))
    (directory / CHUNKS_FILE).write_text(
        json.dumps([asdict(chunk) for chunk in chunks], indent=1, ensure_ascii=False) + "\n"
    )
    (directory / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2) + "\n")


def make_manifest(chunks: list[Chunk], index: faiss.Index, chunk_chars: int, chunk_overlap: int) -> dict:
    return {
        "model": EMBEDDING_MODEL,
        "dimensions": index.d,
        "chunk_count": len(chunks),
        "article_chunks": sum(chunk.kind == "article" for chunk in chunks),
        "glossary_chunks": sum(chunk.kind == "glossary" for chunk in chunks),
        "chunk_chars": chunk_chars,
        "chunk_overlap": chunk_overlap,
        "content_hash": content_hash(chunk_chars, chunk_overlap),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def load_index(directory: Path = INDEX_DIR) -> KnowledgeIndex:
    """Load a saved index without re-embedding. Raises IndexLoadError if it can't be used."""
    paths = [directory / name for name in (INDEX_FILE, CHUNKS_FILE, MANIFEST_FILE)]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise IndexLoadError(f"The knowledge base index is missing ({', '.join(missing)}). {REBUILD_HINT}")
    try:
        index = faiss.read_index(str(paths[0]))
        chunks = [Chunk(**item) for item in json.loads(paths[1].read_text())]
        manifest = json.loads(paths[2].read_text())
    except Exception as exc:  # faiss raises RuntimeError; json and Chunk raise others
        raise IndexLoadError(f"The knowledge base index could not be read. {REBUILD_HINT}") from exc
    if index.ntotal != len(chunks) or manifest.get("chunk_count") != len(chunks):
        raise IndexLoadError(f"The knowledge base index files don't match each other. {REBUILD_HINT}")
    return KnowledgeIndex(index, chunks, manifest)


def is_stale(knowledge: KnowledgeIndex, articles_dir: Path = ARTICLES_DIR, glossary_path: Path = GLOSSARY_PATH) -> bool:
    """True if the articles, glossary or chunk settings changed since the index was built."""
    manifest = knowledge.manifest
    current = content_hash(
        manifest.get("chunk_chars", 0), manifest.get("chunk_overlap", 0), articles_dir, glossary_path
    )
    return manifest.get("content_hash") != current
