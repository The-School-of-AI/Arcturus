# P14 Watchtower — Architecture & Implementation Plan

**Purpose:** Holistic overview of data, APIs, dashboard, cost analysis, and admin setup for P14.  
**Use this to:** Ensure nothing is missed and build in the right order.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           P14 WATCHTOWER — DATA FLOW                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                      │
│  │ Agent Loop   │     │ LLM Calls    │     │ Sandbox      │                      │
│  │ core/loop.py │     │ model_mgr    │     │ executor     │                      │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘                      │
│         │                    │                    │                              │
│         └────────────────────┼────────────────────┘                              │
│                              ▼                                                   │
│                    ┌──────────────────┐                                         │
│                    │ OpenTelemetry    │                                         │
│                    │ TracerProvider   │                                         │
│                    └────────┬─────────┘                                         │
│                             │                                                    │
│              ┌──────────────┼──────────────┐                                     │
│              ▼              ▼              ▼                                     │
│     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                           │
│     │ MongoDB     │  │ Jaeger      │  │ (Future)     │                           │
│     │ watchtower  │  │ OTLP HTTP   │  │ Cost DB      │                           │
│     │ .spans      │  │ :4318       │  │              │                           │
│     └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                           │
│            │               │                │                                    │
│            ▼               ▼                ▼                                    │
│     ┌─────────────────────────────────────────────────────────┐                  │
│     │              Admin API (routers/admin.py)                │                  │
│     │  /traces, /traces/{id}, /metrics/summary, /traces/view   │                  │
│     └─────────────────────────────┬───────────────────────────┘                  │
│                                   │                                              │
│                                   ▼                                              │
│     ┌─────────────────────────────────────────────────────────┐                  │
│     │              Admin Dashboard (features/admin/)           │                  │
│     │  Traces | Cost | Health | Controls | Audit              │                  │
│     └─────────────────────────────────────────────────────────┘                  │
│                                                                                  │
│  PARALLEL PATH (existing, session-file based):                                    │
│  ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐          │
│  │ data/            │     │ MetricsAggregator│     │ /api/metrics/    │          │
│  │ conversation_    │ ──► │ core/            │ ──► │ dashboard        │          │
│  │ history/         │     │ metrics_          │     │                  │          │
│  │ session_*.json   │     │ aggregator.py    │     └────────┬─────────┘          │
│  └──────────────────┘     └──────────────────┘              │                   │
│                                                               ▼                   │
│                                                    ┌──────────────────┐           │
│                                                    │ StatsModal       │           │
│                                                    │ (Header button)   │           │
│                                                    └──────────────────┘           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. MongoDB Collections — Current & Planned

### 2.1 Current: `watchtower.spans`

**Purpose:** OpenTelemetry span storage for distributed tracing.

| Field | Type | Description |
|-------|------|--------------|
| `trace_id` | string (32 hex) | Trace ID |
| `span_id` | string (16 hex) | Span ID |
| `parent_span_id` | string or null | Parent span |
| `name` | string | e.g. `run.execute`, `llm.generate` |
| `start_time` | ISODate | |
| `end_time` | ISODate | |
| `duration_ms` | number | |
| `status` | `"ok"` \| `"error"` | |
| `attributes` | object | run_id, session_id, agent, model, prompt_length, etc. |

**Indexes:** `trace_id`, `attributes.run_id`, `attributes.session_id`, `(start_time, -1)`

**Populated by:** `ops/tracing/core.py` → `MongoDBSpanExporter`

---

### 2.2 Planned: `watchtower.cost_events` (Days 6–10)

**Purpose:** Per-LLM-call cost tracking for analytics.

| Field | Type | Description |
|-------|------|--------------|
| `trace_id` | string | Link to span |
| `span_id` | string | Link to llm.generate span |
| `run_id` | string | |
| `session_id` | string | |
| `timestamp` | ISODate | |
| `model` | string | e.g. gemini-2.5-flash |
| `provider` | string | gemini, ollama |
| `input_tokens` | int | |
| `output_tokens` | int | |
| `cost_usd` | float | |
| `agent` | string | e.g. ThinkerAgent |
| `step_id` | string | |

**Populated by:** New `ops/cost_tracker.py` — intercept in `llm_span` or `ModelManager` after each call.

