# PXX Delivery README Template

Use this template for each project delivery file:
- `CAPSTONE/project_charters/P01_DELIVERY_README.md`
- `CAPSTONE/project_charters/P02_DELIVERY_README.md`
- ...
- `CAPSTONE/project_charters/P15_DELIVERY_README.md`

## 1. Scope Delivered
- Features completed vs planned.
- Explicitly list deferred items.

## 2. Architecture Changes
- New modules/files and ownership.
- Data flow diagram or sequence summary.
- Backward compatibility notes.

## 3. API And UI Changes
- Endpoints/components added or changed.
- Request/response schema changes.
- Migration notes for consumers.

## 4. Mandatory Test Gate Definition
- Acceptance file path and exact scenarios covered.
- Integration file path and dependencies exercised.
- CI check name and commands executed.
- Pass/fail criteria and thresholds.

## 5. Test Evidence
- Command outputs (summarized) and links to CI runs.
- Coverage impact and flaky-test handling.
- Performance numbers against project P95 target.

## 6. Existing Baseline Regression Status
- `scripts/test_all.sh quick` result.
- Any additional regression/stress suites run.
- Known deviations and mitigation plan.

## 7. Security And Safety Impact
- New attack surfaces.
- Guardrails/policy checks added.
- Secrets/credentials handling.

## 8. Known Gaps
- Open defects and severity.
- Tech debt accepted for this sprint.

## 9. Rollback Plan
- Safe rollback steps.
- Data rollback implications.
- Feature flag or kill-switch details.

## 10. Demo Steps
- Reproducible demo commands.
- Required fixtures/test data.
- Expected visible outputs.
