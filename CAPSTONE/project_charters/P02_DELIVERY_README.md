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

### Multimodal Search (2.5)

- **Dual-Provider File Extraction** (`routers/runs.py`) — Configurable multimodal extraction supporting two providers: OpenRouter (default, uses `OPENROUTER_API_KEY`) and Gemini File API (optional, uses `GEMINI_API_KEY`). Provider selection via `settings.file_extraction_provider`. Router function `_extract_multimodal_file` dispatches to `_extract_via_openrouter` (base64 vision API) or `_extract_via_gemini` (native file upload via `google.genai` SDK). Both providers raise `RuntimeError` on failure instead of silently returning error strings.
- **File Content Extraction Pipeline** (`routers/runs.py:_extract_file_content`) — Unified extraction for all file types: images (`.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`) and PDFs via multimodal provider; CSV via direct read (capped at 50K chars); Excel (`.xlsx`, `.xls`) via `openpyxl` conversion to CSV-like rows (capped at 2000 rows); plain text fallback for other extensions; binary file graceful handling. Returns `(file_manifest, uploaded_files)` tuple for the agent loop.
- **File Path Detection** (`routers/runs.py:_detect_file_paths_in_query`) — Regex-based detection of file paths in query text (e.g., `"file at this location: /tmp/doc.pdf"`) for backward compatibility with non-upload workflows.
- **Multimodal MCP Server** (`mcp_servers/server_multimodal.py`) — FastMCP server exposing 4 tools:
  - `analyze_image(image_path, prompt)` — Vision Q&A using Gemini 2.5 Flash via LangChain, supports JPEG/PNG/WebP
  - `analyze_pdf_document(pdf_path, prompt)` — PDF extraction via `pymupdf4llm` to markdown, LLM Q&A on extracted content (up to 100K chars), direct text return for simple extraction prompts
  - `analyze_data_file(file_path, prompt)` — CSV and Excel (`.xlsx`/`.xls`) statistical analysis: auto-detects numeric vs categorical columns, computes mean/min/max/count for numerics, unique value counts for categoricals, sends summary + 5-row sample to LLM (not full data, preventing PII leakage)
  - `analyze_video(video_path, prompt)` — Native video analysis via Gemini File API with async upload, processing poll loop, and automatic cloud file cleanup
- **Post-Plan Multimodal Compliance Enforcement** (`core/loop.py`) — Structural guardrail that runs after the planner generates a plan: scans all plan nodes and rewrites any `RetrieverAgent` tasks that reference uploaded files to `ThinkerAgent` (for images/PDFs/documents) or `CoderAgent` (for CSV/spreadsheet/Excel). Detection uses both filename matching and 15 upload-marker phrases (e.g., "uploaded file", "the chart", "the pdf", "analyze the file"). Prevents the planner LLM from incorrectly routing uploaded file analysis to web search.
- **globals_schema File Injection** (`core/loop.py`) — Uploaded file content injected into the DAG `globals_schema` under both the original filename and `{session_id}_{filename}` keys, allowing plan nodes to resolve file dependencies via their `reads` fields without "Missing dependency" errors.
- **Planner Multimodal Awareness** (`core/skills/library/planner/skill.py`) — Highest-priority constraint block in planner prompt: images → ThinkerAgent, PDFs → ThinkerAgent, CSV/data → CoderAgent. Never use RetrieverAgent for uploaded file analysis. Multimodal tools listed in agent capability table.
- **Configurable Extraction Model** (`config/settings.json`) — `models.file_extraction` key controls which model is used for extraction (default: `google/gemini-2.5-flash`). Separate `file_extraction_provider` key selects the API provider (`openrouter` or `gemini`).

### Internal Knowledge Search (2.6)

- **Internal Knowledge MCP Server** (`mcp_servers/server_internal.py`) — FastMCP server exposing 5 tools:
  - `search_workspace_files(query, directory)` — Recursive text search across workspace files (`.py`, `.md`, `.txt`, `.json`, `.csv`, `.yaml`, `.html`, `.css`, `.js`, `.ts`, `.tsx`), skips `.git`/`node_modules`/`venv`/`__pycache__`, returns matching lines with ±1 context line, capped at 20 results and 3 matches per file
  - `search_past_conversations(query)` — Scans `data/user_memory.json` for matching memories by content and tags (case-insensitive)
  - `create_space(space_name)` — Creates a persistent workspace/collection in `data/spaces.json` for ongoing research projects
  - `add_to_space(space_name, item)` — Appends research notes, URLs, or knowledge items to a named space
  - `search_space(space_name)` — Retrieves all items stored in a specific project space
