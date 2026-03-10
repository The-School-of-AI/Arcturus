#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: ci/run_project_gate.sh <ci-check-name> <acceptance-test-path> <integration-test-path> [lint-paths]"
  exit 1
fi

CHECK_NAME="$1"
ACCEPTANCE_PATH="$2"
INTEGRATION_PATH="$3"
LINT_PATHS="${4:-}"   # Optional — space-separated paths to lint/typecheck

if [[ ! -f "$ACCEPTANCE_PATH" ]]; then
  echo "Missing acceptance test file: $ACCEPTANCE_PATH"
  exit 1
fi

if [[ ! -f "$INTEGRATION_PATH" ]]; then
  echo "Missing integration test file: $INTEGRATION_PATH"
  exit 1
fi

# ---------------------------------------------------------------------------
# Lint / typecheck (only when LINT_PATHS is provided)
# ---------------------------------------------------------------------------
if [[ -n "$LINT_PATHS" ]]; then
  echo "[gate:$CHECK_NAME] Running ruff lint on: $LINT_PATHS"
  # shellcheck disable=SC2086  # word-splitting of LINT_PATHS is intentional
  python -m ruff check $LINT_PATHS

  echo "[gate:$CHECK_NAME] Running mypy typecheck on: $LINT_PATHS"
  # shellcheck disable=SC2086
  python -m mypy $LINT_PATHS
fi

# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------
echo "[gate:$CHECK_NAME] Running project contract tests"
python -m pytest -q "$ACCEPTANCE_PATH" "$INTEGRATION_PATH"

# ---------------------------------------------------------------------------
# Baseline regression
# ---------------------------------------------------------------------------
echo "[gate:$CHECK_NAME] Running baseline regression"
./scripts/test_all.sh quick
