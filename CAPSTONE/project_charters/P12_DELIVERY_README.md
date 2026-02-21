# P12 Delivery README

## 1. Scope Delivered
- Prompt-injection input scanner
- Minimal policy engine (PII redaction)
- Canary generator + helpers
- Test scaffolding (acceptance)

## 2. Architecture Changes
- Added `safety/` package
- Integrated middleware scaffold in `core/loop.py` (developer must paste)

Known Gaps
- ML-based jailbreak classifier not implemented
- Tool whitelist to be provided per-org

## 3. API And UI Changes
- TODO

## 4. Mandatory Test Gate Definition
- Acceptance file: tests/acceptance/p12_aegis/test_injection_attempts_blocked.py
- Integration file: tests/integration/test_aegis_enforcement_on_oracle_and_legion.py
- CI check: p12-aegis-safety

## 5. Test Evidence
- TODO

## 6. Existing Baseline Regression Status
- Command: scripts/test_all.sh quick
- TODO

## 7. Security And Safety Impact
- TODO

## 8. Known Gaps
- TODO

## 9. Rollback Plan
- TODO

## 10. Demo Steps
- Script: scripts/demos/p12_aegis.sh
- TODO
