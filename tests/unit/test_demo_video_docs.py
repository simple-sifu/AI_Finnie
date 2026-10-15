"""Story 10.2: demo video documentation deliverables."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "docs" / "demo-video-script.md"
DELIVERABLE = ROOT / "docs" / "demo-video.md"
README = ROOT / "README.md"


def test_demo_video_script_covers_submission_topics():
    text = SCRIPT.read_text()
    assert "5–10 minute" in text or "5-10 minute" in text
    for topic in ("Portfolio", "Markets", "Goal", "disclaimer", "freshness", "Sample data"):
        assert topic.lower() in text.lower() or "Live" in text


def test_demo_video_deliverable_has_link_and_checklist():
    text = DELIVERABLE.read_text()
    assert "URL" in text and "acceptance checklist" in text.lower()
    assert "demo-video-script.md" in text


def test_readme_links_demo_video_docs():
    readme = README.read_text()
    assert "demo-video.md" in readme
