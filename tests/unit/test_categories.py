"""Story 2.2: categories are fixed, and every article has exactly one valid category."""

from pathlib import Path

import pytest

from src.core.categories import CATEGORIES, is_category
from src.rag.content import ContentError, load_articles, parse_article

VALID = """---
title: "Test"
category: {category}
source_name: "Investor.gov (U.S. SEC)"
source_url: https://www.investor.gov/
---

# Test

Body text.
"""


def write_articles(directory: Path, count: int, category: str = "Stocks") -> None:
    for i in range(count):
        (directory / f"a{i:03}.md").write_text(VALID.format(category=category))


def test_category_list_matches_the_prd():
    assert CATEGORIES == (
        "Investing Basics",
        "Stocks",
        "Bonds",
        "ETFs & Mutual Funds",
        "Retirement & Tax Accounts",
        "Portfolio & Risk",
        "Markets",
        "Goals & Saving",
    )


def test_is_category():
    assert is_category("Bonds")
    assert not is_category("bonds")
    assert not is_category(None)


def test_real_articles_all_have_a_valid_category():
    articles = load_articles()
    assert all(article.category in CATEGORIES for article in articles)
    assert {article.category for article in articles} == set(CATEGORIES)  # every category used


def test_valid_article_parses(tmp_path):
    path = tmp_path / "ok.md"
    path.write_text(VALID.format(category='"ETFs & Mutual Funds"'))
    article = parse_article(path)
    assert article.category == "ETFs & Mutual Funds" and article.slug == "ok"


@pytest.mark.parametrize(
    "category_line, message",
    [
        ("category: Crypto", "unknown category"),
        ("category: [Stocks, Bonds]", "exactly one category"),
        ("category:", "missing category"),
    ],
)
def test_bad_category_fails(tmp_path, category_line, message):
    path = tmp_path / "bad.md"
    path.write_text(VALID.format(category="Stocks").replace("category: Stocks", category_line))
    with pytest.raises(ContentError, match=message):
        parse_article(path)


def test_missing_front_matter_fails(tmp_path):
    path = tmp_path / "bad.md"
    path.write_text("# No front matter\n")
    with pytest.raises(ContentError, match="missing front matter"):
        parse_article(path)


def test_invalid_yaml_fails(tmp_path):
    path = tmp_path / "bad.md"
    path.write_text("---\ntitle: [unclosed\n---\n# x\n")
    with pytest.raises(ContentError, match="not valid YAML"):
        parse_article(path)


def test_non_mapping_front_matter_fails(tmp_path):
    path = tmp_path / "bad.md"
    path.write_text("---\n- a\n- list\n---\n# x\n")
    with pytest.raises(ContentError, match="key: value"):
        parse_article(path)


@pytest.mark.parametrize("count", [49, 101])
def test_article_count_outside_50_to_100_fails(tmp_path, count):
    write_articles(tmp_path, count)
    with pytest.raises(ContentError, match="expected 50-100 articles"):
        load_articles(tmp_path)


def test_one_bad_article_fails_the_whole_load(tmp_path):
    write_articles(tmp_path, 50)
    (tmp_path / "a000.md").write_text(VALID.format(category="Crypto"))
    with pytest.raises(ContentError, match="a000.md"):
        load_articles(tmp_path)
