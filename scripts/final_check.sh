#!/usr/bin/env bash
# Story 10.4: one command to verify tests, UAT and NFR13 benchmarks before submission.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${PY:-python3.12}
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
fi

echo "==> Configuration"
"$PY" -m src.core.config

echo "==> Full test suite (80% coverage gate)"
"$PY" -m pytest -q

echo "==> UAT scenarios (offline)"
"$PY" -m pytest -k uat --cov-fail-under=0 -q

echo "==> Performance benchmarks (NFR13)"
"$PY" scripts/benchmark.py

echo ""
echo "Final check passed."
