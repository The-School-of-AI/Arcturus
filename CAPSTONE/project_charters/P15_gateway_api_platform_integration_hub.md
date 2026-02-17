# PROJECT 15: "Gateway" — API Platform & Integration Hub


> **Inspired by:** Perplexity (Search API, embeddings API), OpenClaw (webhooks, cron, Gmail Pub/Sub), existing scaling plan (Project "Nexus" AI Gateway)
> **Team:** API & Integration Engineering · **Priority:** P1 · **Duration:** 4 weeks

### Objective
Build a **developer-facing API platform** that exposes Arcturus's capabilities as APIs and provides a rich integration framework with webhooks, cron jobs, and third-party service connectors.

### Detailed Features

#### 15.1 Public API
- **Search API:** `/api/v1/search` — real-time web search with citations (uses Project 2)
- **Page Generation API:** `/api/v1/pages/generate` — generate Arcturus Pages programmatically
- **Document API:** `/api/v1/studio/{slides|docs|sheets}` — generate documents via API
- **Chat API:** `/api/v1/chat/completions` — OpenAI-compatible chat API backed by Arcturus agent
- **Embeddings API:** `/api/v1/embeddings` — generate embeddings for text using Arcturus's models
- **Memory API:** `/api/v1/memory/{read|write|search}` — programmatic access to knowledge spaces
- **Agent API:** `/api/v1/agents/run` — spawn an agent task and get results

#### 15.2 API Management
- **API keys:** Self-service API key generation with per-key rate limits and permissions
- **Rate limiting:** Token bucket algorithm with burst handling
- **Usage metering:** Per-key usage tracking with monthly billing
- **API documentation:** Auto-generated OpenAPI/Swagger docs + interactive playground
- **SDKs:** Official Python and TypeScript SDKs

#### 15.3 Webhooks & Events
- **Outbound webhooks:** Subscribe to agent events (task complete, error, memory update) and receive HTTP POST notifications
- **Inbound webhooks:** Trigger agent actions via incoming webhooks
- **Event types:** `agent.response`, `task.complete`, `task.error`, `memory.updated`, `session.started`, `session.ended`
- **Retry policy:** Exponential backoff with dead letter queue for failed deliveries

#### 15.4 Cron & Scheduled Tasks
- **Cron jobs:** Define recurring agent tasks: "Every Monday at 9am, generate weekly project summary"
- **Calendar integration:** Trigger tasks based on calendar events
- **One-off scheduling:** "In 2 hours, remind me to check the deployment"
- **Cron UI:** Visual cron job editor with natural language support

#### 15.5 Third-Party Integrations
- **Gmail Pub/Sub:** Real-time email notifications → agent processing
- **GitHub:** PR events, issue tracking, code review automation
- **Jira:** Ticket creation/updates from agent, project tracking integration
- **Notion:** Page creation/updates, database queries
- **Google Drive:** File access, document import/export
- **Salesforce:** CRM data access, record management
- **Zapier/Make:** Generic integration layer via webhooks for 1000+ apps

#### 15.6 MCP Server Registry
- **Remote MCP servers:** Connect to cloud-hosted MCP servers (Salesforce MCP, Notion MCP, etc.)
- **MCP discovery:** Directory of available MCP servers with auto-configuration
- **Custom MCP servers:** Documentation and toolkit for building custom MCP servers
- **SSE transport:** Server-Sent Events transport layer for remote MCP connections

#### 15.7 Deliverables
- `api/v1/` — versioned API endpoint handlers
- `api/auth.py` — API key management and authentication
- `api/rate_limiter.py` — token bucket rate limiter
- `api/metering.py` — usage metering and billing
- `api/webhooks.py` — webhook subscription and delivery engine
- `api/cron.py` — cron job scheduler (enhance existing `core/scheduler.py`)
- `integrations/` — third-party service adapters (Gmail, GitHub, Jira, etc.)
- `api/sdks/` — Python and TypeScript SDK packages
- Frontend: `features/api/` — API key management, webhook config, cron editor, docs browser

### Strategy
- Design API to be OpenAI-compatible where possible for ecosystem compatibility
- Existing `routers/` provide the foundation — wrap with API key auth and rate limiting
- Existing `core/scheduler.py` and `routers/cron.py` provide cron foundation — extend with persistent storage and UI

---

## 20-Day Execution Addendum

### Team Split
- Single owner: public APIs, webhook pipeline, cron and external integration contracts.

### Day Plan
- Days 1-5: API contracts and auth/rate-limit middleware.
- Days 6-10: Webhook events and signature validation.
- Days 11-15: Cron and scheduled task execution history.
- Days 16-20: SDK examples and third-party connector stabilization.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py`
- Integration: `tests/integration/test_gateway_to_oracle_spark_forge.py`
- CI required check: `p15-gateway-api`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. Public API auth, rate limits, webhook signatures/retries, and cron scheduling correctness (including timezone handling) must be covered.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Gateway endpoints successfully trigger Oracle/Spark/Forge flows and emit traceable event lifecycle records.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p15-gateway-api must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P15_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 300ms API gateway overhead (excluding model/tool latency).