**Note:** Cost/tokens already exist in `plan_graph.nodes` and chronicle `step_complete` events. The cost tracker would **also** write to MongoDB for queryable analytics.

---

### 2.3 Planned: `watchtower.health_checks` (Days 6–10)

**Purpose:** Service health snapshots.

| Field | Type | Description |
|-------|------|--------------|
| `timestamp` | ISODate | |
| `service` | string | agent_core, mongodb, qdrant, mcp_*, ollama |
| `status` | `"ok"` \| `"degraded"` \| `"down"` | |
| `latency_ms` | number | optional |
| `details` | object | optional error/message |

---

### 2.4 Planned: `watchtower.audit_log` (Days 16–20)

**Purpose:** State-changing admin actions.

| Field | Type | Description |
|-------|------|--------------|
| `timestamp` | ISODate | |
| `actor` | string | user/session id |
| `action` | string | e.g. feature_toggle, cache_flush |
| `resource` | string | e.g. feature:voice_enabled |
| `old_value` | any | |
| `new_value` | any | |
| `context` | object | |

---

## 3. Data Sources — What Exists Today

| Source | Location | Contains | Consumed By |
|--------|----------|----------|-------------|
| **MongoDB spans** | `watchtower.spans` | Traces, spans, duration, status | Admin API, Jaeger |
| **Session files** | `data/conversation_history/session_*.json` | Runs, nodes, cost, tokens, outcomes | MetricsAggregator → /api/metrics |
| **Chronicle checkpoints** | `memory/chronicle_checkpoints/` | step_complete events (cost, tokens) | Replay, resume |
| **Plan graph (runtime)** | In-memory during run | cost, input_tokens, output_tokens per node | Loop, checkpointing |

**Gap:** Cost/token data is in session files and chronicle, but **not** in MongoDB. Admin trace API has duration/errors, not cost. Metrics API has cost but reads from files, not MongoDB.

---

## 4. API Endpoints — Current vs Planned

### 4.1 Current

| Endpoint | Source | Purpose |
|----------|--------|---------|
| `GET /api/admin/traces` | MongoDB spans | List traces |
| `GET /api/admin/traces/{trace_id}` | MongoDB spans | Trace detail + span tree |
| `GET /api/admin/metrics/summary` | MongoDB spans | total_traces, avg_duration_ms, error_count |
| `GET /api/admin/traces/view` | — | HTML fallback page |
| `GET /api/metrics/dashboard` | Session files (MetricsAggregator) | Fleet metrics: cost, tokens, outcomes, agents |
| `POST /api/metrics/refresh` | Same | Force cache refresh |

### 4.2 Planned (Days 6–20)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/admin/cost/summary` | Cost by run, session, agent, model (from cost_events or spans) |
| `GET /api/admin/health` | Current health of services |
| `GET /api/admin/health/history` | Health check history |
| `POST /api/admin/feature-flags` | Toggle features |
| `POST /api/admin/cache/flush` | Flush caches |
| `GET /api/admin/audit` | Audit log query |

---

## 5. Dashboard Build Plan

### 5.1 Current UI

- **StatsModal** — Modal from Header; shows fleet metrics (cost, tokens, outcomes, agents, retries). Data: `/api/metrics/dashboard`.
- **Admin traces/view** — Simple HTML page linking to Jaeger. No React.

### 5.2 Target: `features/admin/` (Grafana-style)

**Recommended structure:**

```
platform-frontend/src/features/admin/
├── AdminDashboard.tsx      # Main layout, tabs
├── components/
│   ├── TracesPanel.tsx     # Trace list, drill-down, link to Jaeger
│   ├── CostPanel.tsx       # Cost by run/agent/model, trends
│   ├── HealthPanel.tsx     # Service status, uptime
│   ├── MetricsSummary.tsx  # Reuse/embed StatsModal logic or API
│   └── AuditLogPanel.tsx   # (Days 16–20)
├── hooks/
│   ├── useAdminTraces.ts
│   └── useAdminCost.ts
└── routes.ts               # /admin or /admin/* route
```

### 5.3 Build Order

