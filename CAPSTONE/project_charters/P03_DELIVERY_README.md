# P03 Spark Delivery README

## 1. Scope Delivered
- Implemented a Phase‑1 scaffold for Spark pages delivering the following features and artifacts:
  - Canonical page JSON schema and example
  - Deterministic Oracle mock for development and CI
  - Modular section-agent contracts (overview, detail, data, source)
  - Minimal multi-agent orchestrator to compose structured pages
  - File-based persistence for generated pages under `data/pages/`
  - HTTP endpoints to generate and retrieve pages (`routers/pages.py`)

**Delivered artifacts:**
  - `content/schema.md` — canonical page JSON schema and example
  - `content/oracle_client.py` — deterministic Oracle mock for development/CI
  - `content/section_agents/` — `overview_agent`, `detail_agent`, `data_agent`, `source_agent` (stubs)
  - `content/page_generator.py` — multi-agent orchestrator and persistence
  - `routers/pages.py` — API endpoints for page CRUD/generation
  - `data/pages/` — persisted generated page artifacts (file-based)
  - `tests/acceptance/p03_spark/test_structured_page_not_text_wall.py` — 8 acceptance cases

## 2. Architecture Changes
- **Backend**: added a `content/` submodule to host page generation logic and agent contracts.
- **Orchestrator**: `content/page_generator.py` launches the section agents in parallel, composes structured pages, and persists JSON artifacts for later retrieval.
- **Persistence**: file-based persistence under `data/pages/` for Phase‑1; designed to be replaceable by a DB later.
- **Testability**: `content/oracle_client.py` provides deterministic `search_oracle()` outputs for stable CI and local testing; production Oracle client to be integrated in Phase‑2.

## 3. API And UI Changes
- **New backend endpoints** (FastAPI):
  - `POST /api/pages/generate` — Accepts `{ "query": string, "template": string? }` and returns `{ page_id, page }`.
  - `GET  /api/pages/{page_id}` — Returns persisted page JSON.
- **Frontend**: no production UI shipped in Phase‑1. A React renderer in `platform-frontend/src/features/pages/` is planned for Phase‑2 and will render structured sections, tables, charts and an inline copilot control.

## 4. Mandatory Test Gate Definition
- **Acceptance**: `tests/acceptance/p03_spark/test_structured_page_not_text_wall.py` (contains 8 executable tests)
- **Integration**: `tests/integration/test_spark_oracle_data_pipeline.py` (integration scaffold; Phase‑2 will add scenarios)
- **CI check name**: `p03-spark-pages` (must be wired into `.github/workflows/project-gates.yml` for gating)

## 5. Test Evidence

### 5.1 Acceptance Tests (Phase‑1)
**Command:**
```bash
pytest tests/acceptance/p03_spark -q
```
**Notes:** The acceptance suite validates:
- Generated page is a structured JSON with multiple `sections` (not a single markdown wall).
- At least one `table` block is present (derived from Oracle `structured_extracts`).
- Sections reference citation ids which map into top-level `citations` metadata.
- Generated page persists to `data/pages/{page_id}.json` and is loadable via `GET /api/pages/{id}`.
- Agent stubs are deterministic: repeated runs with the same query produce identical section contents (idempotency).

### 5.2 Integration Smoke (local/mock)
**Command:**
```bash
pytest tests/integration/test_spark_oracle_data_pipeline.py -q
```
**Notes:** Integration scaffold verifies that Spark consumes Oracle outputs (mock) and maps `citation_id` → `page.citations` correctly. Full end‑to‑end tests with production Oracle are scheduled for Phase‑2.

## 6. Existing Baseline Regression Status
- **Run baseline**: `scripts/test_all.sh quick` — Phase‑1 changes are additive and use a mock Oracle to avoid external flakiness.
- **Local smoke**: start backend and run a sample generation (see Demo Steps) and acceptance tests above.

## 7. Security And Safety Impact
- **Input validation**: router enforces non-empty `query` payloads and returns `400` for malformed requests.
- **Safety**: Phase‑1 does not yet integrate the P12 Aegis safety layer; all LLM/agent calls must be protected by Aegis in Phase‑2 to prevent prompt injection and to apply content policies.

## 8. Known Gaps
- Replace `content/oracle_client` mock with production Oracle HTTP client and adapt to real `structured_extracts` schema.
- Implement LLM-backed agent logic in `content/section_agents/*` (currently stubs).
- Add frontend `features/pages/` renderer and UI components (SectionBlock, InlineCopilot, ExportControls).
- Implement `content/export.py` and Forge ingestion handoff with integration tests.
- Wire CI check `p03-spark-pages` into `.github/workflows/project-gates.yml`.

## 9. Rollback Plan
- Revert the feature branch PR to remove introduced files and API routes.
- Remove persisted artifacts under `data/pages/` if necessary.

## 10. Demo Steps
1. Start backend (development):
```bash
# from repo root (uses repo's uv helper/executable)
uv run api.py
```
2. Generate a page (example):
```bash
curl -sS -X POST http://localhost:8000/api/pages/generate \
  -H "Content-Type: application/json" \
  -d '{"query":"electric scooters 2026","template":"topic_overview"}' | jq
```
3. Retrieve page JSON by id returned in step (2):
```bash
curl http://localhost:8000/api/pages/<page_id> | jq
```
4. Run acceptance tests:
```bash
pytest tests/acceptance/p03_spark -q
```

**Expected acceptance:** `tests/acceptance/p03_spark/test_structured_page_not_text_wall.py`
**Expected integration:** `tests/integration/test_spark_oracle_data_pipeline.py`
