"""Story 1.4: the repository follows the prescribed structure (PRD §4.1)."""

from pathlib import Path

import src

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ["agents", "core", "rag", "web_app", "utils", "workflow"]


def test_package_version():
    assert src.__version__ == "0.1.0"


def test_prescribed_folders_exist():
    for folder in [*PACKAGES, "data"]:
        assert (ROOT / "src" / folder).is_dir(), f"missing src/{folder}"
    assert (ROOT / "tests").is_dir()
    assert (ROOT / "scripts").is_dir()
    assert (ROOT / "scripts" / "benchmark.py").is_file()


def test_prescribed_files_exist():
    for name in ["config.yaml", "requirements.txt", "README.md"]:
        assert (ROOT / name).is_file(), f"missing {name}"


def test_requirements_are_pinned():
    lines = (ROOT / "requirements.txt").read_text().splitlines()
    deps = [line for line in lines if line and not line.startswith("#")]
    assert deps, "requirements.txt is empty"
    assert all("==" in dep for dep in deps), "every dependency must be pinned with =="