| Phase | Deliverable | Depends On |
|-------|-------------|------------|
| **1. Dashboard shell** | `AdminDashboard.tsx`, route `/admin`, tab layout | — |
| **2. Traces panel** | TracesPanel: list traces, open detail, link to Jaeger | Admin API (exists) |
| **3. Metrics panel** | Embed or reuse StatsModal data; show in admin context | /api/metrics (exists) |
| **4. Cost panel** | Cost by run/agent; charts | Cost API + cost_events OR extend spans |
| **5. Health panel** | Service status grid | Health API + health_checks |
| **6. Auth** | Protect /admin routes | Days 11–15 |

---

## 6. Cost Analysis — How to Implement

### 6.1 Where Cost Is Already Computed

- **core/loop.py** — `plan_graph.nodes[n]['cost']`, `input_tokens`, `output_tokens` set on step completion.
- **core/model_manager.py** — LLM calls; token counts available from provider response.
- **config/agent** — `max_cost_per_run`, `warn_at_cost` for runtime limits.

### 6.2 Option A: Extend Spans (Minimal Change)

Add `cost_usd`, `input_tokens`, `output_tokens` to `llm_span` attributes. They already flow to MongoDB. Admin API can aggregate from spans:

```python
# In llm_span or ModelManager, after LLM call:
span.set_attribute("cost_usd", cost)
span.set_attribute("input_tokens", inp)
span.set_attribute("output_tokens", out)
```

Then add `GET /api/admin/cost/summary` that aggregates `llm.generate` spans by `attributes.agent`, `attributes.model`, time range.

### 6.3 Option B: Dedicated Cost Tracker (Charter)

- **ops/cost_tracker.py** — Middleware that records each LLM call to `watchtower.cost_events`.
- **Pricing config** — `config/cost_pricing.json` or in settings: $/1K tokens per model.
- **Budget alerts** — Days 6–10; optional Slack/email.

**Recommendation:** Start with Option A (extend spans). Add Option B if you need per-call granularity, alerts, or separate cost DB.

---

## 7. Admin Setup — Auth & Access

### 7.1 Current

- No auth on admin endpoints.
- Admin routes mounted at `/api/admin/`.

### 7.2 Planned (Days 11–15)

- **Auth** — JWT or session-based; admin role required.
- **Routes** — `/admin` protected; redirect to login if not authenticated.
- **Roles** — SuperAdmin, Admin, Viewer (per charter).

---

## 8. Phase-by-Phase Checklist

### Phase 1: Dashboard Shell (Now)

- [ ] Create `features/admin/AdminDashboard.tsx` with tab layout (Traces | Metrics | Cost | Health).
- [ ] Add route `/admin` in App/router.
- [ ] Add nav entry to open Admin (e.g. from Header or sidebar).
- [ ] TracesPanel: fetch `/api/admin/traces`, display table, link to `/api/admin/traces/{id}` and Jaeger.

### Phase 2: Enrich Traces + Cost in Spans

- [ ] Add `cost_usd`, `input_tokens`, `output_tokens` to `llm_span` in model_manager.
- [ ] Ensure these are in `attributes` in MongoDB (MongoDBSpanExporter already exports attributes).
- [ ] Add `GET /api/admin/cost/summary` aggregating from spans.

### Phase 3: Cost Panel

- [ ] CostPanel component: fetch cost summary, show by agent/model, time range.
- [ ] Charts: cost over time, cost by agent.

### Phase 4: Metrics Integration

- [ ] In Admin dashboard, add Metrics tab that uses `/api/metrics/dashboard` (same as StatsModal).
- [ ] Or embed StatsModal in admin context.

### Phase 5: Health (Days 6–10)

- [x] `ops/health/` package — periodic health checks (MongoDB, Qdrant, Ollama, MCP, Neo4J).
- [x] `watchtower.health_checks` collection + HealthRepository.
- [x] `GET /api/admin/health`, `/health/history`, `/health/uptime`, `/health/resources`.
- [x] HealthPanel in dashboard.
- [x] HealthScheduler for periodic checks.
- [x] Alert evaluation system.

### Phase 6: Admin Controls (Days 11–15)

