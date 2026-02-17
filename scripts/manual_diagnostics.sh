#!/usr/bin/env bash
set -uo pipefail

MODE="${1:-smoke}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILED=0

run_step() {
  local name="$1"
  local cmd="$2"
  echo "[manual] $name"
  if (
    cd "$ROOT_DIR"
    eval "$cmd"
  ); then
    echo "[manual] PASS: $name"
  else
    echo "[manual] FAIL: $name"
    FAILED=1
  fi
}

run_smoke() {
  run_step "event bus" "python tests/manual/legacy/scripts/test_event_bus.py"
  run_step "persistence" "python tests/manual/legacy/scripts/test_persistence.py"
  run_step "scheduler" "python tests/manual/legacy/scripts/test_scheduler.py"
  run_step "inbox" "python tests/manual/legacy/scripts/test_inbox.py"
}

run_integration() {
  if [[ "${RUN_MANUAL_INTEGRATION:-0}" != "1" ]]; then
    echo "Set RUN_MANUAL_INTEGRATION=1 to run integration diagnostics"
    return
  fi

  run_step "skills lifecycle (API)" "python tests/manual/manual_end_to_end_skills.py"
  run_step "direct API probe" "python tests/manual/legacy/debugs_and_tests/verify_api_directly.py"
}

show_catalog() {
  cat "$ROOT_DIR/tests/manual/legacy/CATALOG.md"
}

case "$MODE" in
  smoke)
    run_smoke
    ;;
  integration)
    run_integration
    ;;
  all)
    run_smoke
    run_integration
    ;;
  catalog)
    show_catalog
    ;;
  *)
    echo "Usage: scripts/manual_diagnostics.sh [smoke|integration|all|catalog]"
    exit 1
    ;;
esac

if [[ "$MODE" != "catalog" && "$FAILED" -ne 0 ]]; then
  exit 1
fi