- **Memory Retriever with Provenance Tags** (`memory/memory_retriever.py`) — Orchestrates semantic recall (Qdrant/FAISS vector search), entity recall (NER → Neo4j graph resolution → expansion), and graph expansion. Output sections tagged with `[SOURCE: MEMORY]` and `[SOURCE: KNOWLEDGE_GRAPH]` for downstream provenance attribution. Logging instrumentation for debugging: query details, store type, filter metadata, result counts.
- **Cross-Session Memory Retrieval Fix** (`routers/runs.py`) — Removed `session_id=run_id` from `retrieve()` calls. Each new run gets a unique `run_id`; filtering by it excluded ALL memories from prior sessions (FAISS post-search filter at `faiss_store.py:74-75`). Now only uses `space_id` scoping for memory retrieval.
- **Query Intent Classifier** (`core/loop.py`) — Pattern-matching classifier that detects internal-knowledge queries (e.g., "what did we discuss", "do you remember", "our previous", "last session") and classifies intent as `internal` (signal + memory found), `internal_empty` (signal but no memory), or `external`. Passed to planner as `query_intent` field to guide memory-first vs web-search routing.
- **Planner Internal Query Routing** (`core/skills/library/planner/skill.py`) — When `query_intent` is `internal`, planner prioritizes memory context over web search. When `internal_empty`, planner acknowledges no memories found. Replaced the old "May be old. Request retriever agent to search online" instruction.
- **Source Provenance in Citations** (`search/synthesizer.py`) — `Citation` dataclass extended with `source_type` field (`"web"` | `"memory"` | `"workspace"` | `"document"`) for provenance tracking across blended search results.
- **Formatter Provenance Instructions** (`core/skills/library/formatter/skill.py`) — Formatter prompt includes `SOURCE PROVENANCE` section: labels each section's origin, groups sources as "From your workspace", "From previous research", "From web" in citations footer.
- **Space-Scoped Retrieval** (`memory/memory_retriever.py`, `routers/runs.py`) — `RunRequest` accepts `space_id`; memory retrieval scoped to specified space via Qdrant payload filter (`space_id IN [__global__, requested_space]`) and Neo4j `IN_SPACE` relationship filter.
- **MCP Config Registration** (`mcp_servers/mcp_config.json`) — Both `server_multimodal` and `server_internal` registered globally so all agents can invoke multimodal and internal knowledge tools.

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

### Multimodal Architecture (2.5)

- **Dual-Provider Architecture** — File extraction routed through `_extract_multimodal_file()` which dispatches to either OpenRouter (base64 vision API, default) or Gemini File API (native upload). Provider selection via single settings key `file_extraction_provider`, enabling runtime switching without code changes.
- **Post-Plan Structural Enforcement** — Instead of relying solely on LLM prompt compliance, `loop.py` applies a deterministic guardrail after plan generation. Scans plan DAG nodes and rewrites incorrect `RetrieverAgent` assignments for uploaded files to `ThinkerAgent`/`CoderAgent` based on content type. Ensures uploaded file analysis never routes to web search regardless of LLM behavior.
- **globals_schema DAG Integration** — Uploaded file content injected into the execution graph's globals_schema under both original and session-prefixed keys, bridging the gap between file upload and plan node dependency resolution (fixes "Missing dependency" errors).
- **Unified Extraction Pipeline** — Single `_extract_file_content()` function handles all file types through a priority chain: multimodal provider (images + PDFs) → direct read (CSV) → openpyxl conversion (Excel) → text fallback → binary graceful handling. Each path returns typed content (`image`, `pdf`, `csv`, `spreadsheet`, `text`, `binary`).

### Internal Knowledge Architecture (2.6)

- **Memory Retriever Provenance Tagging** — `memory_retriever.py` output sections tagged with `[SOURCE: MEMORY]` and `[SOURCE: KNOWLEDGE_GRAPH]` enabling downstream attribution in reports.
- **Cross-Session Memory Fix** — Removed session_id-based filtering that was silently blocking all cross-session memory retrieval (FAISS post-search filter eliminated memories stored under different session IDs).
- **Query Intent Classification** — Pattern-matching classifier in `loop.py` detects internal-knowledge queries and routes to memory-first retrieval. Planner receives `query_intent` field (`internal`/`internal_empty`/`external`) to guide routing decisions.
- **Space-Scoped Retrieval** — `RunRequest` accepts `space_id`; memory retrieval auto-scopes to global + specified space via Qdrant/Neo4j filters.
- **Citation Source Types** — `Citation` dataclass in `synthesizer.py` extended with `source_type` field (`web`/`memory`/`workspace`/`document`) for provenance tracking across blended results.
- **Formatter Provenance** — Formatter prompt enforces source attribution: groups citations as "From your workspace", "From previous research", "From web".
- **MCP Server Registration** — `server_multimodal` (4 tools) and `server_internal` (5 tools) registered globally in `mcp_config.json` so all agents can invoke them.
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

