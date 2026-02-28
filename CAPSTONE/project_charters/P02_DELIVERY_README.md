# P02 Delivery README

## 1. Scope Delivered

- **Project Goal:** Build an answer engine matching Perplexity, adding Deep Research, Multimodal, and Internal Search.

### Deep Research

- **Deep Research Skill** (`core/skills/library/deep-research/skill.py`) — New 6-phase iterative research pipeline (decompose → broad search → gap analysis → targeted search → synthesis → report generation) registered with PlannerAgent
- **Search Module** (`search/`) — Standalone research backbone: query decomposer (3-8 sub-queries via LLM), crawl pipeline (parallel web search + content extraction reusing `smart_search`/`smart_web_extract`), multi-source synthesizer with inline citations and confidence scoring, deep research orchestrator (up to 5 iterations with gap-driven loops), graph bridge for canvas sync
- **6 Focus Modes** (`search/focus_modes.py`) — Domain-specific search configs (web, academic, news, code, finance, writing) with tailored search suffixes, retriever instructions, citation formats, and decomposition hints
- **Search REST API** (`routers/search.py`) — 5 new endpoints: `GET /api/search/focus-modes`, `POST /api/search/decompose`, `POST /api/search` (quick), `POST /api/search/deep` (SSE streaming), `POST /api/search/{run_id}/stop`
- **Frontend Search Feature** (`platform-frontend/src/features/search/`) — TypeScript types, API hooks (`useSearchApi`), SSE streaming hook (`useSearchStream`), composable search hook (`useSearch`)
- **Research Progress UI** (`platform-frontend/src/components/graph/ResearchProgress.tsx`) — Draggable/collapsible overlay on graph canvas showing URL extraction progress bar, live agent activity log with spinners, completed URLs with domain names, auto-scroll
- **Agent Base Enhancements** (`agents/base_agent.py`) — `exclude_skills` parameter for selective skill loading; JSON parse fallback wrapping raw text in expected output keys for FormatterAgent/SummarizerAgent
- **Core Loop Deep Research Engine** (`core/loop.py`) — `_expand_deep_research_dag()` method for engine-driven phase-by-phase DAG expansion; research_mode/focus_mode parameters; flexible edge format handling (arrays, dicts, from/to fallback); iteration limit scaling (3x + min 15 for deep research); pending/running step cleanup on loop end; plan output normalization (auto-wraps top-level nodes/edges)
- **Summarizer Citation System** (`core/skills/library/summarizer/skill.py`) — Inline `[N]` citation tagging, per-paragraph confidence scoring (HIGH/MEDIUM/LOW), contradiction detection with both perspectives, source agreement map, complete citation list format
- **Retriever Deep Research Mode** (`core/skills/library/retriever/skill.py`) — `search_web_with_text_content` guidance for deep research preserving `{url, content, rank}`, configurable result count up to 20
- **Planner Edge Format** (`core/skills/library/planner/skill.py`) — Standardized edge format as objects `{"source": "...", "target": "..."}` with critical note against array format
- **Browser MCP** (`mcp_servers/server_browser.py`) — Configurable `integer` parameter (1-20) for `search_web_with_text_content`; model provider updated to Ollama/gemma3:12b for browser-use
- **Memory/Context Robustness** (`memory/context.py`) — Type-safe result extraction (handles list/primitive); missing property initialization in `from_deserialized` (stop_requested, api_mode, user_input_event, etc.)
- **Frontend State Management** (`platform-frontend/src/store/index.ts`) — `ResearchProgressState` interface tracking phases, node statuses, URL extraction progress, step labels; query approval flow (pendingQueryApproval, approveQueries, dismissQueryApproval); event stream parsing for `dag_expanded`/`step_start` events
- **Sidebar UI** (`platform-frontend/src/components/layout/Sidebar.tsx`) — Research mode selector (Standard/Deep Research dropdown), focus mode selector (6 options, shown only when Deep Research selected)
- **Frontend API Client** (`platform-frontend/src/lib/api.ts`) — `createRun` extended with `mode` and `focus_mode` parameters
- **Run Router** (`routers/runs.py`) — `RunRequest` extended with `mode`/`focus_mode` fields; `QueryApprovalRequest` model; robust output extraction (checks markdown_report, formatted_report_*, final_answer, output keys)
- **Skills Registry** (`core/skills/registry.json`) — `deep_research` skill registered with path, version, class_name
- **Agent Config** (`config/agent_config.yaml`) — `deep_research` added to PlannerAgent skills list
- **User Preferences Hub** (`memory/user_model/preferences_hub.json`) — Schema for stable defaults, output contract, anti-preferences, tooling defaults, autonomy/risk, coding contracts

### Multimodal & Internal Search

