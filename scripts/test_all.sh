#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-quick}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_backend() {
  echo "[backend] Running Python test suite"
  (
    cd "$ROOT_DIR"
    python -m pytest -q tests --ignore=tests/stress_tests
  )
}

run_frontend() {
  echo "[frontend] Running Vitest suite"
  (
    cd "$ROOT_DIR/platform-frontend"
    npm run test -- --reporter=dot
  )
}

run_stress() {
  echo "[stress] Running stress tests"
  local marker_expr="stress and not integration and not external"
  if [[ "${RUN_STRESS_INTEGRATION:-0}" == "1" ]]; then
    marker_expr="stress"
  fi
  (
    cd "$ROOT_DIR"
    python -m pytest -q tests/stress_tests -m "$marker_expr"
  )
}

case "$MODE" in
  quick)
    run_backend
    run_frontend
    ;;
  backend)
    run_backend
    ;;
  frontend)
    run_frontend
    ;;
  full)
    run_backend
    run_frontend
    if [[ "${RUN_STRESS_TESTS:-0}" == "1" ]]; then
      run_stress
    else
      echo "[stress] Skipped (set RUN_STRESS_TESTS=1 to enable)"
    fi
    ;;
  *)
    echo "Usage: scripts/test_all.sh [quick|backend|frontend|full]"
    exit 1
    ;;
esac
