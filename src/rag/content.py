"""Load and validate knowledge-base articles (Stories 2.1 and 2.2).

Each article is a Markdown file with YAML front matter: title, category,
source_name, source_url and, for year-specific figures, as_of.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.core.categories import CATEGORIES, is_category

ARTICLES_DIR = Path(__file__).resolve().parents[1] / "data" / "articles"
MIN_ARTICLES, MAX_ARTICLES = 50, 100
REQUIRED_FIELDS = ("title", "category", "source_name", "source_url")


class ContentError(Exception):
    """Raised when knowledge-base content is missing or invalid."""


@dataclass(frozen=True)
class Article:
    slug: str
    title: str
    category: str
    source_name: str
    source_url: str
    body: str
    as_of: int | None = None


def parse_article(path: Path) -> Article:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or text.count("---\n") < 2:
        raise ContentError(f"{path.name}: missing front matter")
    _, front, body = text.split("---\n", 2)
    try:
        meta = yaml.safe_load(front) or {}
    except yaml.YAMLError as exc:
        raise ContentError(f"{path.name}: front matter is not valid YAML") from exc
    if not isinstance(meta, dict):
        raise ContentError(f"{path.name}: front matter must be key: value pairs")

    missing = [field for field in REQUIRED_FIELDS if not meta.get(field)]
    if missing:
        raise ContentError(f"{path.name}: missing {', '.join(missing)}")
    if isinstance(meta["category"], list):
        raise ContentError(f"{path.name}: an article must have exactly one category")
    if not is_category(meta["category"]):
        raise ContentError(
            f"{path.name}: unknown category {meta['category']!r}; "
            f"use one of: {', '.join(CATEGORIES)}"
        )

    return Article(
        slug=path.stem,
        title=str(meta["title"]),
        category=meta["category"],
        source_name=str(meta["source_name"]),
        source_url=str(meta["source_url"]),
        body=body.strip(),
        as_of=meta.get("as_of"),
    )


def load_articles(directory: Path = ARTICLES_DIR) -> list[Article]:
    """Load every article and check the collection. Raises ContentError on any problem."""
    paths = sorted(directory.glob("*.md"))
    if not MIN_ARTICLES <= len(paths) <= MAX_ARTICLES:
        raise ContentError(
            f"expected {MIN_ARTICLES}-{MAX_ARTICLES} articles in {directory.name}/, found {len(paths)}"
        )
    return [parse_article(path) for path in paths]
