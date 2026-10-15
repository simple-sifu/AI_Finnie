"""Story 2.3: the glossary of financial terms."""

import pytest

from src.core.categories import CATEGORIES
from src.rag.content import (
    ARTICLES_DIR,
    ContentError,
    count_sentences,
    load_glossary,
)


def entry(term="Bond", definition="A loan to a company.", category="Bonds", related="bonds-basics"):
    lines = [f"  - term: {term}", f"    definition: {definition}", f"    category: {category}"]
    if related:
        lines.append(f"    related_article: {related}")
    return "\n".join(lines)


def glossary_file(tmp_path, entries, extra=50):
    filler = [entry(term=f"Term {i}", related=None) for i in range(extra)]
    path = tmp_path / "glossary.yaml"
    path.write_text("terms:\n" + "\n".join([*entries, *filler]) + "\n")
    return path


def test_real_glossary_loads_with_at_least_50_terms():
    terms = load_glossary()
    assert len(terms) >= 50
    assert {t.category for t in terms} <= set(CATEGORIES)


def test_every_real_term_links_to_an_existing_article():
    slugs = {p.stem for p in ARTICLES_DIR.glob("*.md")}
    assert all(t.related_article in slugs for t in load_glossary() if t.related_article)


def test_terms_are_indexable_text():
    term = next(t for t in load_glossary() if t.term == "Expense ratio")
    assert term.text.startswith("Expense ratio: The yearly fee")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("One sentence.", 1),
        ("A loan to the U.S. government. It matures soon.", 2),
        ("Postponed, as in a traditional 401(k) or IRA.", 1),
        ("One. Two! Three?", 3),
        ("No ending punctuation", 0),
    ],
)
def test_count_sentences(text, expected):
    assert count_sentences(text) == expected


def test_valid_custom_glossary(tmp_path):
    terms = load_glossary(glossary_file(tmp_path, [entry()]), ARTICLES_DIR)
    assert terms[0].related_article == "bonds-basics"


@pytest.mark.parametrize(
    "bad, message",
    [
        (entry(category="Crypto"), "unknown category"),
        (entry(related="no-such-article"), "missing article"),
        (entry(definition="One. Two. Three. Four."), "1-3 sentence"),
        (entry(definition='""'), "1-3 sentence"),
        (entry(term='""'), "missing its term"),
    ],
)
def test_bad_entry_fails(tmp_path, bad, message):
    with pytest.raises(ContentError, match=message):
        load_glossary(glossary_file(tmp_path, [bad]), ARTICLES_DIR)


def test_duplicate_term_fails(tmp_path):
    with pytest.raises(ContentError, match="more than once"):
        load_glossary(glossary_file(tmp_path, [entry(), entry(term="bond")]), ARTICLES_DIR)


def test_fewer_than_50_terms_fails(tmp_path):
    with pytest.raises(ContentError, match="at least 50"):
        load_glossary(glossary_file(tmp_path, [entry()], extra=10), ARTICLES_DIR)


@pytest.mark.parametrize("text", ["terms: not-a-list\n", "- just\n- a list\n", "terms: [unclosed\n"])
def test_malformed_file_fails(tmp_path, text):
    path = tmp_path / "glossary.yaml"
    path.write_text(text)
    with pytest.raises(ContentError):
        load_glossary(path, ARTICLES_DIR)
