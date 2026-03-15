# P14 Watchtower — Status Summary & Pickup Guide

**Last updated:** March 2025  
**Scope:** Days 1–20 delivered (all phases complete)

---

## 1. Delivery Summary

All five P14 phases have been implemented end-to-end (backend + frontend + tests).

### P14.1 — Distributed Tracing (Days 1–5)

| Component | Status | Location |
|-----------|--------|----------|
| **OpenTelemetry integration** | Done | `ops/tracing/` |
| **MongoDB + Jaeger exporters** | Done | `ops/tracing/core.py` |
| **Span hierarchy** | Done | `ops/tracing/spans.py` |
| **Agent loop instrumentation** | Done | `core/loop.py` |
| **LLM / sandbox / code instrumentation** | Done | `core/model_manager.py`, `core/sandbox/executor.py`, `memory/context.py` |
| **Admin API** | Done | `routers/admin.py` |
| **Fallback HTML UI** | Done | `GET /api/admin/traces/view` |
| **CI gate** | Done | `p14-watchtower-ops` |

### P14.2 — Cost Analytics (Days 6–10)

| Component | Status | Location |
|-----------|--------|----------|
| **ConfigurableCostCalculator** | Done | `ops/cost/calculator.py` |
| **Per-model pricing config** | Done | `ops/cost/pricing.py` |
| **Cost attributes in llm_span** | Done | `core/model_manager.py` |
| **Cost summary API** | Done | `GET /api/admin/cost/summary` |
| **CostPanel (dashboard)** | Done | `features/admin/components/CostPanel.tsx` |

### P14.3 — Health Monitoring (Days 6–10)

| Component | Status | Location |
|-----------|--------|----------|
| **Service health checks** (MongoDB, Qdrant, Ollama, MCP, Neo4j, Agent Core) | Done | `ops/health/checks.py` |
| **HealthScheduler** (periodic background checks) | Done | `ops/health/scheduler.py` |
| **HealthRepository** (MongoDB persistence, uptime) | Done | `ops/health/repository.py` |
| **AlertEvaluator + LogNotifier** | Done | `ops/health/alerts.py` |
| **Resource monitoring** (CPU/memory/disk via psutil) | Done | `ops/health/checks.py` |
| **Health APIs** (`/health`, `/health/history`, `/health/uptime`, `/health/resources`) | Done | `routers/admin.py` |
| **HealthPanel (dashboard)** | Done | `features/admin/components/HealthPanel.tsx` |

### P14.4 — Admin Controls (Days 11–15)

| Component | Status | Location |
|-----------|--------|----------|
| **Feature flags** (JSON-backed, lifecycle hooks) | Done | `ops/admin/feature_flags.py` |
| **Cache management** (list/flush) | Done | `routers/admin.py` |
| **Config view/diff** | Done | `routers/admin.py` |
| **Diagnostics** (arcturus doctor) | Done | `ops/admin/diagnostics.py` |
| **Sessions API** | Done | `ops/admin/spans_repository.py` |
| **Throttle policy** (hourly/daily budgets) | Done | `ops/admin/throttle.py` |
| **Admin auth** (`X-Admin-Key` header guard) | Done | `routers/admin.py` |
| **Frontend panels** (Flags, Config, Diagnostics) | Done | `features/admin/components/` |

### P14.5 — Audit & Compliance (Days 16–20)

| Component | Status | Location |
|-----------|--------|----------|
| **AuditLogger** (MongoDB + JSONL fallback) | Done | `ops/audit/audit_logger.py` |
| **AuditRepository** (query by time/action/resource) | Done | `ops/audit/audit_logger.py` |
| **SessionDataManager** (GDPR export/delete across 6 stores) | Done | `ops/audit/data_manager.py` |
| **Audit API** (`GET /admin/audit`) | Done | `routers/admin.py` |
| **GDPR endpoints** (`GET/DELETE /admin/data/{session_id}`) | Done | `routers/admin.py` |
| **AuditLogPanel (dashboard)** | Done | `features/admin/components/AuditLogPanel.tsx` |

### Span Hierarchy (implemented)

```
run.execute
└── agent_loop.run
    ├── agent_loop.plan
    ├── agent_loop.execute_dag
    │   ├── agent_loop.execute_node_{agent_type}_{step_id}
    │   │   └── agent_loop.iteration_{agent_type}_{step_id}_{turn}
    │   │       ├── llm.generate
    │   │       ├── code.execution
    │   │       └── sandbox.run
    │   └── ...
    └── ...
```

---

## 2. MongoDB Schema for Tracing

**Database:** `watchtower`  
**Collection:** `spans`

### Document shape

```json
{
  "trace_id": "032x hex string (32 chars)",
  "span_id": "016x hex string (16 chars)",
  "parent_span_id": "016x hex string or null",
  "name": "span name (e.g. run.execute, llm.generate)",
  "start_time": "ISODate",
  "end_time": "ISODate",
  "duration_ms": "number",
  "status": "ok | error",
  "attributes": {
    "run_id": "string",
    "session_id": "string",
    "query": "string (truncated)",
    "agent": "string (e.g. ThinkerAgent)",
    "node_id": "string",
    "step_id": "string",
    "model": "string",
    "provider": "string",
    "prompt_length": "number",
    "cost_usd": "number",
    "input_tokens": "number",
    "output_tokens": "number",
    "code_preview": "string",
    "code_variant_keys": "string",
    "resumed": "True",
    "resumed_at": "ISO timestamp",
    "retry_attempt": "number",
    "is_retry": "True",
    "iteration": "number",
    "max_turns": "number"
  }
}
```

### Indexes (created by `MongoDBSpanExporter._ensure_indexes`)

