# P14 Watchtower — Day 1–5 Delivery README

**Project:** P14 Watchtower — Admin, Observability & Operations Dashboard  
**Scope:** Days 1–5 — Core tracing/metrics dashboard  
**Branch:** p14_week1_kamran

---

## 1. Scope Delivered

Core distributed tracing and metrics dashboard for agent runs:

- **OpenTelemetry integration** — Spans exported to MongoDB and Jaeger (OTLP HTTP)
- **End-to-end run tracing** — User query → planner → agent DAG → tool calls → response
- **Span hierarchy** — `run_span` → `agent_loop_run_span` → `agent_plan_span` → `agent_execute_dag_span` → `agent_execute_node_span` → `agent_iteration_span` → `llm_span` / `code_execution_span` / `sandbox_run_span`
- **Resume support** — Traces linked by `run_id` and `session_id` for resumed runs
- **Admin API** — Query traces and metrics from MongoDB
- **Fallback UI** — HTML page at `/api/admin/traces/view` when Jaeger is not running

### Jaeger Trace Visualization

![Jaeger trace: arcturus run.execute](p14_jaeger_trace.png)

*Full trace of a run: `run.execute` → `agent_loop_run` → planner, DAG execution, agent iterations (RetrieverAgent, ThinkerAgent, ChatGenAgent, FormatterAgent), `lm.generate` and `code.execution` spans. Duration ~1m 21s, 28 spans, depth 7.*

---

## 2. Architecture Changes

| Component | Change |
|----------|--------|
| `ops/tracing/` | New package: `core.py` (MongoDB + Jaeger exporters), `spans.py` (decorators), `context.py` (span context), `helpers.py` (plan-graph attachment) |
| `api.py` | Lifespan bootstrap: `init_tracing()` + FastAPIInstrumentor |
| `core/loop.py` | Instrumented with `run_span`, `agent_loop_run_span`, `agent_plan_span`, `agent_execute_dag_span`, `agent_execute_node_span`, `agent_iteration_span` |
| `core/model_manager.py` | `llm_span` around LLM calls |
| `core/sandbox/executor.py` | `sandbox_run_span` with security/execution error capture |
| `memory/context.py` | `code_execution_span` for code runs |
| `routers/admin.py` | New admin router: `/admin/traces`, `/admin/traces/{trace_id}`, `/admin/metrics/summary`, `/admin/traces/view` |
| `routers/runs.py` | Wrapped with `run_span`; agent execution uses tracing spans |
| `docker-compose.yml` | Added `mongodb` and `jaeger` services |
| `config/settings.json` | Added `watchtower` block: `enabled`, `mongodb_uri`, `jaeger_endpoint` |

---

## 3. API And UI Changes

### Admin API (no auth in Days 1–5)

| Endpoint | Method | Description |
|----------|--------|--------------|
| `/api/admin/traces` | GET | List traces (optional: `run_id`, `limit`, `since`) |
| `/api/admin/traces/{trace_id}` | GET | Full span tree for a trace |
| `/api/admin/metrics/summary` | GET | Aggregates: total traces, avg duration, error count (optional: `hours`) |
| `/api/admin/traces/view` | GET | HTML fallback page with link to Jaeger UI |

### Settings

```json
"watchtower": {
  "enabled": true,
  "mongodb_uri": "mongodb://localhost:27017",
  "jaeger_endpoint": "http://localhost:4318/v1/traces"
}
```

### Span Attributes

- `run_id`, `session_id` — Correlate spans across resumed runs
- `agent_name`, `step_id`, `agent_prompt` — Agent context
- `plan_graph` — Attached for planner spans
- `code_preview`, `session_id` — Sandbox execution context

---

## 4. Mandatory Test Gate Definition

- **Acceptance file:** `tests/acceptance/p14_watchtower/test_trace_path_is_complete.py`
- **Integration file:** `tests/integration/test_watchtower_with_gateway_api_usage.py`
- **CI check:** `p14-watchtower-ops`

---

## 5. Test Evidence

| Test Suite | Status | Notes |
|------------|--------|-------|
| `tests/acceptance/p14_watchtower/test_trace_path_is_complete.py` | 8 tests | Charter, demo script, delivery README, CI wiring |
| `tests/integration/test_watchtower_with_gateway_api_usage.py` | 5 tests | Integration file, baseline script, workflow wiring |
| `scripts/test_all.sh quick` | Baseline | Regression suite |

---

## 6. Existing Baseline Regression Status

- **Command:** `scripts/test_all.sh quick`
- **Status:** Run as part of CI gate `p14-watchtower-ops`

---

## 7. Security And Safety Impact

- Admin endpoints are **unauthenticated** in Days 1–5 (per charter). Auth planned for Days 11–15.
- Trace data may include prompts and outputs; stored in MongoDB. Ensure MongoDB is not exposed publicly.
- Jaeger UI (port 16686) is local-only by default.

---

## 8. Known Gaps

- No auth on admin API
- Cost analytics (Days 6–10)
- Health monitoring dashboard (Days 6–10)
- Admin controls and throttling (Days 11–15)
- Trace completeness assertions in acceptance tests (scaffold only)
- Integration tests do not yet prove “Gateway/API paths, MCP health, core loop spans in one correlated view”

---

## 9. Rollback Plan

1. Set `watchtower.enabled: false` in `config/settings.json`
2. Restart API — tracing will not initialize
3. Remove `routers/admin.py` from app if admin routes must be disabled
4. Revert commits: `3ab61b2`, `1ce102b`, `0da9b7a`, `a40eec4` if full rollback needed

---

## 10. Demo Steps

**Script:** `scripts/demos/p14_watchtower.sh`

### Manual Demo

1. Start infrastructure:
   ```bash
   cd Arcturus && docker-compose up -d
   ```

2. Start app:
   ```bash
   npm run electron:dev:all
   ```

3. Run a query in the UI (e.g. “Plan me an evening for savoring Bangalore Ramadan”).

4. View traces:
   - **Jaeger UI:** http://localhost:16686 — select service `arcturus`, Find Traces
   - **Admin API:** `curl http://localhost:8000/api/admin/traces`
   - **Fallback:** http://localhost:8000/api/admin/traces/view

5. Check metrics:
   ```bash
   curl "http://localhost:8000/api/admin/metrics/summary?hours=24"
   ```

---

## Commits (Day 1–5)

| Commit | Description |
|--------|-------------|
| `3ab61b2` | Add OpenTelemetry tracing integration with MongoDB and Jaeger support |
| `1ce102b` | Simplify code, isolate common logic, add agent name/prompt/output attributes |
| `0da9b7a` | Fix resume functionality when agent errored without completion |
| `a40eec4` | Enhance tracing and error handling in agent execution and sandbox operations |