### Multimodal & Internal Search (2.5 / 2.6)

**Modified Backend Endpoints:**

- `POST /api/runs` — Extended `RunRequest` with `file_paths` (list of server-side file paths for multimodal extraction) and `space_id` (for space-scoped memory retrieval)
- `POST /runs/upload` — File upload endpoint saves files to `data/uploads/` and returns server paths for subsequent run requests

**Backend Processing Pipeline:**

- File upload → `_extract_file_content()` dispatches by type → content injected into planner query as `UPLOADED FILE CONTENTS` block → post-plan enforcement ensures correct agent assignment → globals_schema injection for DAG node resolution
- Memory retrieval → `memory_retriever.retrieve()` with provenance tags → query intent classifier → planner receives `query_intent` + `memory_context` → formatter applies source attribution

**New MCP Tools (available to all agents):**

- Multimodal: `analyze_image`, `analyze_pdf_document`, `analyze_data_file`, `analyze_video`
- Internal: `search_workspace_files`, `search_past_conversations`, `create_space`, `add_to_space`, `search_space`

**Configuration:**

- `config/settings.json` — `file_extraction_provider`: `"openrouter"` (default) or `"gemini"`; `models.file_extraction`: model ID for extraction (default: `google/gemini-2.5-flash`)
- Environment: `OPENROUTER_API_KEY` (default provider), `GEMINI_API_KEY` (optional Gemini provider)

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

**Unit Tests** (`tests/unit/oracle/test_multimodal_extraction.py`) — 10 tests:

- `test_pdf_extraction_returns_markdown` — PDF extraction via mocked multimodal provider
- `test_image_extraction_calls_provider` — Image extraction routes to configured provider
- `test_csv_extraction_reads_content` — CSV direct read without LLM processing
- `test_xlsx_extraction` — Excel-to-CSV conversion via openpyxl
- `test_binary_file_fallback` — Binary files handled gracefully (no crash)
- `test_nonexistent_file_skipped` — Missing paths return empty manifest
- `test_detect_file_paths_in_query` — File path regex detection in query text
- `test_file_extraction_model_configurable` — Settings `models.file_extraction` key exists
- `test_post_plan_enforcement_rewrites_retriever` — RetrieverAgent rewritten to ThinkerAgent for image uploads
- `test_post_plan_enforcement_csv_uses_coder` — RetrieverAgent rewritten to CoderAgent for CSV/spreadsheet

**Unit Tests** (`tests/unit/oracle/test_provenance_labels.py`) — 3 tests:

- `test_memory_context_has_provenance_tags` — `[SOURCE: MEMORY]` tags in retriever output
- `test_citation_source_type_field` — Citation dataclass accepts `source_type`
- `test_formatter_skill_has_provenance_section` — Formatter prompt contains provenance instructions

**Integration Tests** (`tests/integration/test_oracle_multimodal_internal.py`) — Module loading validation

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

### Multimodal & Internal Search (2.5 / 2.6)

- `search_workspace_files` strictly filters by a safe whitelist of file extensions (`.py`, `.md`, `.txt`, `.json`, etc.) implicitly preventing the reading of `.env` files or binary secrets.
- `search_workspace_files` automatically drops system directories like `.git`, `node_modules`, `venv`, `__pycache__` preventing path-traversal and denial of service from recursive loops.
- `analyze_data_file` sends only statistical summaries and 5-row samples (not full row data) to the LLM to prevent PII leakage on large datasets. Supports CSV and Excel via openpyxl.
- File extraction providers raise `RuntimeError` on failure instead of silently injecting error strings into the planner query — prevents error text from being treated as actual file content.
- Gemini File API provider auto-deletes uploaded files after extraction (cleanup in `finally` block) to avoid cloud storage accumulation.
- OpenRouter provider uses 120s timeout to prevent hanging connections on large file uploads.
- CSV reads capped at 50K chars; Excel conversion capped at 2000 rows — prevents memory exhaustion on large files.
- Binary files handled gracefully with `[Binary file]` placeholder — no raw binary content sent to LLM.
- Post-plan enforcement is a deterministic structural check (not LLM-dependent) — cannot be bypassed by prompt injection in uploaded file content.

