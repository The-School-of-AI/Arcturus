#!/usr/bin/env python3
"""Verify project gate check names stay synchronized.

Compares:
- ci/project_required_checks.txt
- .github/workflows/project-gates.yml (matrix check_name entries)
"""

from __future__ import annotations

import re
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKS_FILE = REPO_ROOT / "ci" / "project_required_checks.txt"
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "project-gates.yml"


def _load_required_checks() -> list[str]:
    lines = CHECKS_FILE.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def _load_workflow_checks() -> list[str]:
    text = WORKFLOW_FILE.read_text(encoding="utf-8")
    return re.findall(r"check_name:\s*([a-z0-9\-]+)", text)


def main() -> int:
    required = _load_required_checks()
    workflow = _load_workflow_checks()

    required_set = set(required)
    workflow_set = set(workflow)

    missing_in_workflow = sorted(required_set - workflow_set)
    extra_in_workflow = sorted(workflow_set - required_set)

    if missing_in_workflow or extra_in_workflow:
        print("Project gate check names are out of sync.")
        if missing_in_workflow:
            print("Missing in workflow:")
            for name in missing_in_workflow:
                print(f"  - {name}")
        if extra_in_workflow:
            print("Extra in workflow:")
            for name in extra_in_workflow:
                print(f"  - {name}")
        return 1

    if len(workflow) != 15:
        print(f"Expected 15 workflow gate checks, found {len(workflow)}")
        return 1

    print("Project gate check names are synchronized (15 checks).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
