"""Load and validate knowledge-base articles (Stories 2.1 and 2.2).

Each article is a Markdown file with YAML front matter: title, category,
source_name, source_url and, for year-specific figures, as_of.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import re

import yaml

from src.core.categories import CATEGORIES, is_category

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ARTICLES_DIR = DATA_DIR / "articles"
GLOSSARY_PATH = DATA_DIR / "glossary.yaml"
MIN_ARTICLES, MAX_ARTICLES = 50, 100
REQUIRED_FIELDS = ("title", "category", "source_name", "source_url")
MIN_GLOSSARY_TERMS = 50
MAX_DEFINITION_SENTENCES = 3
# Sentence ends: . ! or ? followed by a space or the end, but not after a single
# capital letter, so abbreviations like "U.S." are not counted ("IRA." still is).
_SENTENCE_END = re.compile(r"(?<!\b[A-Z])[.!?](?=\s|$)")


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


@dataclass(frozen=True)
class GlossaryTerm:
    term: str
    definition: str
    category: str
    related_article: str | None = None

    @property
    def text(self) -> str:
        """The text indexed for retrieval, as one chunk per term (architecture §8.2)."""
        return f"{self.term}: {self.definition}"


def count_sentences(text: str) -> int:
    return len(_SENTENCE_END.findall(text.strip()))


def load_glossary(
    path: Path = GLOSSARY_PATH, articles_dir: Path = ARTICLES_DIR
) -> list[GlossaryTerm]:
    """Load and check the glossary. Raises ContentError on any problem."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ContentError(f"{path.name}: cannot be read as YAML") from exc
    entries = data.get("terms") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ContentError(f"{path.name}: expected a 'terms:' list")

    slugs = {p.stem for p in articles_dir.glob("*.md")}
    terms: list[GlossaryTerm] = []
    seen: set[str] = set()
    for entry in entries:
        name = str(entry.get("term", "")).strip() if isinstance(entry, dict) else ""
        if not name:
            raise ContentError(f"{path.name}: an entry is missing its term")
        where = f"{path.name}: {name!r}"
        if name.lower() in seen:
            raise ContentError(f"{where} appears more than once")
        seen.add(name.lower())

        definition = str(entry.get("definition") or "").strip()
        sentences = count_sentences(definition)
        if not 1 <= sentences <= MAX_DEFINITION_SENTENCES:
            raise ContentError(f"{where} needs a 1-3 sentence definition, found {sentences}")
        if not is_category(entry.get("category")):
            raise ContentError(f"{where} has unknown category {entry.get('category')!r}")
        related = entry.get("related_article")
        if related is not None and related not in slugs:
            raise ContentError(f"{where} links to missing article {related!r}")

        terms.append(GlossaryTerm(name, definition, entry["category"], related))

    if len(terms) < MIN_GLOSSARY_TERMS:
        raise ContentError(f"{path.name}: expected at least {MIN_GLOSSARY_TERMS} terms, found {len(terms)}")
    return terms
