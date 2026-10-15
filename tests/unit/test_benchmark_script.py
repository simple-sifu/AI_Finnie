"""Story 9.4: benchmark script runs and reports NFR13 targets."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "benchmark.py"


def test_benchmark_script_writes_results(tmp_path):
    out = tmp_path / "benchmarks.md"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    text = out.read_text()
    assert "Performance benchmarks (NFR13)" in text
    assert "| Pass |" in text or "**Pass**" in text
    assert "App startup" in text
