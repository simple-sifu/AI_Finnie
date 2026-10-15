"""Story 2.1: the curated financial education articles."""

from pathlib import Path

import pytest
import yaml

ARTICLES = Path(__file__).resolve().parents[2] / "src" / "data" / "articles"
FILES = sorted(ARTICLES.glob("*.md"))
REQUIRED_FIELDS = ("title", "category", "source_name", "source_url")


def parse(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    assert text.startswith("---\n"), f"{path.name}: missing front matter"
    _, front, body = text.split("---\n", 2)
    return yaml.safe_load(front), body


def test_article_count_is_between_50_and_100():
    assert 50 <= len(FILES) <= 100


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_article_has_complete_front_matter(path):
    meta, body = parse(path)
    for field in REQUIRED_FIELDS:
        assert meta.get(field), f"{path.name}: missing {field}"
    assert meta["source_url"].startswith("https://")
    assert body.strip().startswith(f"# {meta['title']}"), f"{path.name}: H1 must match title"
    assert len(body.split()) >= 100, f"{path.name}: article is too short"


def test_titles_are_unique():
    titles = [parse(path)[0]["title"] for path in FILES]
    assert len(titles) == len(set(titles))


@pytest.mark.parametrize(
    "slug",
    [
        "compound-interest",  # [FAQ Domain 1]
        "diversification",  # [FAQ Domain 1]
        "etfs-vs-mutual-funds",  # [PB]
        "401k-basics",  # [PB]
        "traditional-ira",  # [PB]
        "roth-ira",  # [PB]
    ],
)
def test_required_topics_are_covered(slug):
    assert (ARTICLES / f"{slug}.md").is_file()


def test_year_specific_figures_carry_an_as_of_year():
    # Story 4.3 AC 3: yearly tax figures come from the knowledge base with their year.
    for slug in ("contribution-limits-2026", "traditional-ira", "roth-ira"):
        meta, _ = parse(ARTICLES / f"{slug}.md")
        assert meta.get("as_of") == 2026, f"{slug}: missing as_of year"
