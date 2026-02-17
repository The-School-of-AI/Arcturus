# Daily PR Review Operating Flow

Use this workflow each day to triage, approve, or request changes.

## 1) Generate Queue

```bash
scripts/github/pr_review_queue.sh theschoolofai/Arcturus
```

Output file:
- `CAPSTONE/PR_REVIEW_QUEUE.md`

## 2) Review Each PR Against Contract
- Confirm charter scope alignment for the PR's project.
- Confirm `CAPSTONE/project_charters/PXX_DELIVERY_README.md` is updated with evidence.
- Confirm required check is green for that project (`pXX-*`).
- Confirm baseline checks are green (`scripts/test_all.sh quick` equivalent in CI).

## 3) Decision
- Approve if all required checks pass and scope matches charter.
- Request changes if gates fail, README evidence is weak, or scope is off-charter.

## 4) Command Examples

Approve:

```bash
gh pr review <PR_NUMBER> -R theschoolofai/Arcturus --approve -b "Project gate and charter requirements satisfied."
```

Request changes:

```bash
gh pr review <PR_NUMBER> -R theschoolofai/Arcturus --request-changes -b "Please address failing gates and update delivery README sections 4/5/10 with evidence."
```

## 5) Non-Negotiable Reject Conditions
- Missing project delivery README.
- Required project check red/pending.
- Baseline suite failing.
- Changes outside assigned project with no justification.
