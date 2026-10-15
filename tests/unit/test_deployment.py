"""Story 10.3: deployment artifacts for local evaluators."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "src" / "data" / "samples"


def test_env_and_requirements_exist():
    assert (ROOT / ".env.example").is_file()
    assert (ROOT / "requirements.txt").is_file()
    deps = [line for line in (ROOT / "requirements.txt").read_text().splitlines() if line and not line.startswith("#")]
    assert deps and all("==" in dep for dep in deps)


def test_sample_data_and_benchmarks_included():
    assert (SAMPLES / "diversified.csv").is_file()
    assert (ROOT / "docs" / "benchmarks.md").is_file()


def test_dockerfile_runs_streamlit_on_port_8501():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "python:3.12" in dockerfile
    assert "streamlit" in dockerfile and "src/web_app/app.py" in dockerfile
    assert "8501" in dockerfile
    assert (ROOT / "docker-compose.yml").is_file()
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "8501:8501" in compose and "env_file" in compose


def test_readme_covers_fresh_clone_and_docker():
    readme = (ROOT / "README.md").read_text()
    assert "git clone" in readme and "streamlit run src/web_app/app.py" in readme
    assert "docker compose" in readme.lower() or "Docker" in readme
    assert "docs/deployment.md" in readme
