# P15 Delivery README

## 1. Scope Delivered
- Implemented Days 11-15 hardening scope for P15 Gateway: reliability controls, strict idempotency, and usage governance.
- Added strict idempotency enforcement for authenticated mutating gateway APIs and admin key mutation APIs via required `Idempotency-Key`.
- Added idempotent replay behavior with persisted response replay, conflict detection, and in-progress duplicate protection.
- Added server-side dedupe for inbound webhooks using derived idempotency keys (`source + signature + timestamp + raw_body`).
- Added hard monthly per-key governance (request and unit quotas) with deterministic enforcement (`429 usage_quota_exceeded`) and `X-Usage-*` headers.
- Added cron timezone support and execution history endpoint (`GET /api/v1/cron/jobs/{job_id}/history`).
- Hardened webhook dispatch reliability by introducing leased `in_progress` state to prevent duplicate concurrent delivery.

## 2. Architecture Changes
- Added new gateway modules:
  - `gateway_api/idempotency.py`
  - `gateway_api/usage_governance.py`
- Extended existing modules:
  - `gateway_api/key_store.py` (monthly quotas persisted per key)
  - `gateway_api/auth.py` (`AuthContext` includes quota fields)
  - `gateway_api/metering.py` (governance-denied and non-billable accounting)
  - `gateway_api/rate_limiter.py` (combined rate-limit + governance enforcement helper)
  - `gateway_api/webhooks.py` (dispatch lease/in-progress reliability controls)
  - `core/scheduler.py` (timezone-aware scheduling + persisted execution history)
- New/updated persistence artifacts:
  - `data/gateway/idempotency_records.json`
  - `data/system/job_history.jsonl`
  - existing rollups now include governance counters (`governance_denied_requests`, `non_billable_requests`).

## 3. API And UI Changes
- Added strict idempotency requirement on mutating routes:
  - User-auth APIs: memory write, agents run, cron write/trigger/delete, webhook create/delete/trigger/dispatch/replay, pages generate, studio generate.
  - Admin APIs: keys create/update/rotate/revoke.
- Added idempotency response headers:
  - `X-Idempotency-Status: created|replayed`
  - `X-Idempotency-Key: <value>`
- Added idempotency error contracts:
  - `400 idempotency_key_required`
  - `409 idempotency_key_conflict`
  - `409 idempotency_request_in_progress`
- Added usage governance enforcement and headers:
  - `429 usage_quota_exceeded`
  - `X-Usage-Month`, `X-Usage-Requests-Limit`, `X-Usage-Requests-Remaining`, `X-Usage-Units-Limit`, `X-Usage-Units-Remaining`
- Extended key contracts:
  - `monthly_request_quota`
  - `monthly_unit_quota`
- Extended cron contracts:
  - `timezone` on create/list responses
  - job history response model from `/api/v1/cron/jobs/{job_id}/history`
- UI changes:
  - No frontend feature/UI surface changes required for this backend hardening phase.

## 4. Mandatory Test Gate Definition
- Acceptance file: `tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py`
- Integration file: `tests/integration/test_gateway_to_oracle_spark_forge.py`
- CI check: `p15-gateway-api`
- Additional phase-focused suites:
  - `tests/unit/gateway_api`
  - `tests/api/p15_gateway`

## 5. Test Evidence
- Focused phase suite command:
  - `uv run python -m pytest -q tests/unit/gateway_api tests/api/p15_gateway tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py tests/integration/test_gateway_to_oracle_spark_forge.py`
  - Result: `54 passed`
- Full project gate command:
  - `uv run ./ci/run_project_gate.sh p15-gateway-api tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py tests/integration/test_gateway_to_oracle_spark_forge.py`
  - Project contract tests result: `17 passed`
  - Baseline backend result: `382 passed, 2 skipped`
  - Baseline frontend result: `111 passed`

## 6. Existing Baseline Regression Status
- `scripts/test_all.sh quick` executed via project gate and passed.
- Backend regression remained green with only expected pre-existing skips.
- Frontend Vitest suite remained green.

## 7. Security And Safety Impact
- Mutating API operations now require explicit idempotency keys to prevent duplicate side effects under retries.
- Inbound webhook replay handling is deduplicated server-side without breaking existing inbound contracts.
- Monthly quota governance now blocks over-consumption deterministically, reducing abuse and runaway usage risk.
- Admin key routes remain fail-closed when `ARCTURUS_GATEWAY_ADMIN_KEY` is unset.
- Inbound webhook signature validation remains fail-closed when `ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET` is unset.

## 8. Known Gaps
- Persistence remains JSON/JSONL file-based; no distributed/shared coordination is implemented.
- Quota governance is key-level only; organization-level policy hierarchy is not implemented.
- Webhook dispatch remains API-triggered/manual and not an always-on worker.

## 9. Rollback Plan
- Remove idempotency and governance calls from `gateway_api/v1/*` route handlers.
- Remove `gateway_api/idempotency.py` and `gateway_api/usage_governance.py` imports/usages.
- Revert scheduler timezone/history changes in `core/scheduler.py`.
- Remove/clean generated artifacts if necessary:
  - `data/gateway/idempotency_records.json`
  - `data/system/job_history.jsonl`

## 10. Demo Steps
- Script: `scripts/demos/p15_gateway.sh`
- Demo flow covers:
  - creating a quota-bound API key,
  - idempotent replay behavior on mutating routes,
  - cron timezone + history retrieval,
  - usage governance quota exceed (`429 usage_quota_exceeded`).
