"""Story 6.1: build, save and load the FAISS index."""

import hashlib
import json
import shutil

import numpy as np
import pytest

from src.rag import build_index as build_cmd
from src.rag.chunking import Chunk
from src.rag.content import ARTICLES_DIR, GLOSSARY_PATH
from src.rag.index import (
    INDEX_DIR,
    IndexLoadError,
    build_index,
    content_hash,
    is_stale,
    load_index,
    make_manifest,
    save_index,
)


def fake_embed(texts):
    """Deterministic stand-in for the real model: one normalized vector per text."""
    vectors = []
    for text in texts:
        seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        vector = np.random.default_rng(seed).normal(size=16)
        vectors.append(vector / np.linalg.norm(vector))
    return np.array(vectors, dtype="float32")


def chunk(i):
    return Chunk(f"c{i}", f"text number {i}", "article", "slug", "Title", "Stocks", "Src", "https://x/")


@pytest.fixture
def saved(tmp_path):
    chunks = [chunk(i) for i in range(5)]
    index = build_index(chunks, fake_embed)
    save_index(index, chunks, make_manifest(chunks, index, 800, 100), tmp_path)
    return tmp_path, chunks


def test_round_trip_without_re_embedding(saved):
    directory, chunks = saved
    knowledge = load_index(directory)
    assert knowledge.size == 5 and knowledge.chunks == chunks
    scores, ids = knowledge.index.search(fake_embed(["text number 3"]), 1)
    assert ids[0][0] == 3 and scores[0][0] == pytest.approx(1.0, abs=1e-5)


@pytest.mark.parametrize("name", ["faiss.index", "chunks.json", "manifest.json"])
def test_missing_file_gives_a_clear_error(saved, name):
    directory, _ = saved
    (directory / name).unlink()
    with pytest.raises(IndexLoadError, match=f"missing.*{name}.*build_index"):
        load_index(directory)


@pytest.mark.parametrize("name", ["faiss.index", "chunks.json", "manifest.json"])
def test_unreadable_file_gives_a_clear_error(saved, name):
    directory, _ = saved
    (directory / name).write_text("not valid content")
    with pytest.raises(IndexLoadError, match="could not be read|don't match"):
        load_index(directory)


def test_mismatched_files_are_rejected(saved):
    directory, chunks = saved
    (directory / "chunks.json").write_text(json.dumps([vars(c) for c in chunks[:3]]))
    with pytest.raises(IndexLoadError, match="don't match"):
        load_index(directory)


def test_build_rejects_bad_input():
    with pytest.raises(ValueError, match="zero chunks"):
        build_index([], fake_embed)
    with pytest.raises(ValueError, match="one vector per chunk"):
        build_index([chunk(1), chunk(2)], lambda texts: fake_embed(texts[:1]))


def test_content_hash_changes_when_content_changes(tmp_path):
    articles = tmp_path / "articles"
    shutil.copytree(ARTICLES_DIR, articles)
    before = content_hash(800, 100, articles, GLOSSARY_PATH)
    assert content_hash(600, 100, articles, GLOSSARY_PATH) != before
    path = articles / "compound-interest.md"
    path.write_text(path.read_text() + "\nOne more sentence.\n")
    assert content_hash(800, 100, articles, GLOSSARY_PATH) != before


def test_rebuild_command_builds_from_real_content(tmp_path, monkeypatch):
    monkeypatch.setattr(build_cmd, "sentence_transformer_embedder", lambda: fake_embed)
    manifest = build_cmd.rebuild(tmp_path)
    knowledge = load_index(tmp_path)
    assert manifest["chunk_count"] == knowledge.size == len(knowledge.chunks)
    assert manifest["article_chunks"] > 0 and manifest["glossary_chunks"] > 0
    assert not is_stale(knowledge)


def test_main_reports_success(monkeypatch, capsys):
    manifest = {"chunk_count": 3, "article_chunks": 2, "glossary_chunks": 1, "dimensions": 16}
    monkeypatch.setattr(build_cmd, "rebuild", lambda: manifest)
    assert build_cmd.main() == 0
    assert "Built index: 3 chunks" in capsys.readouterr().out


def test_main_reports_bad_content(monkeypatch, capsys):
    from src.rag.content import ContentError

    def fail():
        raise ContentError("a000.md: unknown category 'Crypto'")

    monkeypatch.setattr(build_cmd, "rebuild", fail)
    assert build_cmd.main() == 1
    assert "Crypto" in capsys.readouterr().err


def test_committed_index_matches_current_content():
    """Fails if articles, the glossary or chunk settings changed without a rebuild."""
    knowledge = load_index(INDEX_DIR)
    assert knowledge.manifest["dimensions"] == 384
    assert not is_stale(knowledge), "content changed: run `python -m src.rag.build_index`"


@pytest.mark.filterwarnings("ignore:'src.rag.build_index' found in sys.modules:RuntimeWarning")  # a runpy quirk
def test_python_m_build_index_builds_and_exits_zero(tmp_path, monkeypatch, capsys):
    import runpy

    monkeypatch.setattr("src.rag.index.sentence_transformer_embedder", lambda: fake_embed)  # no real model
    monkeypatch.setattr("src.rag.index.INDEX_DIR", tmp_path)  # never touch the committed index
    with pytest.raises(SystemExit) as result:
        runpy.run_module("src.rag.build_index", run_name="__main__")
    assert result.value.code == 0 and "Built index:" in capsys.readouterr().out
    assert load_index(tmp_path).size > 0
