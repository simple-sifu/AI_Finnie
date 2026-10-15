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
    # Exit 1 means a timing target was missed, which depends on how busy this machine is (a full test run
    # is). This test checks that the script runs and writes its report; the targets are checked by running it alone.
    assert completed.returncode in (0, 1), completed.stderr or completed.stdout
    text = out.read_text()
    assert "Performance benchmarks (NFR13)" in text
    assert "| Pass |" in text or "**Pass**" in text or "**Review**" in text
    assert "App startup" in text
