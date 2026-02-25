# P15 Delivery README

## 1. Scope Delivered
- Implemented a new source-controlled gateway package: `gateway_api/` (avoids collision with `api.py`).
- Added versioned public gateway routing at `/api/v1` and mounted it from `api.py`.
- Delivered Phase 1 (Day 1) contract + skeleton coverage for:
  - Search: `POST /api/v1/search`
  - Chat (OpenAI-subset, non-streaming): `POST /api/v1/chat/completions`
  - Embeddings: `POST /api/v1/embeddings`
  - Memory: `POST /api/v1/memory/{read|write|search}`
  - Agents: `POST /api/v1/agents/run`
  - Cron wrappers: `/api/v1/cron/*`
  - API Keys admin: `/api/v1/keys/*`
  - Usage: `/api/v1/usage`, `/api/v1/usage/all`
  - Webhooks contract skeleton: `/api/v1/webhooks/*`
  - Pages/Studio typed placeholders: `/api/v1/pages/generate`, `/api/v1/studio/{slides|docs|sheets}`
- Implemented scoped API-key auth model (`x-api-key` and `Authorization: Bearer ...`).
- Implemented in-memory token-bucket rate limiter with standard headers.
- Implemented JSON/JSONL metering pipeline and monthly rollups in `data/gateway/`.
- Implemented JSON-backed key store with hash-at-rest, rotate/revoke, and audit log.
- Implemented webhook subscription + trigger contract skeleton with persisted queue records.
- Delivered Phase 2 (Days 6-10) integration behavior:
  - Added adapter layer for Oracle/Spark/Forge under `core/gateway_services/`.
  - Converted `/api/v1/pages/generate` from placeholder to functional Oracle+Spark integration.
  - Converted `/api/v1/studio/{slides|docs|sheets}` from placeholder to functional Oracle+Forge integration.
  - Added signed inbound webhook endpoint with fail-closed secret requirement.
  - Added webhook dispatch lifecycle endpoints (`dispatch`, `deliveries`, `dlq replay`) with retry/dead-letter behavior.
  - Added integration trace events persisted to `data/gateway/integration_events.jsonl`.
- Implemented Days 11-15 hardening scope for P15 Gateway:
  - strict idempotency for mutating APIs,
  - hard monthly usage governance,
  - cron timezone + execution history,
  - webhook dispatch duplicate-prevention improvements.

## 2. Architecture Changes
- Added new package and modules:
  - `gateway_api/contracts.py`
  - `gateway_api/key_store.py`
  - `gateway_api/auth.py`
  - `gateway_api/rate_limiter.py`
  - `gateway_api/metering.py`
  - `gateway_api/webhooks.py`
  - `gateway_api/integration_tracing.py`
  - `gateway_api/v1/*` routers and mount router
- Added/landed service-layer source modules under `core/gateway_services/` for search/embeddings/memory wrappers.
- Added service adapters for Phase 2:
  - `core/gateway_services/oracle_adapter.py`
  - `core/gateway_services/spark_adapter.py`
  - `core/gateway_services/forge_adapter.py`
  - `core/gateway_services/exceptions.py`
- Updated `api.py` to include `gateway_api.v1.router` while leaving existing `/api/*` routers unchanged.
- Added Days 11-15 modules:
  - `gateway_api/idempotency.py`
  - `gateway_api/usage_governance.py`
- Extended existing modules for Days 11-15:
  - `gateway_api/key_store.py` (monthly quotas persisted per key)
  - `gateway_api/auth.py` (`AuthContext` quota fields)
  - `gateway_api/metering.py` (governance-denied and non-billable accounting)
  - `gateway_api/rate_limiter.py` (combined rate-limit + governance enforcement helper)
  - `gateway_api/webhooks.py` (dispatch lease/in-progress reliability controls)
  - `core/scheduler.py` (timezone-aware scheduling + persisted execution history)
- Persistence artifacts (runtime):
  - `data/gateway/api_keys.json`
  - `data/gateway/key_audit.jsonl`
  - `data/gateway/metering_events.jsonl`
  - `data/gateway/metering_rollup_YYYY-MM.json`
  - `data/gateway/webhook_subscriptions.json`
  - `data/gateway/webhook_deliveries.jsonl`
  - `data/gateway/webhook_dlq.jsonl`
  - `data/gateway/integration_events.jsonl`
  - `data/gateway/idempotency_records.json`
  - `data/system/job_history.jsonl`

