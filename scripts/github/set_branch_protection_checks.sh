#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "Usage: scripts/github/set_branch_protection_checks.sh <owner/repo> [branch=main] [checks_file=ci/project_required_checks.txt]"
  exit 1
fi

REPO="$1"
BRANCH="${2:-main}"
CHECKS_FILE="${3:-ci/project_required_checks.txt}"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required."
  exit 1
fi

if [[ ! -f "$CHECKS_FILE" ]]; then
  echo "Checks file not found: $CHECKS_FILE"
  exit 1
fi

TMP_PAYLOAD="$(mktemp)"
python - "$CHECKS_FILE" > "$TMP_PAYLOAD" <<'PY'
import json
import sys
from pathlib import Path

checks_file = Path(sys.argv[1])
checks = [line.strip() for line in checks_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.strip().startswith("#")]
if not checks:
    raise SystemExit("No check names found in checks file")

payload = {
    "strict": True,
    "contexts": checks,
}
print(json.dumps(payload, indent=2))
PY

echo "Applying required status checks to ${REPO}:${BRANCH}"

gh api \
  --method PATCH \
  -H "Accept: application/vnd.github+json" \
  "/repos/${REPO}/branches/${BRANCH}/protection/required_status_checks" \
  --input "$TMP_PAYLOAD"

rm -f "$TMP_PAYLOAD"

echo "Done. Required checks now sourced from ${CHECKS_FILE}."
