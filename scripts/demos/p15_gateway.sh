#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MODE="${1:-guide}"
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "./.venv/bin/python" ]]; then
    PYTHON_BIN="./.venv/bin/python"
  else
    PYTHON_BIN="python"
  fi
fi

if [[ "$MODE" == "--smoke" ]]; then
  "$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from p15_gateway_runtime import build_gateway_runtime_context


def auth_headers(api_key: str, idempotency_key: str | None = None) -> dict:
    headers = {"x-api-key": api_key}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


with tempfile.TemporaryDirectory() as tmp_dir:
    monkeypatch = pytest.MonkeyPatch()
    try:
        ctx = build_gateway_runtime_context(Path(tmp_dir), monkeypatch)
        client = ctx["client"]
        api_key = ctx["create_api_key"](
            [
                "search:read",
                "pages:write",
                "webhooks:write",
                "webhooks:read",
                "cron:read",
                "cron:write",
            ]
        )
        connector_headers = ctx["connector_headers"]

        search = client.post("/api/v1/search", json={"query": "demo"}, headers=auth_headers(api_key))
        assert search.status_code == 200, search.text

        page = client.post(
            "/api/v1/pages/generate",
            json={"query": "demo page", "template": "overview"},
            headers=auth_headers(api_key, "demo-smoke-page"),
        )
        assert page.status_code == 200, page.text

        cron = client.post(
            "/api/v1/cron/jobs",
            json={
                "name": "Smoke Cron",
                "cron": "0 9 * * *",
                "agent_type": "PlannerAgent",
                "query": "smoke",
                "timezone": "UTC",
            },
            headers=auth_headers(api_key, "demo-smoke-cron"),
        )
        assert cron.status_code == 200, cron.text

        sub = client.post(
            "/api/v1/webhooks",
            json={"target_url": "https://example.com/inbound", "event_types": ["memory.updated"]},
            headers=auth_headers(api_key, "demo-smoke-webhook-sub"),
        )
        assert sub.status_code == 200, sub.text

        github_payload = {"ref": "refs/heads/main", "after": "abc"}
        inbound = client.post(
            "/api/v1/webhooks/inbound/github",
            content=json.dumps(github_payload),
            headers=connector_headers("github", github_payload, event_name="push"),
        )
        assert inbound.status_code == 200, inbound.text

        connectors = client.get("/api/v1/webhooks/connectors", headers=auth_headers(api_key))
        assert connectors.status_code == 200, connectors.text
        sources = {row["source"] for row in connectors.json()}
        assert {"github", "jira", "gmail"} <= sources

        print("p15_gateway smoke passed")
    finally:
        monkeypatch.undo()
PY
  exit 0
fi

cat <<MSG
[p15_gateway] Demo commands for Final Phase (Days 16-20)

1) Create API key with quotas (requires ARCTURUS_GATEWAY_ADMIN_KEY)
curl -sS -X POST "$BASE_URL/api/v1/keys" \
  -H "x-gateway-admin-key: \$ARCTURUS_GATEWAY_ADMIN_KEY" \
  -H "Idempotency-Key: demo-admin-create-key" \
  -H "content-type: application/json" \
  -d '{
    "name": "demo-gateway-key",
    "scopes": ["pages:write", "search:read", "webhooks:write", "webhooks:read", "cron:read", "cron:write", "usage:read"],
    "monthly_request_quota": 10,
    "monthly_unit_quota": 100
  }'

2) Idempotent replay on mutating endpoint
curl -sS -X POST "$BASE_URL/api/v1/pages/generate" \
  -H "x-api-key: <API_KEY>" \
  -H "Idempotency-Key: demo-pages-1" \
  -H "content-type: application/json" \
  -d '{"query":"Final phase reliability","template":"overview"}'

curl -sS -X POST "$BASE_URL/api/v1/pages/generate" \
  -H "x-api-key: <API_KEY>" \
  -H "Idempotency-Key: demo-pages-1" \
  -H "content-type: application/json" \
  -d '{"query":"Final phase reliability","template":"overview"}'

3) Connector listing and inbound GitHub event (connector auth mode)
curl -sS "$BASE_URL/api/v1/webhooks/connectors" \
  -H "x-api-key: <API_KEY>"

# ARCTURUS_GATEWAY_GITHUB_WEBHOOK_SECRET must be configured.
# Compute x-hub-signature-256 on the raw JSON body and submit inbound event.
curl -sS -X POST "$BASE_URL/api/v1/webhooks/inbound/github" \
  -H "content-type: application/json" \
  -H "x-github-event: push" \
  -H "x-github-delivery: demo-delivery-1" \
  -H "x-hub-signature-256: <sha256_signature>" \
  -d '{"ref":"refs/heads/main","after":"abc123"}'

4) Cron timezone + history
curl -sS -X POST "$BASE_URL/api/v1/cron/jobs" \
  -H "x-api-key: <API_KEY>" \
  -H "Idempotency-Key: demo-cron-create" \
  -H "content-type: application/json" \
  -d '{"name":"Daily Status","cron":"0 9 * * *","agent_type":"PlannerAgent","query":"summarize updates","timezone":"UTC"}'

curl -sS "$BASE_URL/api/v1/cron/jobs/<JOB_ID>/history?limit=5" \
  -H "x-api-key: <API_KEY>"

5) Usage governance quota exceed signal
curl -sS -X POST "$BASE_URL/api/v1/search" \
  -H "x-api-key: <API_KEY>" \
  -H "content-type: application/json" \
  -d '{"query":"first"}'

curl -sS -X POST "$BASE_URL/api/v1/search" \
  -H "x-api-key: <API_KEY>" \
  -H "content-type: application/json" \
  -d '{"query":"second"}'

Expect when exhausted:
- HTTP 429
- detail.error.code = usage_quota_exceeded
- X-Usage-* headers

Use './scripts/demos/p15_gateway.sh --smoke' for deterministic local smoke validation.
MSG
