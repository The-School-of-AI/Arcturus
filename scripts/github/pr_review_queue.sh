#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: scripts/github/pr_review_queue.sh <owner/repo> [output_markdown=CAPSTONE/PR_REVIEW_QUEUE.md]"
  exit 1
fi

REPO="$1"
OUT="${2:-CAPSTONE/PR_REVIEW_QUEUE.md}"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required."
  exit 1
fi

TMP_PR="$(mktemp)"
TMP_OUT="$(mktemp)"

gh pr list -R "$REPO" --limit 100 --json number,title,author,headRefName,isDraft,reviewDecision,url > "$TMP_PR"

python - "$TMP_PR" "$TMP_OUT" "$REPO" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

pr_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
repo = sys.argv[3]
prs = json.loads(pr_path.read_text(encoding="utf-8"))

lines = []
lines.append("# PR Review Queue")
lines.append("")
lines.append("Daily triage report for capstone PR approvals and change requests.")
lines.append("")

if not prs:
    lines.append("No open PRs.")
else:
    lines.append("| PR | Title | Author | Branch | Draft | Required Checks | Recommendation |")
    lines.append("|---|---|---|---|---|---|---|")

for pr in prs:
    number = pr["number"]
    cmd = [
        "gh", "pr", "checks", str(number), "-R", repo,
        "--required", "--json", "name,bucket,state"
    ]
    try:
        checks_raw = subprocess.check_output(cmd, text=True)
        checks = json.loads(checks_raw)
    except subprocess.CalledProcessError:
        checks = []

    if not checks:
        checks_summary = "no-required-checks-detected"
        recommendation = "REQUEST_CHANGES (missing required checks)"
    else:
        buckets = [c.get("bucket", "") for c in checks]
        if any(b in ("fail", "cancel") for b in buckets):
            recommendation = "REQUEST_CHANGES"
        elif any(b == "pending" for b in buckets):
            recommendation = "WAIT (checks pending)"
        else:
            recommendation = "APPROVE_CANDIDATE"
        checks_summary = ", ".join(f"{c['name']}:{c.get('bucket','?')}" for c in checks)

    if pr.get("isDraft"):
        recommendation = "WAIT (draft PR)"

    lines.append(
        f"| #{number} | {pr['title']} | {pr['author']['login']} | {pr['headRefName']} | {str(pr['isDraft']).lower()} | {checks_summary} | {recommendation} |"
    )

lines.append("")
lines.append("## Decision Policy")
lines.append("1. Approve only if recommendation is APPROVE_CANDIDATE and scope matches charter.")
lines.append("2. Request changes if required checks fail or charter/delivery README is incomplete.")
lines.append("3. Do not approve draft PRs.")

out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

mkdir -p "$(dirname "$OUT")"
cp "$TMP_OUT" "$OUT"
rm -f "$TMP_PR" "$TMP_OUT"

echo "Wrote PR queue report to $OUT"