| Index | Purpose |
|-------|---------|
| `trace_id` | Look up all spans for a trace |
| `attributes.run_id` | Filter by run |
| `attributes.session_id` | Filter by session |
| `(start_time, -1)` | Time-range queries |

---

## 3. Config: Watchtower

**Current:** `config/settings.json` has `"enabled": true`.

```json
"watchtower": {
  "enabled": true,
  "mongodb_uri": "mongodb://localhost:27017",
  "jaeger_endpoint": "http://localhost:4318/v1/traces",
  "service_name": "arcturus",
  "health_check_interval_seconds": 60,
  "alert_rules": []
}
```

Optional config keys (use defaults when absent):

| Key | Default | Purpose |
|-----|---------|---------|
| `cost_pricing` | Built-in defaults | Per-model/provider pricing |
| `throttle.daily_budget_usd` | 10.0 | Daily cost budget |
| `throttle.hourly_budget_usd` | 2.0 | Hourly cost budget |
| `admin_api_key` | None (dev mode) | `X-Admin-Key` auth |

---

## 4. Test Coverage

### Acceptance tests (34 tests)

```bash
uv run pytest tests/acceptance/p14_watchtower/test_trace_path_is_complete.py -v
```

- 8 contract tests (charter, demo script, delivery readme, CI)
- 26 admin API tests (traces, cost, errors, health, flags, cache, config, diagnostics, sessions, audit, GDPR, auth)

### Integration tests (18 tests)

```bash
uv run pytest tests/integration/test_watchtower_with_gateway_api_usage.py -v
```

- 5 contract tests
- 8 admin API wiring + ops module tests
- 5 P14.5 tests (audit logger, JSONL fallback, session data manager, auth middleware)

### Unit tests

| File | Covers |
|------|--------|
| `tests/unit/ops/test_health.py` | Health checks, resource snapshot |
| `tests/unit/ops/test_health_scheduler.py` | HealthScheduler lifecycle |
| `tests/unit/ops/test_health_repository.py` | HealthRepository save/history/uptime |
| `tests/unit/ops/test_health_alerts.py` | AlertEvaluator, AlertRule, LogNotifier |
| `tests/unit/ops/test_cost_calculator.py` | ConfigurableCostCalculator |

---

## 5. Remaining Minor Gaps (Non-Blocking)

| Gap | Severity | Notes |
|-----|----------|-------|
| No unit tests for `ops/tracing` | Low | Covered by acceptance/integration |
| No unit tests for `ops/admin` modules | Low | Covered by acceptance/integration |
| `MongoDBSpanExporter.shutdown()` is empty | Low | No client close on shutdown |
| `ops/health/__init__.py` doesn't export all classes | Low | Direct imports work |
| No `cost_pricing` in settings.json | Low | Built-in defaults are functional |
| No `admin_api_key` in settings.json | Low | Dev mode works without it |
| `PUT /admin/config` (live config write) | Medium | Read-only config for now |
| Per-user/group feature flags | Medium | Only global toggles exist |
| Throttle not enforced in agent loop | Medium | Only reportable via admin API |
| Hardcoded Jaeger URL in TracesPanel | Low | `http://localhost:16686` |
| No refresh buttons on Traces/Cost/Errors panels | Low | Health panel has auto-refresh |
| No URL-based admin tab routing | Low | Tab state via React state only |

---

## 6. Key Files

| Purpose | File |
|---------|------|
| **Tracing init** | `api.py` (lifespan), `ops/tracing/core.py` |
| **Span definitions** | `ops/tracing/spans.py` |
| **Span context** | `ops/tracing/context.py` |
| **Trace helpers** | `ops/tracing/helpers.py` |
| **MongoDB exporter** | `ops/tracing/core.py` (MongoDBSpanExporter) |
| **Cost calculator** | `ops/cost/calculator.py`, `ops/cost/pricing.py` |
| **Health checks** | `ops/health/checks.py` |
| **Health scheduler** | `ops/health/scheduler.py` |
| **Health repository** | `ops/health/repository.py` |
| **Health alerts** | `ops/health/alerts.py` |
| **Feature flags** | `ops/admin/feature_flags.py` |
| **Diagnostics** | `ops/admin/diagnostics.py` |
| **Throttle policy** | `ops/admin/throttle.py` |
| **Spans repository** | `ops/admin/spans_repository.py` |
| **Audit logger** | `ops/audit/audit_logger.py` |
| **GDPR data manager** | `ops/audit/data_manager.py` |
| **Admin API (all endpoints)** | `routers/admin.py` |
| **Metrics (session files)** | `core/metrics_aggregator.py`, `routers/metrics.py` |
| **Cost in loop** | `core/loop.py` (accumulated_cost, warn, max) |
| **Cost in LLM** | `core/model_manager.py` (llm_span) |
| **Admin Dashboard UI** | `features/admin/AdminDashboard.tsx` (9 tabs) |
| **Admin UI panels** | `features/admin/components/`: TracesPanel, CostPanel, ErrorsPanel, HealthPanel, FlagsPanel, ConfigPanel, DiagnosticsPanel, AuditLogPanel, CachePanel |
| **Feature flags config** | `config/feature_flags.json` |
| **Stats UI** | `components/stats/StatsModal.tsx` |
| **Config** | `config/settings.json` (watchtower block) |

---

## 7. Quick Demo

```bash
# 1. Ensure watchtower.enabled is true in config/settings.json
# 2. Start infra
cd Arcturus && docker compose up -d mongodb jaeger

# 3. Start app
cd platform-frontend && npm run dev:all

# 4. Run a query in UI

# 5. View traces
# Jaeger: http://localhost:16686
# Admin API: curl http://localhost:8000/api/admin/traces
# Admin Dashboard: open sidebar → Shield icon → Watchtower Admin
```