- `Multimodal Search` handling Vision Q&A (local images), PDFs, and CSV data modeling (via `server_multimodal.py`).
- `Internal Knowledge Search` handling filesystem search and episodic memory queries (via `server_internal.py`).

## 2. Architecture Changes

### Deep Research

- **Deep Research as Engine-Driven DAG Expansion** — Instead of a static plan, `loop.py` builds the execution graph phase-by-phase: after each phase completes, the engine reads outputs, decides the next phase, and appends new nodes/edges. The frontend sees nodes appear in real-time.
- **Standalone Search Module** — New `search/` package provides research capabilities independent of the agent loop: query decomposition → parallel crawl → synthesis. Can be used via REST API without running a full agent session.
- **Focus Modes as Composable Domain Filters** — Six pre-configured research profiles modify search queries (site: operators), retriever instructions, citation formats, and decomposition hints. Applied at both decomposition and retrieval stages.
- **SSE Streaming for Real-Time Progress** — Deep research streams `DeepResearchEvent` objects via Server-Sent Events. Frontend uses `fetch + ReadableStream` (not EventSource) to support JSON POST bodies.
- **Graph Bridge for Canvas Visualization** — `search/graph_bridge.py` writes networkx-compatible session JSON so the canvas displays research phases (Thinker → Retrievers → Synthesizer → Formatter) identically to agent runs.
- **Skill Exclusion Mechanism** — `base_agent.run_agent()` accepts `exclude_skills` list; standard mode passes `exclude_skills=["deep_research"]` to prevent planner from generating research plans in non-research runs.
- **Agent Role Segregation** — Clear rules in deep research: RetrieverAgent for search (never CoderAgent), ThinkerAgent for analysis, SummarizerAgent for synthesis, FormatterAgent for reports.
- **JSON Parse Fallback** — Lightweight models returning plain text instead of JSON are gracefully handled by wrapping raw output in expected output keys.

### Multimodal & Internal Search

- Created `mcp_servers/server_multimodal.py` for image parsing, PDF breakdown, and CSV data extraction using Gemini models and standard libs.
- Created `mcp_servers/server_internal.py` for local context and bridging to past conversations.
- Updated `mcp_servers/mcp_config.json` to expose these servers globally.
- Implemented `focus_mode: "internal"` into the Deep Research phase to specifically fetch from the local workspace footprint.

## 3. API And UI Changes

### Deep Research

**New Backend Endpoints:**

- `GET /api/search/focus-modes` — List all available focus modes with labels and descriptions
- `POST /api/search/decompose` — Preview query decomposition into sub-queries without executing search
- `POST /api/search` — Quick search: single-iteration decompose → crawl → synthesize, returns markdown + citations
- `POST /api/search/deep` — Deep research with SSE streaming: multi-iteration with gap analysis
- `POST /api/search/{run_id}/stop` — Gracefully stop in-progress deep research

**Modified Backend Endpoints:**

- `POST /api/runs` — Extended `RunRequest` with `mode` ("standard"|"deep_research") and `focus_mode` fields

**Frontend UI Changes:**

- Sidebar: Research mode dropdown (Standard Research / Deep Research)
- Sidebar: Focus mode dropdown (General, Academic, News, Code, Finance, Writing) — visible only when Deep Research selected
- Graph Canvas: ResearchProgress overlay — draggable, collapsible widget showing URL extraction progress bar, live agent activity with spinners, completed URLs with domain names
- Store: ResearchProgressState tracking phases, node statuses, URL extraction, step labels; query approval modal

### Multimodal & Internal Search

- Exposed new internal/multimodal tooling to existing agents without altering frontend contract.
- Added new MCP server registration.

## 4. Mandatory Test Gate Definition

- Acceptance file: `tests/acceptance/p02_oracle/test_citations_back_all_claims.py`
- Integration file: `tests/integration/test_oracle_source_diversity.py`
- CI check: `p02-oracle-research` in `.github/workflows/project-gates.yml`

## 5. Test Evidence

### Backend (Python)

```text
$ pytest tests/ -v
309 passed, 2 skipped, 3 warnings in 34.68s
```

- **309 passed** — all acceptance, integration, and unit tests green
- **2 skipped** — `test_production_build` (requires `RUN_BUILD_TESTS=1`), `test_self_correction` (requires `RUN_EXTERNAL_TESTS=1`)
- **0 failures**

### Frontend (Vitest)

```text
$ cd platform-frontend && npm test
vitest run

 ✓ src/__tests__/prompt.test.ts (4 tests)
 ✓ src/__tests__/parsing.test.ts (9 tests)
 ✓ src/__tests__/security.test.ts (44 tests)
 ✓ src/__tests__/tool_reliability.test.ts (11 tests)
 ✓ src/__tests__/agent_tool_tests.test.ts (43 tests)

Test Files  5 passed (5)
     Tests  111 passed (111)
  Duration  1.56s
```

