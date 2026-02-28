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
- New persistence artifacts (runtime):
  - `data/gateway/api_keys.json`
  - `data/gateway/key_audit.jsonl`
  - `data/gateway/metering_events.jsonl`
  - `data/gateway/metering_rollup_YYYY-MM.json`
  - `data/gateway/webhook_subscriptions.json`
  - `data/gateway/webhook_deliveries.jsonl`
  - `data/gateway/webhook_dlq.jsonl`
  - `data/gateway/integration_events.jsonl`

## 3. API And UI Changes
- API changes:
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
- UI changes:
  - No frontend UI changes in Day 1 scope (API management UI deferred).

## 4. Mandatory Test Gate Definition
- Acceptance file: tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py
- Integration file: tests/integration/test_gateway_to_oracle_spark_forge.py
- CI check: p15-gateway-api

## 5. Test Evidence
- New/updated gateway tests added and passing:
  - `tests/unit/gateway_api/test_gateway_auth.py`
  - `tests/unit/gateway_api/test_gateway_key_store_and_metering.py`
  - `tests/unit/gateway_api/test_gateway_rate_limiter.py`
  - `tests/unit/gateway_api/test_gateway_adapters_and_tracing.py`
  - `tests/unit/gateway_api/test_gateway_webhooks_security_and_dispatch.py`
  - `tests/api/p15_gateway/test_gateway_v1_contracts.py`
- Command:
  - `uv run python -m pytest -q tests/unit/gateway_api tests/api/p15_gateway`
  - Result: `25 passed`
- Updated P15 acceptance/integration behavioral gate tests passing:
  - `uv run python -m pytest -q tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py tests/integration/test_gateway_to_oracle_spark_forge.py`
  - Result: `13 passed`

## 6. Existing Baseline Regression Status
- Command: scripts/test_all.sh quick
- Executed via project gate command:
  - `uv run ./ci/run_project_gate.sh p15-gateway-api tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py tests/integration/test_gateway_to_oracle_spark_forge.py`
- Status: **passing**
  - P15 gate tests: `13 passed`
  - Backend baseline: `334 passed, 2 skipped`
  - Frontend baseline: `111 passed`

## 7. Security And Safety Impact
- API keys are stored hashed (SHA-256) in persistent storage; plaintext is only returned once at create/rotate time.
- Scope-based authorization added per endpoint.
- Rate-limiting and usage metering added to reduce abuse exposure and improve observability.
- Admin key protection added for key lifecycle endpoints.
- No default admin secret is accepted; if `ARCTURUS_GATEWAY_ADMIN_KEY` is unset, `/api/v1/keys*` remains unavailable (`503` fail-closed response).
- Inbound signed webhook validation is fail-closed when `ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET` is unset.
- Webhook delivery lifecycle now supports controlled retries and dead-letter handling via API-triggered dispatch.

## 8. Known Gaps
- Webhook dispatch is API-invoked (manual/triggered) rather than always-on background worker.
- Chat endpoint is OpenAI-subset and intentionally rejects `stream=true`.
- Usage/billing is metering-only; billing settlement logic not implemented.
- Spark integration currently uses `AppGenerator` as Phase 2 adapter base; dedicated Spark service package is deferred.

## 9. Rollback Plan
- Remove `app.include_router(gateway_v1_router.router)` from `api.py`.
- Delete `gateway_api/` package and new `core/gateway_services/*.py` files.
- Delete added tests under `tests/unit/gateway_api/` and `tests/api/p15_gateway/`.
- Remove generated `data/gateway/*` files if cleanup is needed.

## 10. Demo Steps
- Script: scripts/demos/p15_gateway.sh
- Set `ARCTURUS_GATEWAY_ADMIN_KEY` in the environment, then generate an API key via `x-gateway-admin-key` using `POST /api/v1/keys`.
- Set `ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET` before using signed inbound webhook endpoint.
- Call `POST /api/v1/search` and `POST /api/v1/chat/completions` with `x-api-key`.
- Call `POST /api/v1/pages/generate` and `POST /api/v1/studio/{slides|docs|sheets}` with integration-capable scopes.
- Create cron job via `POST /api/v1/cron/jobs`, list via `GET /api/v1/cron/jobs`.
- Create webhook subscription via `POST /api/v1/webhooks`, trigger with `POST /api/v1/webhooks/trigger`.
- Validate signed inbound flow via `POST /api/v1/webhooks/inbound/{source}` using `x-gateway-signature` and `x-gateway-timestamp`.
- Process queued deliveries with `POST /api/v1/webhooks/dispatch`, inspect state with `GET /api/v1/webhooks/deliveries`, and replay failures with `POST /api/v1/webhooks/dlq/{delivery_id}/replay`.
- Inspect generated gateway files under `data/gateway/` for key audit, metering, integration trace, and webhook lifecycle evidence.
