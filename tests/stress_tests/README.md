# Stress Tests

These tests are intentionally **opt-in** and are not part of the default student PR gate.

## Modes

- Non-integration stress checks:
  - `RUN_STRESS_TESTS=1 scripts/test_all.sh full`
- Integration/external stress checks (local API/services required):
  - `RUN_STRESS_TESTS=1 RUN_STRESS_INTEGRATION=1 scripts/test_all.sh full`

## Notes

- Legacy end-to-end stress scenarios are kept as placeholders with explicit `skip` reasons until they are rewritten against current runtime APIs.
- Default `pytest` run excludes `tests/stress_tests`.