- **111 passed** — all frontend tests green
- **0 failures**

### Multimodal & Internal Tests

- Created `tests/integration/test_oracle_multimodal_internal.py` to validate module loading.
- Passes all standard feature branching CI logic.

### CI Workflow

```text
$ cat .github/workflows/project-gates.yml | grep p02
  - check_name: p02-oracle-research
    acceptance: tests/acceptance/p02_oracle/test_citations_back_all_claims.py
    integration: tests/integration/test_oracle_source_diversity.py
```

- CI check `p02-oracle-research` is wired in `.github/workflows/project-gates.yml`
- Both acceptance and integration test files exist and pass locally

## 6. Existing Baseline Regression Status

- Backend: `pytest tests/ -v` → **309 passed, 2 skipped, 0 failures** (34.68s)
- Frontend: `npm test` → **111 passed, 0 failures** (1.56s)
- CI: `p02-oracle-research` wired in `.github/workflows/project-gates.yml`
- Validated via local tests. The newly introduced servers run as FastMCP independent instances and do not negatively impact the main backend or orchestrator latency.

## 7. Security And Safety Impact

### Deep Research

- No new authentication/authorization surfaces — search endpoints inherit existing session context
- URL extraction uses existing `smart_web_extract` with 8s timeout per URL — no unbounded network calls
- SSE streaming uses AbortController for cleanup — no dangling connections
- User preferences hub stores no credentials — schema only
- Focus mode configs are static — no user-injectable search operators
- No new secrets or API keys introduced (browser-use model uses local Ollama instance)

### Multimodal & Internal Search

- `search_workspace_files` strictly filters by a safe whitelist of file extensions (`.py`, `.md`, `.txt`, `.json`, etc.) implicitly preventing the reading of `.env` files or binary secrets.
- `search_workspace_files` automatically drops system directories like `.git` and `venv` preventing path-traversing denial of service by hanging on recursive loops.
- `analyze_data_file` strictly limits tabular analysis to `.csv` format and only sends statistical summaries (not full row data) to the LLM to prevent PII leakage on large datasets.
- Vision and PDF parsing operations run locally before sending base64 payloads to Google Gemini, heavily relying on the enterprise API data-privacy wrapper.

## 8. Known Gaps

### Deep Research

- Query approval gate (interactive gap iteration approval) is foundational but not wired to a UI modal yet
- Search cache layer (`search/cache.py`) is scaffolded but not fully integrated
- Deep research iteration count is hardcoded (max 5) — not user-configurable via UI
- No rate limiting on search endpoints
- Browser-use model hardcoded to Ollama/gemma3:12b — requires local Ollama instance

### Multimodal & Internal Search

- Currently, large tabular analysis depends strictly on CSVs; XLSX binary ingestion requires manual CSV pre-processing.
- High-resolution images sent to LLMs might throw payload size limits if sent raw without proper downsizing.

## 9. Rollback Plan

### Deep Research

- Feature is fully opt-in: `mode: "standard"` (default) bypasses all deep research code paths
- Search endpoints are additive — removing `routers/search.py` and its include in `api.py` disables the feature
- Skill exclusion ensures standard agent runs are unaffected
- Frontend search UI components are isolated — removing `features/search/` and `ResearchProgress.tsx` reverts UI
- No database migrations or schema changes to roll back

### Multimodal & Internal Search

- Revert `server_multimodal.py` and `server_internal.py` from `mcp_servers`.
- Remove instructions from `core/skills/library/retriever/skill.py`.

## 10. Demo Steps

### Deep Research Demo

- Script: `scripts/demos/p02_oracle.sh`
- Expected acceptance: `tests/acceptance/p02_oracle/test_citations_back_all_claims.py`
- Expected integration: `tests/integration/test_oracle_source_diversity.py`

**Manual Demo:**

1. Start the backend: `python api.py`
2. Start the frontend: `cd platform-frontend && npm run dev`
3. Open the UI in a browser
4. Click "New Run" in the sidebar
5. Select **Deep Research** from the Research Mode dropdown
6. Choose a focus mode (e.g., Academic, News, Code)
7. Enter a research query (e.g., "What are the latest advances in transformer architectures for long-context reasoning?")
8. Observe the real-time Research Progress overlay on the graph canvas — URL extraction progress, agent activity with spinners
9. Watch the canvas populate with research phase nodes (Thinker → Retrievers → Synthesizer → Formatter)
10. Review the final report with inline citations `[N]`, confidence scores, and source list

### Multimodal & Internal Search Demo

1. Open the UI and test dropping a PDF or CSV file into the browser.
2. Activate focus mode "internal" and ask about past memory context.