## 3. API And UI Changes
- API changes from Phase 1/2:
  - Added public `/api/v1` gateway endpoints listed in Scope Delivered.
  - Added admin-only key management via `x-gateway-admin-key`.
  - Admin key management routes (`/api/v1/keys*`) fail closed unless `ARCTURUS_GATEWAY_ADMIN_KEY` is explicitly configured; unset config returns `503` with `admin_key_not_configured`.
  - Added functional Spark endpoint `POST /api/v1/pages/generate` with typed response (`trace_id`, citations, artifact payload).
  - Added functional Forge endpoints:
    - `POST /api/v1/studio/slides`
    - `POST /api/v1/studio/docs`
    - `POST /api/v1/studio/sheets`
  - Added webhook lifecycle/security endpoints:
    - `POST /api/v1/webhooks/inbound/{source}`
    - `POST /api/v1/webhooks/dispatch`
    - `GET /api/v1/webhooks/deliveries`
    - `POST /api/v1/webhooks/dlq/{delivery_id}/replay`
  - Inbound webhook signature validation fails closed unless `ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET` is configured (`503` `webhook_signing_not_configured`).
  - Added scope enforcement (`search:read`, `chat:write`, `embeddings:write`, `memory:*`, `agents:run`, `cron:*`, `webhooks:write`, `usage:read`, etc.).
  - Added rate-limit response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`.
- API changes from Days 11-15:
  - Added strict idempotency requirement on mutating routes (user-auth and admin-auth mutations).
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
    - `GET /api/v1/cron/jobs/{job_id}/history`
- UI changes:
  - No frontend API management UI changes in delivered P15 backend phases.

## 4. Mandatory Test Gate Definition
- Acceptance file: `tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py`
- Integration file: `tests/integration/test_gateway_to_oracle_spark_forge.py`
- CI check: `p15-gateway-api`
- Additional phase-focused suites:
  - `tests/unit/gateway_api`
  - `tests/api/p15_gateway`

## 5. Test Evidence
- Phase 1/2 gateway suite:
  - `uv run python -m pytest -q tests/unit/gateway_api tests/api/p15_gateway`
  - Result (prior phase): `25 passed`
- Phase 2 acceptance/integration:
  - `uv run python -m pytest -q tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py tests/integration/test_gateway_to_oracle_spark_forge.py`
  - Result (prior phase): `13 passed`
- Days 11-15 focused phase suite:
  - `uv run python -m pytest -q tests/unit/gateway_api tests/api/p15_gateway tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py tests/integration/test_gateway_to_oracle_spark_forge.py`
  - Result: `54 passed`
- Full project gate:
  - `uv run ./ci/run_project_gate.sh p15-gateway-api tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py tests/integration/test_gateway_to_oracle_spark_forge.py`
  - Project contract tests result: `17 passed`
  - Baseline backend result: `382 passed, 2 skipped`
  - Baseline frontend result: `111 passed`

## 6. Existing Baseline Regression Status
- Executed via project gate command:
  - `uv run ./ci/run_project_gate.sh p15-gateway-api tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py tests/integration/test_gateway_to_oracle_spark_forge.py`
- Prior phase baseline snapshot:
  - P15 gate tests: `13 passed`
  - Backend baseline: `334 passed, 2 skipped`
  - Frontend baseline: `111 passed`
- Current Days 11-15 baseline snapshot:
  - Project contract tests: `17 passed`
  - Backend baseline: `382 passed, 2 skipped`
  - Frontend baseline: `111 passed`

## 7. Security And Safety Impact
- API keys are stored hashed (SHA-256) in persistent storage; plaintext is only returned once at create/rotate time.
- Scope-based authorization enforced per endpoint.
- Rate-limiting and usage metering reduce abuse exposure and improve observability.
- Admin key protection is fail-closed when `ARCTURUS_GATEWAY_ADMIN_KEY` is unset.
- Inbound signed webhook validation is fail-closed when `ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET` is unset.
- Webhook delivery lifecycle supports controlled retries and dead-letter handling via API-triggered dispatch.
- Days 11-15 hardening additions:
  - Mutating API operations require explicit idempotency keys to prevent duplicate side effects.
  - Inbound webhook replay handling is deduplicated server-side without breaking contract compatibility.
  - Monthly quota governance blocks over-consumption deterministically.

## 8. Known Gaps
- Webhook dispatch is API-invoked/manual rather than always-on background worker.
- Chat endpoint is OpenAI-subset and intentionally rejects `stream=true`.
- Usage/billing is metering-only; settlement logic is not implemented.
- Spark integration currently uses `AppGenerator` as Phase 2 adapter base; dedicated Spark service package is deferred.
- Persistence remains JSON/JSONL file-based; no distributed/shared coordination is implemented.
- Quota governance is key-level only; organization-level policy hierarchy is not implemented.

## 9. Rollback Plan
- Remove `app.include_router(gateway_v1_router.router)` from `api.py`.
- Delete `gateway_api/` package and new `core/gateway_services/*.py` files.
- Delete added tests under `tests/unit/gateway_api/` and `tests/api/p15_gateway/`.
- Remove generated `data/gateway/*` files if cleanup is needed.
- Days 11-15 rollback specifics:
  - Remove idempotency and governance calls from `gateway_api/v1/*` route handlers.
  - Remove `gateway_api/idempotency.py` and `gateway_api/usage_governance.py` imports/usages.
  - Revert scheduler timezone/history changes in `core/scheduler.py`.
  - Remove/clean generated artifacts if needed:
    - `data/gateway/idempotency_records.json`
    - `data/system/job_history.jsonl`

## 10. Demo Steps
- Script: `scripts/demos/p15_gateway.sh`
- Set `ARCTURUS_GATEWAY_ADMIN_KEY` in the environment, then generate an API key via `x-gateway-admin-key` using `POST /api/v1/keys`.
- Set `ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET` before using signed inbound webhook endpoint.
- Call `POST /api/v1/search` and `POST /api/v1/chat/completions` with `x-api-key`.
- Call `POST /api/v1/pages/generate` and `POST /api/v1/studio/{slides|docs|sheets}` with integration-capable scopes.
- Create cron job via `POST /api/v1/cron/jobs`, list via `GET /api/v1/cron/jobs`.
- Create webhook subscription via `POST /api/v1/webhooks`, trigger with `POST /api/v1/webhooks/trigger`.
- Validate signed inbound flow via `POST /api/v1/webhooks/inbound/{source}` using `x-gateway-signature` and `x-gateway-timestamp`.
- Process queued deliveries with `POST /api/v1/webhooks/dispatch`, inspect state with `GET /api/v1/webhooks/deliveries`, and replay failures with `POST /api/v1/webhooks/dlq/{delivery_id}/replay`.
- Inspect generated gateway files under `data/gateway/` for key audit, metering, integration trace, idempotency, and webhook lifecycle evidence.
- Days 11-15 demo coverage includes:
  - idempotent replay behavior on mutating routes,
  - cron timezone + history retrieval,
  - usage governance quota exceed (`429 usage_quota_exceeded`).
