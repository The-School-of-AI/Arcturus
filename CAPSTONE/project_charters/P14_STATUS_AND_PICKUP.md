# P14 Watchtower — Status Summary & Pickup Guide

**Last updated:** March 2025  
**Scope:** Days 1–5 delivered; Days 6–20 pending

---

## 1. Where We Were (Two Weeks Ago)

### Delivered (Days 1–5)

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

### Span hierarchy (implemented)

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

### Example query (admin API)

```javascript
// List traces
db.spans.aggregate([
  { $match: { "attributes.run_id": "optional_run_id" } },
  { $sort: { start_time: -1 } },
  { $limit: 500 },
  {
    $group: {
      _id: "$trace_id",
      spans: { $push: "$$ROOT" },
      start_time: { $min: "$start_time" },
      duration_ms: { $sum: "$duration_ms" },
      status: { $max: { $cond: [{ $eq: ["$status", "error"] }, 1, 0] } }
    }
  },
  { $sort: { start_time: -1 } },
  { $limit: 50 }
]);
```

---

## 3. Config: Watchtower

**Current:** `config/settings.json` has `"enabled": false`, so tracing is off.

To enable:

```json
"watchtower": {
  "enabled": true,
  "mongodb_uri": "mongodb://localhost:27017",
  "jaeger_endpoint": "http://localhost:4318/v1/traces",
  "service_name": "arcturus"
}
```

---

## 4. Where to Pick Up Now

### Immediate checks (after code changes)

1. **Enable tracing** (if desired): Set `watchtower.enabled: true` in `config/settings.json`.
2. **Run acceptance tests:**
   ```bash
   uv run pytest tests/acceptance/p14_watchtower/test_trace_path_is_complete.py -v
   ```
3. **Run integration tests:**
   ```bash
   uv run pytest tests/integration/test_watchtower_with_gateway_api_usage.py -v
   ```
4. **Verify instrumentation:** `core/loop.py` still imports and uses tracing spans. If the loop structure changed, confirm spans are still created in the right places.

### Known gaps (from P14_DELIVERY_README)

| Gap | Status | Next step |
|-----|--------|-----------|
| **Trace completeness assertions** | Acceptance tests are scaffold only | Add assertions that span hierarchy is present |
| **Gateway/API + MCP + core spans in one view** | Integration tests do not prove this | Add integration test that runs a run and checks traces in MongoDB |
| **Admin API auth** | None | Planned for Days 11–15 |
| **Cost analytics** | Not started | Days 6–10 |
| **Health monitoring** | Not started | Days 6–10 |
| **Admin controls** | Not started | Days 11–15 |

### Recommended next steps

1. **Re-enable tracing** and run a quick end-to-end test.
2. **Add trace completeness assertions** in acceptance tests (e.g. run a query, fetch traces, assert `run.execute` → `agent_loop.run` → `agent_loop.plan` exists).
3. **Integration test:** Start API, trigger a run, query MongoDB for spans with `trace_id`, assert expected span names.
4. **Days 6–10:** Cost analytics and error views.

---

## 5. Key Files

| File | Purpose |
|------|---------|
| `ops/tracing/core.py` | MongoDB exporter, `init_tracing`, `get_tracer` |
| `ops/tracing/spans.py` | Span context managers |
| `ops/tracing/context.py` | `set_span_context` / `get_span_context` |
| `ops/tracing/helpers.py` | `attach_plan_graph_to_span` |
| `routers/admin.py` | `/api/admin/traces`, `/api/admin/metrics/summary`, `/api/admin/traces/view` |
| `api.py` | Lifespan: `init_tracing()` + FastAPIInstrumentor |
| `core/loop.py` | Instrumented with all spans |
| `config/settings.json` | `watchtower` block |

---

## 6. Quick Demo

```bash
# 1. Enable watchtower in config/settings.json
# 2. Start infra
cd Arcturus && docker compose up -d mongodb jaeger

# 3. Start app
cd platform-frontend && npm run dev:all

# 4. Run a query in UI

# 5. View traces
# Jaeger: http://localhost:16686
# Admin API: curl http://localhost:8000/api/admin/traces
# Fallback: http://localhost:8000/api/admin/traces/view
```
