# P15 Delivery README

## 1. Scope Delivered
- Implemented a new source-controlled gateway package: `gateway_api/` (avoids collision with `api.py`).
- Added versioned public gateway routing at `/api/v1` and mounted it from `api.py`.
- Delivered Day 1 contract + skeleton coverage for:
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

## 2. Architecture Changes
- Added new package and modules:
  - `gateway_api/contracts.py`
  - `gateway_api/key_store.py`
  - `gateway_api/auth.py`
  - `gateway_api/rate_limiter.py`
  - `gateway_api/metering.py`
  - `gateway_api/webhooks.py`
  - `gateway_api/v1/*` routers and mount router
- Added/landed service-layer source modules under `core/gateway_services/` for search/embeddings/memory wrappers.
- Updated `api.py` to include `gateway_api.v1.router` while leaving existing `/api/*` routers unchanged.
- New persistence artifacts (runtime):
  - `data/gateway/api_keys.json`
  - `data/gateway/key_audit.jsonl`
  - `data/gateway/metering_events.jsonl`
  - `data/gateway/metering_rollup_YYYY-MM.json`
  - `data/gateway/webhook_subscriptions.json`
  - `data/gateway/webhook_deliveries.jsonl`
  - `data/gateway/webhook_dlq.jsonl`

## 3. API And UI Changes
- API changes:
  - Added public `/api/v1` gateway endpoints listed in Scope Delivered.
  - Added admin-only key management via `x-gateway-admin-key`.
  - Admin key management routes (`/api/v1/keys*`) fail closed unless `ARCTURUS_GATEWAY_ADMIN_KEY` is explicitly configured; unset config returns `503` with `admin_key_not_configured`.
  - Added scope enforcement (`search:read`, `chat:write`, `embeddings:write`, `memory:*`, `agents:run`, `cron:*`, `webhooks:write`, `usage:read`, etc.).
  - Added rate-limit response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`.
- UI changes:
  - No frontend UI changes in Day 1 scope (API management UI deferred).

## 4. Mandatory Test Gate Definition
- Acceptance file: tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py
- Integration file: tests/integration/test_gateway_to_oracle_spark_forge.py
- CI check: p15-gateway-api

## 5. Test Evidence
- New Day 1 gateway tests added and passing:
  - `tests/unit/gateway_api/test_gateway_auth.py`
  - `tests/unit/gateway_api/test_gateway_key_store_and_metering.py`
  - `tests/unit/gateway_api/test_gateway_rate_limiter.py`
  - `tests/api/p15_gateway/test_gateway_v1_contracts.py`
- Command:
  - `uv run python -m pytest -q tests/unit/gateway_api tests/api/p15_gateway`
  - Result: `12 passed`
- Existing P15 scaffold gate tests still passing:
  - `uv run python -m pytest -q tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py tests/integration/test_gateway_to_oracle_spark_forge.py`
  - Result: `13 passed`

## 6. Existing Baseline Regression Status
- Command: scripts/test_all.sh quick
- Attempted via: `uv run scripts/test_all.sh quick`
- Status: **fails due unrelated pre-existing import errors** during backend test collection:
  - `tests/test_episodic_retrieval.py` -> `ModuleNotFoundError: No module named 'memory.episodic'`
  - `tests/test_preplan_retrieval.py` -> `ModuleNotFoundError: No module named 'memory.episodic'`
- No failures observed in newly added P15 Day 1 gateway tests.

## 7. Security And Safety Impact
- API keys are stored hashed (SHA-256) in persistent storage; plaintext is only returned once at create/rotate time.
- Scope-based authorization added per endpoint.
- Rate-limiting and usage metering added to reduce abuse exposure and improve observability.
- Admin key protection added for key lifecycle endpoints.
- No default admin secret is accepted; if `ARCTURUS_GATEWAY_ADMIN_KEY` is unset, `/api/v1/keys*` remains unavailable (`503` fail-closed response).
- Webhook delivery execution is intentionally not enabled yet (contract-only skeleton), limiting external side effects at this stage.

## 8. Known Gaps
- `/api/v1/pages/generate` and `/api/v1/studio/{slides|docs|sheets}` are typed contract stubs returning `501`.
- Webhook worker/retry engine, signature validation middleware, and DLQ replay flow are not implemented yet (skeleton only).
- Chat endpoint is OpenAI-subset and intentionally rejects `stream=true`.
- Usage/billing is metering-only; billing settlement logic not implemented.
- Quick baseline suite currently fails due pre-existing missing `memory.episodic` module, unrelated to this Day 1 change.

## 9. Rollback Plan
- Remove `app.include_router(gateway_v1_router.router)` from `api.py`.
- Delete `gateway_api/` package and new `core/gateway_services/*.py` files.
- Delete added tests under `tests/unit/gateway_api/` and `tests/api/p15_gateway/`.
- Remove generated `data/gateway/*` files if cleanup is needed.

## 10. Demo Steps
- Script: scripts/demos/p15_gateway.sh
- Set `ARCTURUS_GATEWAY_ADMIN_KEY` in the environment, then generate an API key via `x-gateway-admin-key` using `POST /api/v1/keys`.
- Call `POST /api/v1/search` and `POST /api/v1/chat/completions` with `x-api-key`.
- Create cron job via `POST /api/v1/cron/jobs`, list via `GET /api/v1/cron/jobs`.
- Create webhook subscription via `POST /api/v1/webhooks`, trigger with `POST /api/v1/webhooks/trigger`.
- Inspect generated gateway files under `data/gateway/` for key audit, metering, and webhook queue evidence.
