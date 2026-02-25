#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

cat <<MSG
[p15_gateway] Demo commands for Phase Days 11-15

1) Create API key with strict quotas (requires ARCTURUS_GATEWAY_ADMIN_KEY)
curl -sS -X POST "$BASE_URL/api/v1/keys" \
  -H "x-gateway-admin-key: \$ARCTURUS_GATEWAY_ADMIN_KEY" \
  -H "Idempotency-Key: demo-admin-create-key" \
  -H "content-type: application/json" \
  -d '{
    "name": "demo-gateway-key",
    "scopes": ["pages:write", "search:read", "webhooks:write", "webhooks:read", "cron:read", "cron:write"],
    "monthly_request_quota": 3,
    "monthly_unit_quota": 20
  }'

2) Idempotent replay on mutating endpoint (same key + same payload)
curl -sS -X POST "$BASE_URL/api/v1/pages/generate" \
  -H "x-api-key: <API_KEY_FROM_STEP_1>" \
  -H "Idempotency-Key: demo-pages-1" \
  -H "content-type: application/json" \
  -d '{"query":"Phase 3 reliability plan","template":"overview"}'

curl -sS -X POST "$BASE_URL/api/v1/pages/generate" \
  -H "x-api-key: <API_KEY_FROM_STEP_1>" \
  -H "Idempotency-Key: demo-pages-1" \
  -H "content-type: application/json" \
  -d '{"query":"Phase 3 reliability plan","template":"overview"}'

Expect second response header: X-Idempotency-Status: replayed

3) Cron timezone + history
curl -sS -X POST "$BASE_URL/api/v1/cron/jobs" \
  -H "x-api-key: <API_KEY_FROM_STEP_1>" \
  -H "Idempotency-Key: demo-cron-create" \
  -H "content-type: application/json" \
  -d '{"name":"Daily Status","cron":"0 9 * * *","agent_type":"PlannerAgent","query":"summarize updates","timezone":"UTC"}'

curl -sS "$BASE_URL/api/v1/cron/jobs/<JOB_ID>/history?limit=5" \
  -H "x-api-key: <API_KEY_FROM_STEP_1>"

4) Usage governance quota exceed signal
curl -sS -X POST "$BASE_URL/api/v1/search" \
  -H "x-api-key: <API_KEY_FROM_STEP_1>" \
  -H "content-type: application/json" \
  -d '{"query":"first"}'

curl -sS -X POST "$BASE_URL/api/v1/search" \
  -H "x-api-key: <API_KEY_FROM_STEP_1>" \
  -H "content-type: application/json" \
  -d '{"query":"second"}'

Expect controlled failure once quota is exhausted:
- HTTP 429
- detail.error.code = usage_quota_exceeded
- X-Usage-* headers
MSG
