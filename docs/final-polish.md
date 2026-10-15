---
title: Finnie — Final Polish Sign-Off
story: 10.4
status: final
---

# Final polish (Story 10.4)

Sign-off that Finnie v1 is stable for submission (Epic 10).

| Field | Value |
|---|---|
| **Date** | 2026-10-15 |
| **Git ref** | `main` after Story 10.3 merge |
| **Owner** | PM / dev sign-off |

## Story 10.4 acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | All known **blocking** bugs fixed | **Pass** | Issues log below is empty; no open blockers in UAT or tests |
| 2 | All tests pass, coverage ≥ 80% (D-13) | **Pass** | `pytest` — 1821 passed, ~99.75% line coverage |
| 3 | UAT script (Story 9.3) passes on final run | **Pass** | `pytest -k uat --cov-fail-under=0` — 28 passed; [`uat-results.md`](uat-results.md) |

## Final verification commands

Run from repo root with Python 3.12 and dependencies installed:

```bash
./scripts/final_check.sh
```

Or manually:

```bash
pytest
pytest -k uat --cov-fail-under=0
python scripts/benchmark.py    # refreshes docs/benchmarks.md
python -m src.core.config     # Configuration OK
```

## Known issues (blocking)

| ID | Area | Description | Status |
|---|---|---|---|
| — | — | None | — |

## Known issues (non-blocking)

| ID | Area | Description |
|---|---|---|
| NB-1 | Demo video | MP4 not in repo; add URL to [`demo-video.md`](demo-video.md) after recording (Story 10.2) |
| NB-2 | Docker image | Large download (PyTorch); first `docker compose build` needs network and time |

## Submission deliverables (cross-check)

| Deliverable | Location |
|---|---|
| Working prototype | `streamlit run src/web_app/app.py` or Docker |
| README + architecture | [`README.md`](../README.md), [`architecture.md`](architecture.md) |
| Tests + coverage | `pytest`, `tests/` |
| UAT | [`uat-script.md`](uat-script.md), [`uat-results.md`](uat-results.md) |
| Benchmarks | [`benchmarks.md`](benchmarks.md) |
| Deployment | [`deployment.md`](deployment.md), `Dockerfile`, `.env.example` |
| Demo video | [`demo-video.md`](demo-video.md) (link TBD) |

Epic 10 code stories **10.1–10.3** and **10.4** (this sign-off) are complete when this document and CI/local `final_check` pass.
