"""Story 10.1: documentation deliverables required for evaluators."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
ARCHITECTURE = ROOT / "docs" / "architecture.md"
TECH = ROOT / "docs" / "technology-choices.md"

DOCSTRING_PACKAGES = ("src/agents", "src/workflow", "src/rag")


def _public_classes_without_docstrings(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    missing = []
    if not ast.get_docstring(tree):
        missing.append(f"{path}: module")
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            if not ast.get_docstring(node):
                missing.append(f"{path}:{node.name}")
    return missing


def test_readme_has_evaluator_sections():
    text = README.read_text()
    assert "## Architecture overview" in text
    assert "## Development setup" in text
    assert "## API and configuration" in text
    assert "## Usage examples" in text
    assert "## Troubleshooting" in text
    assert "docs/architecture.md" in text


def test_architecture_is_complete_with_diagrams():
    text = ARCHITECTURE.read_text()
    assert "status: final" in text
    assert "```mermaid" in text
    assert "RAG implementation" in text or "RAG" in text
    assert "Performance Considerations" in text or "NFR13" in text


def test_technology_choices_doc_exists():
    assert TECH.is_file()
    assert "LangGraph" in TECH.read_text()


def test_agent_workflow_and_rag_public_classes_have_docstrings():
    missing: list[str] = []
    for package in DOCSTRING_PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            missing.extend(_public_classes_without_docstrings(path))
    assert not missing, "missing docstrings:\n" + "\n".join(missing)
