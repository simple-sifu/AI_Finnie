"""Story 10.4: final polish documentation and check script."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "docs" / "final-polish.md"
CHECK = ROOT / "scripts" / "final_check.sh"


def test_final_polish_doc_records_acceptance_criteria():
    text = FINAL.read_text()
    assert "Story 10.4" in text
    assert "blocking" in text.lower()
    assert "pytest -k uat" in text or "uat" in text
    assert "80%" in text or "coverage" in text.lower()


def test_final_check_script_exists_and_runs_verification_steps():
    assert CHECK.is_file() and CHECK.stat().st_mode & 0o111
    subprocess.run(["bash", "-n", str(CHECK)], check=True)
    body = CHECK.read_text()
    assert "pytest" in body and "uat" in body and "benchmark.py" in body