- [x] Feature flags API (`GET/PUT/DELETE /admin/flags/{name}`) + `ops/admin/feature_flags.py`.
- [x] Cache list/flush API (`GET /admin/cache`, `POST /admin/cache/{name}/flush`).
- [x] Config view/diff API (`GET /admin/config`, `GET /admin/config/diff`).
- [x] Diagnostics / arcturus doctor (`GET /admin/diagnostics`) + `ops/admin/diagnostics.py`.
- [x] Sessions API (`GET /admin/sessions`).
- [x] Throttle policy (`GET/PUT /admin/throttle`) + `ops/admin/throttle.py`.
- [x] Frontend panels: FlagsPanel, ConfigPanel, DiagnosticsPanel.
- [ ] Auth for admin routes.
- [ ] Live config write endpoint (`PUT /admin/config`).
- [ ] Per-user/group feature flags.

### Phase 7: Audit (Days 16–20)

- [ ] `ops/audit.py` — log state-changing actions.
- [ ] `watchtower.audit_log` collection.
- [ ] AuditLogPanel.

---

## 9. P14 Charter Coverage — Checklist

| Charter Item | Status | Notes |
|--------------|--------|-------|
| **14.1 Distributed Tracing** | Done | Spans → MongoDB + Jaeger |
| **14.1 Latency P50/P90/P99** | Partial | Can derive from spans; no dedicated endpoint |
| **14.1 Error correlation** | Partial | status=error in spans; no root-cause UI |
| **14.2 Cost Analytics** | Done | Cost summary API (`/admin/cost/summary`) groups by agent/model; CostPanel in dashboard |
| **14.2 Per-user cost** | Partial | Per-session cost via `/admin/sessions`; no per-user identity |
| **14.2 Budget alerts** | Done | Throttle policy: hourly/daily budgets via `/admin/throttle` |
| **14.3 Health Monitoring** | Done | `ops/health/` module, HealthScheduler, `/admin/health`, `/admin/health/history`, `/admin/health/uptime`, `/admin/health/resources`, Neo4J checks |
| **14.4 Admin Controls** | Done (global) | Feature flags (global toggle), cache list/flush, config view/diff, diagnostics, sessions, throttle. No per-user/group flags, no ban/suspend, no admin auth |
| **14.5 Audit & Compliance** | Not started | Days 16–20 |
| **14.6 ops/cost_tracker.py** | Done (via spans) | Option A: cost_usd in span attributes + `ops/cost/ConfigurableCostCalculator` |
| **14.6 ops/health.py** | Done | `ops/health/`: health checks, HealthScheduler, alert evaluation, HealthRepository |
| **14.6 ops/admin.py** | Done | `ops/admin/`: feature_flags.py, diagnostics.py, throttle.py, spans_repository.py; routers/admin.py |
| **14.6 ops/audit.py** | Not started | |
| **14.6 features/admin/** | Done | AdminDashboard.tsx with 7 tabs: Traces, Cost, Errors, Health, Flags, Config, Diagnostics |

---

## 10. Quick Reference: Key Files

| Purpose | File |
|---------|------|
| Tracing init | `api.py` (lifespan), `ops/tracing/core.py` |
| Span definitions | `ops/tracing/spans.py` |
| MongoDB exporter | `ops/tracing/core.py` (MongoDBSpanExporter) |
| Admin API | `routers/admin.py` |
| Admin ops modules | `ops/admin/`: feature_flags.py, diagnostics.py, throttle.py, spans_repository.py |
| Health monitoring | `ops/health/`: health checks, HealthScheduler, alert evaluation, HealthRepository |
| Cost calculator | `ops/cost/` (ConfigurableCostCalculator) |
| Metrics (session files) | `core/metrics_aggregator.py`, `routers/metrics.py` |
| Cost in loop | `core/loop.py` (accumulated_cost, warn, max) |
| Cost in LLM | `core/model_manager.py` (llm_span) |
| Admin Dashboard UI | `features/admin/AdminDashboard.tsx` (7 tabs) |
| Admin UI panels | `features/admin/components/`: FlagsPanel, ConfigPanel, DiagnosticsPanel, TracesPanel, CostPanel, ErrorsPanel, HealthPanel |
| Feature flags config | `config/feature_flags.json` |
| Stats UI | `components/stats/StatsModal.tsx` |
| Config | `config/settings.json` (watchtower block) |