## 8. Known Gaps

### Deep Research

- Query approval gate (interactive gap iteration approval) is foundational but not wired to a UI modal yet
- Search cache layer (`search/cache.py`) is scaffolded but not fully integrated
- Deep research iteration count is hardcoded (max 5) — not user-configurable via UI
- No rate limiting on search endpoints
- Browser-use model hardcoded to Ollama/gemma3:12b — requires local Ollama instance

### Multimodal & Internal Search (2.5 / 2.6) — Known Gaps

- No frontend drag-drop upload UI in the main search input — file upload requires the existing upload endpoint workflow
- No reverse image search (image-to-web-search flow) — image VQA works but finding similar images online is not implemented
- No chart/visualization generation from CSV data — CoderAgent is assigned but matplotlib chart generation instructions are guidance-only (no enforced pipeline)
- No frontend space selector UI — backend space-scoped retrieval works but users cannot select spaces from the UI
- High-resolution images sent via OpenRouter use base64 encoding which may hit payload size limits for very large files
- Video analysis in MCP server uses `gemini-1.5-flash` (hardcoded) — not configurable via settings
- `server_multimodal.py` contains duplicated code blocks (copy-paste artifact) that should be cleaned up

## 9. Rollback Plan

### Deep Research

- Feature is fully opt-in: `mode: "standard"` (default) bypasses all deep research code paths
- Search endpoints are additive — removing `routers/search.py` and its include in `api.py` disables the feature
- Skill exclusion ensures standard agent runs are unaffected
- Frontend search UI components are isolated — removing `features/search/` and `ResearchProgress.tsx` reverts UI
- No database migrations or schema changes to roll back

### Multimodal & Internal Search (2.5 / 2.6) — Rollback

- Revert `server_multimodal.py` and `server_internal.py` from `mcp_servers/` and their entries in `mcp_config.json`
- Revert dual-provider extraction functions in `routers/runs.py` (`_extract_via_openrouter`, `_extract_via_gemini`, `_extract_multimodal_file`, `_extract_file_content`)
- Revert post-plan enforcement block and globals_schema injection in `core/loop.py`
- Revert query intent classifier in `core/loop.py`
- Revert planner multimodal awareness block in `core/skills/library/planner/skill.py`
- Revert provenance tags in `memory/memory_retriever.py`
- Revert `source_type` field from `Citation` in `search/synthesizer.py`
- Revert provenance instructions from `core/skills/library/formatter/skill.py`
- Remove `file_extraction_provider` and `models.file_extraction` from `config/settings.json`
- Remove test files: `tests/unit/oracle/test_multimodal_extraction.py`, `tests/unit/oracle/test_provenance_labels.py`
- No database migrations or schema changes to roll back

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

**Image Upload & Analysis:**

1. Start the backend: `python api.py`
2. Start the frontend: `cd platform-frontend && npm run dev`
3. Click "New Run", upload an image file (PNG/JPG/WebP)
4. Enter a query: "What data is shown in this image?"
5. Observe: file extracted via OpenRouter/Gemini → planner assigns ThinkerAgent (not RetrieverAgent) → formatted analysis returned

**PDF Upload & Q&A:**

1. Click "New Run", upload a PDF document
2. Enter a query: "Summarize the key findings in this document"
3. Observe: PDF extracted to markdown via multimodal provider → ThinkerAgent analyzes content → FormatterAgent produces report

**CSV/Excel Data Analysis:**

1. Click "New Run", upload a CSV or XLSX file
2. Enter a query: "What are the top trends in this data?"
3. Observe: CSV read directly / Excel converted via openpyxl → CoderAgent assigned for statistical analysis → formatted output

**Internal Knowledge Query:**

1. Run several research queries first to build up memory
2. Click "New Run", enter: "What did we discuss about API design?"
3. Observe backend logs: `🔍 MemoryRetriever: searching...` with `session_id=None`, `Semantic recall: X results` (X > 0)
4. Result should reference previous memories (tagged `[SOURCE: MEMORY]`) rather than defaulting to web search

**Provider Switching (OpenRouter → Gemini):**

1. Edit `config/settings.json`: change `"file_extraction_provider": "openrouter"` to `"gemini"`
2. Ensure `GEMINI_API_KEY` is set in environment
3. Upload an image — extraction now uses Gemini File API (native upload) instead of OpenRouter base64
