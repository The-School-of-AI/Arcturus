# Manual Diagnostics Catalog

Only high-signal diagnostics are kept here.

## Useful
- `tests/manual/legacy/scripts/test_event_bus.py`
  - Verifies core event-bus publish/subscribe behavior.
- `tests/manual/legacy/scripts/test_persistence.py`
  - Verifies snapshot persistence manager against active loop state.
- `tests/manual/legacy/scripts/test_scheduler.py`
  - Verifies scheduler add/list/delete flow and job persistence file.
- `tests/manual/legacy/scripts/test_inbox.py`
  - Verifies inbox DB write/read path.
- `tests/manual/manual_end_to_end_skills.py`
  - API-level skills lifecycle validation (requires running backend).
- `tests/manual/legacy/debugs_and_tests/verify_api_directly.py`
  - Direct API health and run polling check (requires running backend).

## Removed As Obsolete/Redundant
- Old one-off experiments, local path dependent probes, and prompt/pdf tuning scripts that were not reliable quality gates.
- Legacy scripts that had no assertions and no repeatable pass/fail behavior.
