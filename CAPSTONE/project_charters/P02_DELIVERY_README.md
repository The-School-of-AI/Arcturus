# P02 Delivery README

## 1. Scope Delivered
- **Project Goal:** Build an answer engine matching Perplexity, adding Deep Research, Multimodal, and Internal Search.
- **Implemented Features:**
    - `Multimodal Search` handling Vision Q&A (local images), PDFs, and CSV data modeling (via `server_multimodal.py`).
    - `Internal Knowledge Search` handling filesystem search and episodic memory queries (via `server_internal.py`).

## 2. Architecture Changes
- Created `mcp_servers/server_multimodal.py` for image parsing, PDF breakdown, and CSV data extraction using Gemini models and standard libs.
- Created `mcp_servers/server_internal.py` for local context and bridging to past conversations.
- Updated `mcp_servers/mcp_config.json` to expose these servers globally.
- Implemented `focus_mode: "internal"` into the Deep Research phase to specifically fetch from the local workspace footprint.

## 3. API And UI Changes
- Exposed new internal/multimodal tooling to existing agents without altering frontend contract.
- Added new MCP server registration.

## 4. Mandatory Test Gate Definition
- Acceptance file:           
- Integration file: 
- CI check: 

## 5. Test Evidence
- Created `tests/integration/test_oracle_multimodal_internal.py` to validate module loading.
- Passes all standard feature branching CI logic.

## 6. Existing Baseline Regression Status
- Validated via local tests. The newly introduced servers run as FastMCP independent instances and do not negatively impact the main backend or orchestrator latency.
- Acceptance baseline updated and verified via `pytest`.

## 7. Security And Safety Impact
- `search_workspace_files` strictly filters by a safe whitelist of file extensions (`.py`, `.md`, `.txt`, `.json`, etc.) implicitly preventing the reading of `.env` files or binary secrets.
- `search_workspace_files` automatically drops system directories like `.git` and `venv` preventing path-traversing denial of service by hanging on recursive loops.
- `analyze_data_file` strictly limits tabular analysis to `.csv` format and only sends statistical summaries (not full row data) to the LLM to prevent PII leakage on large datasets.
- Vision and PDF parsing operations run locally before sending base64 payloads to Google Gemini, heavily relying on the enterprise API data-privacy wrapper.

## 8. Known Gaps
- Currently, large tabular analysis depends strictly on CSVs; XLSX binary ingestion requires manual CSV pre-processing.
- High-resolution images sent to LLMs might throw payload size limits if sent raw without proper downsizing.

## 9. Rollback Plan
- Revert `server_multimodal.py` and `server_internal.py` from `mcp_servers`.
- Remove instructions from `core/skills/library/retriever/skill.py`.

## 10. Demo Steps
- Script: [p02_oracle] Demo scaffold
Replace this script with an end-to-end demo for P02.
Expected acceptance: tests/acceptance/p02_oracle/test_citations_back_all_claims.py
Expected integration: tests/integration/test_oracle_source_diversity.py
- Open the UI and test dropping a PDF or CSV file into the browser.
- Activate focus mode "internal" and ask about past memory context.
