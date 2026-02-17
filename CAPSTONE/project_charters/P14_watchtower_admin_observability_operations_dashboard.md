# PROJECT 14: "Watchtower" — Admin, Observability & Operations Dashboard


> **Inspired by:** OpenClaw (Control UI, Doctor, logging), Perplexity (usage tracking), existing scaling plan (Projects "Watchtower" + "Control")
> **Team:** Operations & DevOps · **Priority:** P1 · **Duration:** 4 weeks

### Objective
Build a comprehensive **admin and observability platform** for monitoring agent performance, user activity, costs, errors, and system health — essential for scaling to 100k users.

### Detailed Features

#### 14.1 Distributed Tracing
- **OpenTelemetry integration:** Instrument all agent operations with traces, spans, and metrics
- **End-to-end request tracing:** See exact path: user message → channel → gateway → agent loop → tool calls → response
- **Latency breakdown:** P50/P90/P99 latencies per operation (LLM call, tool execution, memory lookup)
- **Error correlation:** Automatically link errors to their root causes across services

#### 14.2 Cost Analytics
- **Per-user cost tracking:** Token usage, API calls, compute time per user
- **Per-feature cost breakdown:** Cost per search, per page generation, per session
- **Budget alerts:** Configurable spending thresholds with email/Slack notifications
- **Cost optimization suggestions:** AI-powered recommendations to reduce costs (model switching, caching)

#### 14.3 Health Monitoring
- **Service health dashboard:** Real-time status of all components (agent core, MCP servers, memory, gateway)
- **Uptime tracking:** SLA monitoring with incident timeline
- **Resource usage:** CPU, memory, disk, network usage per component
- **Alert rules:** Configurable alerts (PagerDuty, Slack, email) for anomalies

#### 14.4 Admin Controls
- **User management:** View users, session history, usage stats, ban/suspend capabilities
- **Feature flags:** Toggle features per user/group/globally
- **Cache management:** View and flush semantic caches, memory stores
- **Config management:** Live config updates without restart
- **Diagnostics:** `arcturus doctor` — automated health check and repair suggestions

#### 14.5 Audit & Compliance
- **Action log:** Every state-changing operation logged with actor, action, timestamp, context
- **Data export:** GDPR-compliant data export and deletion
- **Access control:** Role-based access for admin dashboard (SuperAdmin, Admin, Viewer)

#### 14.6 Deliverables
- `ops/tracing.py` — OpenTelemetry instrumentation decorators
- `ops/cost_tracker.py` — per-user, per-feature cost tracking
- `ops/health.py` — service health monitor with alerting
- `ops/admin.py` — user management and feature flag APIs
- `ops/audit.py` — compliance-grade audit logging
- Frontend: `features/admin/` — admin dashboard with grafana-style panels
- `routers/admin.py` — admin API endpoints

### Strategy
- Use OpenTelemetry Python SDK — instrument `core/loop.py`, all routers, MCP servers
- Cost tracking as middleware — intercept all LLM API calls for token counting
- Admin dashboard as a separate authenticated route (not exposed to regular users)

---

## 20-Day Execution Addendum

### Team Split
- Single owner: tracing dashboard, health controls, and ops audit exports.

### Day Plan
- Days 1-5: Core tracing/metrics dashboard.
- Days 6-10: Error and cost analytics views.
- Days 11-15: Admin controls and throttling policies.
- Days 16-20: Incident workflows and SLO reporting.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p14_watchtower/test_trace_path_is_complete.py`
- Integration: `tests/integration/test_watchtower_with_gateway_api_usage.py`
- CI required check: `p14-watchtower-ops`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. Trace completeness, cost accounting accuracy, alert trigger behavior, and admin control actions must each have acceptance tests with assertions.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Watchtower can observe Gateway/API paths, MCP health, and core loop spans in one correlated view.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p14-watchtower-ops must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P14_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 5s dashboard refresh for live metrics.
