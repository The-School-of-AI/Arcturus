# Test Structure

- `tests/`: CI-gated Python tests.
- `tests/stress_tests/`: stress/load tests (not part of default PR gate).
- `tests/manual/`: manual scripts and exploratory checks (not auto-collected).
- `platform-frontend/src/__tests__/`: frontend Vitest suite.
- `tests/ACTUAL_PLAN_TEST_MAP.md`: mapping from ACTUAL PLAN objectives to retained tests.

## Standard Runs

- Backend only: `scripts/test_all.sh backend`
- Frontend only: `scripts/test_all.sh frontend`
- PR gate (default): `scripts/test_all.sh quick`
- Extended run: `RUN_STRESS_TESTS=1 scripts/test_all.sh full`
- Extended integration stress run: `RUN_STRESS_TESTS=1 RUN_STRESS_INTEGRATION=1 scripts/test_all.sh full`
- Manual diagnostics: `scripts/manual_diagnostics.sh smoke`
- Manual diagnostics (integration): `RUN_MANUAL_INTEGRATION=1 scripts/manual_diagnostics.sh all`
