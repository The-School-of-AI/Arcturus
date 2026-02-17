#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: ci/run_project_gate.sh <ci-check-name> <acceptance-test-path> <integration-test-path>"
  exit 1
fi

CHECK_NAME="$1"
ACCEPTANCE_PATH="$2"
INTEGRATION_PATH="$3"

if [[ ! -f "$ACCEPTANCE_PATH" ]]; then
  echo "Missing acceptance test file: $ACCEPTANCE_PATH"
  exit 1
fi

if [[ ! -f "$INTEGRATION_PATH" ]]; then
  echo "Missing integration test file: $INTEGRATION_PATH"
  exit 1
fi

echo "[gate:$CHECK_NAME] Running project contract tests"
python -m pytest -q "$ACCEPTANCE_PATH" "$INTEGRATION_PATH"

echo "[gate:$CHECK_NAME] Running baseline regression"
./scripts/test_all.sh quick
