# GitHub Setup Runbook (Project + Required Checks)

This runbook sets up the capstone project board and required CI checks.

## Prerequisites
- `gh auth login` completed.
- Token includes scopes: `repo`, `project`, and branch-admin permissions for protection settings.
- Push all local workflow and gate files before running this.

## Step 1: Create/Seed GitHub Project (15 Tracks)

```bash
scripts/github/bootstrap_capstone_project.sh The-School-of-AI The-School-of-AI/Arcturus "Arcturus Capstone 15 Projects"
```

This creates:
- one GitHub project,
- tracking fields,
- 15 draft items (P01..P15),
- repo link.

## Step 2: Apply Required Branch Checks

```bash
scripts/github/set_branch_protection_checks.sh The-School-of-AI/Arcturus master ci/project_required_checks.txt
```

Required checks source:
- `ci/project_required_checks.txt`

## Step 3: Verify Sync

```bash
python ci/verify_project_gate_manifest.py
```

Expected:
- `Project gate check names are synchronized (15 checks).`

## Step 4: Daily PR Queue

```bash
scripts/github/pr_review_queue.sh The-School-of-AI/Arcturus
```

Output:
- `CAPSTONE/PR_REVIEW_QUEUE.md`
