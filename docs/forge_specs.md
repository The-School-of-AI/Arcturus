## Software Product Specification (SPS) — Project 4 “Forge”
**Product:** Forge — AI Document, Slides & Sheets Studio  
**Inspired by:** GenSpark (AI Slides/Sheets), Skywork AI (slides agent)  
**Team:** AI Content Creation | **Priority:** P0 | **Duration:** 4 weeks (20 workdays)  
**Primary target environment:** **Desktop Electron application** (single-user, local-first with optional cloud integrations for Google export)

---

## 1) Purpose
Forge is an AI-powered creation suite that generates **professional presentations, documents, and spreadsheets** from natural-language prompts—positioned as an AI-first alternative to Google Workspace + AI.

Forge supports **generation, iterative editing via chat, version history**, and **multi-format export**.

---

## 2) Goals and Success Criteria

### Product goals
1. **Prompt-to-artifact** generation for Slides / Docs / Sheets with strong baseline quality.
2. **Edit loop**: users can refine output conversationally without manual rebuilding.
3. **Export reliability**: generated PPTX/DOCX/XLSX open cleanly and render as intended.
4. **Research-backed outputs**: integrate web research via **Project 2 (Oracle)** with citations where relevant.

### Quantitative success criteria
- **Performance:** P95 **< 10s** draft artifact generation for a benchmark prompt.
- **Reliability:** Exports open without corruption; overflow/unreadable layout is automatically rejected (at least one validator).
- **Quality gate:** Acceptance + integration test hard conditions satisfied (see Section 12).

---

## 3) Target Users and Key Use Cases

### Primary personas
- **Founder / Operator:** needs pitch decks, business plans, financial models quickly.
- **Product / Engineering Lead:** needs technical specs, migration docs, status reports.
- **Analyst / Finance:** needs models, pivots, anomaly checks, charts from uploads.
- **Consultant / Student:** needs polished deliverables with citations and formatting.

### Top use cases
- “Create a **15-slide Series A pitch deck** for an AI startup.”
- “Write a **technical specification** for a microservices migration.”
- “Create a **SaaS financial model** spreadsheet with formulas and charts.”
- “Make slide 3 more visual.” / “Add competitor comparison on slide 7.”
- “Upload CSV and generate **summary stats + pivots + anomaly detection**.”

---

## 4) Scope

### In scope (P0)

**A) Slides (highest priority)**
- Prompt-to-deck, slide-type selection, themes, speaker notes
- Auto-research (Oracle), auto-charts, auto-images (image API)
- Chat-driven editing loop
- Export: **PPTX**, **PDF**, **HTML (interactive)**, Google Slides link (via API)
- Template marketplace: **de-scoped** for the 4-week build (see Out of scope)

**B) Documents**
- Prompt-to-document across defined types
- Outline-first workflow (outline → approve → fill sections → iterate)
- Citations (APA/MLA/Chicago/IEEE) when research is used
- Collaborative editing: **least-effort** approach (see Section 7)
- Version history + diff visualization
- Export: **DOCX (python-docx)**, **PDF (WeasyPrint)**, **Markdown**, **LaTeX**, Google Docs

**C) Sheets / Data Analysis**
- Prompt-to-spreadsheet with formulas
- Natural language → Excel/Sheets formula translation
- Upload CSV/Excel/JSON → summaries, correlations, trends, anomaly detection, pivots
- Visualization agent chooses best-fit chart types
- Export: **XLSX (openpyxl)**, **CSV**, Google Sheets

### Explicitly out of scope (this 4-week capstone)
- **Authentication + sharing** (no accounts, no multi-user sharing)
- Marketplace publishing/discovery, monetization, moderation
- Enterprise governance (DLP, retention policies, org-level admin)
- Full OT/CRDT real-time collaboration

---

## 5) Product Experience Overview (Electron)

### Desktop-first UX
- Single-user app with local project library
- Local caching of drafts/exports; optional cloud export for Google links
- WYSIWYG editor panes for slides/docs/sheets
- Chat panel for edit loop + generation

### Core workflow pattern (all artifact types)
1. **User prompt** → Forge generates a **structured plan/schema**
2. **Draft artifact** rendered in a **WYSIWYG editor**
3. **Edit loop**: chat instructions apply targeted changes
4. **Export**: format conversion + validations

### Outline-first (Docs)
- Step 1: Generate outline (sections, headings, expected content)
- Step 2: User approval (or edit outline)
- Step 3: Fill sections with citations (if research used)
- Step 4: Iterate + version history

---

## 6) Functional Requirements

### 6.1 Shared Platform Requirements

**FR-S1 Artifact model**
- Every artifact has:
  - `type`: slides | document | sheet
  - `schema_version`
  - `content_tree` (structured representation)
  - `assets` (images, charts, themes)
  - `revisions` (version history)
  - `exports` (format, location, status, timestamps)

**FR-S2 Chat-driven editing**
- Accept instructions like:
  - “Make slide 3 more visual”
  - “Add competitor comparison on slide 7”
  - “Rewrite section 2 in a more formal tone”
  - “Add a pivot by region”
- System must:
  - Identify target scope (artifact-level / section / slide / table)
  - Apply changes deterministically to the schema
  - Produce a new revision and render diff

**FR-S3 Research integration**
- Via **Project 2 (Oracle)**:
  - Pull relevant facts/data
  - Return structured research artifacts (snippets, sources, datasets)
  - When research used, store provenance for citation generation

**FR-S4 Export pipeline**
- Export supported for each artifact type and validated.
- Controlled error handling for malformed payloads/invalid inputs.
- Idempotency/retry where external APIs or queued jobs exist.

---

## 6.2 AI Slides Engine Requirements (P0-first)

**FR-SL1 Prompt-to-deck**
- Input: prompt + optional parameters (slide count, tone, audience, theme)
- Output: complete deck with appropriate slide types and narrative flow

**FR-SL2 Theme system**
- Support **100+ professional themes**.
- **Minimum acceptable theme assets:** *any visually appealing assets* that produce polished results.
  - Practical minimum for this build:
    - 12–20 high-quality base themes shipped in-app
    - Procedural variations (palette + font pairing + background patterns) to reach “100+”

**FR-SL3 Slide types**
- Must support: Title, Content, Two-Column, Comparison, Timeline, Chart, Image+Text, Quote, Code, Team

**FR-SL4 Content intelligence**
- Auto-research (Oracle)
- Auto-chart: bar, line, pie, funnel, scatter
- Auto-image: generate or source via image generation API
- Speaker notes auto-generated for each slide

**FR-SL5 Edit loop**
- Chat edits must support:
  - Layout changes (more visual, two-column, swap chart type)
  - Content additions (competitor slides, team slide)
  - Narrative changes (shorter, more persuasive, more technical)

**FR-SL6 Export**
- PPTX via **python-pptx**
- PDF
- HTML (interactive)
- Google Slides link (via API)

---

## 6.3 AI Document Writer Requirements

**FR-D1 Prompt-to-document**
- Supported types:
  - Technical Spec, Business Plan, Research Paper, Blog Post, Legal Brief, Report, Proposal, White Paper

**FR-D2 Outline-first workflow**
- Generate outline first → user approves → fill sections → iterate

**FR-D3 Citations**
- Auto-cite sources when research is involved
- Styles: APA, MLA, Chicago, IEEE
- Citations must link to stored provenance (Oracle results)

**FR-D4 Collaborative editing (least effort)**
- Implement **near-real-time** collaboration as a low-effort option:
  - Single-writer with periodic refresh/polling
  - “Lock while editing” or optimistic save with last-write-wins + conflict warning
  - Comments/suggestions stored as annotations (no OT/CRDT)

**FR-D5 Version control**
- Full version history with diff visualization (section-level diff acceptable for MVP)

**FR-D6 Export**
- DOCX via **python-docx**
- PDF via **WeasyPrint**
- Markdown, LaTeX
- Google Docs via API

---

## 6.4 AI Sheets / Data Analysis Requirements

**FR-SH1 Prompt-to-spreadsheet**
- Generate full spreadsheet with formulas, formatting, and assumptions section where relevant

**FR-SH2 Formula generation**
- Translate natural language → Excel/Sheets formulas
- Ensure formulas are syntactically valid and reference correct ranges

**FR-SH3 Data analysis agent (uploads)**
- Input: CSV/Excel/JSON
- Output:
  - Summary stats (mean/median/std/distributions)
  - Correlations + trends
  - Anomaly detection
  - Pivot tables + cross-tabs

**FR-SH4 Visualization agent**
- Auto-select best-fit chart type and generate chart configuration

**FR-SH5 Export**
- XLSX via **openpyxl**
- CSV
- Google Sheets via API

---

## 7) Non-Functional Requirements

### Performance
- P95 **< 10s** for draft artifact generation (benchmark prompt)
- Export generation may be asynchronous; must have predictable status + retry

### Reliability
- No corrupted exports; must open in standard viewers
- Graceful failures with clear error messages; no crashes on malformed payloads

### Quality
- At least one **layout-quality validator** rejects overflow/unreadable slide output
- Regression suite required (baseline quick tests + project tests)

### Security & Privacy (desktop baseline)
- No authentication required.
- Store artifacts locally (encrypted-at-rest if feasible) and protect any API keys used for integrations.

---

## 8) System Architecture (Proposed)

### Key modules / directories (as deliverables)
- `studio/slides/` — slide generation engine, themes, PPTX export
- `studio/documents/` — document engine, templates, multi-format export
- `studio/sheets/` — spreadsheet generation, formula engine, analysis
- `studio/assets/` — theme CSS, font bundles, chart templates
- Frontend: `features/studio/` — WYSIWYG editor components (slides/docs/sheets)
- `routers/studio.py` — API endpoints for creation, editing, export

### Electron packaging notes
- Local filesystem project store
- Local render preview inside Electron UI
- Optional cloud calls for Oracle research and Google export

---

## 9) Data Model (Minimum Viable)

**Artifact**
- `id`, `type`, `title`, `created_at`, `updated_at`
- `schema_version`
- `content_tree` (JSON)
- `theme_id` (optional)
- `revision_head_id`

**Revision**
- `id`, `artifact_id`, `parent_revision_id`
- `change_summary`
- `content_tree_snapshot` (or patch/delta)
- `created_at`

**Asset**
- `id`, `artifact_id`, `kind` (image/chart/font/theme)
- `uri`, `metadata`

**ExportJob**
- `id`, `artifact_id`, `format`, `status`
- `output_uri`, `validator_results`, `created_at`, `completed_at`

**ResearchProvenance**
- `id`, `artifact_id`
- `source_entries` (url/title/author/date/snippet)
- `retrieved_at`

---

## 10) API Surface (via `routers/studio.py`)

### Creation
- `POST /studio/slides`
- `POST /studio/documents`
- `POST /studio/sheets`

### Edit loop
- `POST /studio/{artifact_id}/edit`

### Export
- `POST /studio/{artifact_id}/export`
- `GET /studio/exports/{export_job_id}`

> Note: Auth and sharing endpoints are intentionally omitted.

---

## 11) Strategy and Build Plan

### Strategy
1. **Slides first** (highest visual impact)
2. Documents next
3. Sheets last
4. Separate specialized prompts per content type
5. Frontend partnership for slide theme fidelity

### 20-day execution addendum (plan)
- **Team split**
  - Student A: Slides and template/layout engine
  - Student B: Docs/sheets generation and export pipeline
- **Day plan**
  - Days 1–5: Outline-first generation + artifact schemas
  - Days 6–10: Slides quality pass (themes, chart placement, notes)
  - Days 11–15: Docs + sheets generation with export validators
  - Days 16–20: Edit loop, regression suite, demo artifacts

---

## 12) Testing, CI, and Hard Conditions (Mandatory Gate)

### Acceptance
- File: `tests/acceptance/p04_forge/test_exports_open_and_render.py`
- Must exist and contain **≥ 8 executable test cases**
- Must validate:
  1) Happy-path end-to-end for core flow
  2) Controlled errors for invalid/malformed inputs
  3) Retry/idempotency where external calls/queued jobs used
  4) Exports open without corruption
  5) At least one layout-quality validator rejects overflow/unreadable slides

### Integration
- File: `tests/integration/test_forge_research_to_slides.py`
- Must exist and contain **≥ 5 executable integration scenarios**
- Must validate:
  - Oracle research artifacts ingestion
  - Rendering through Canvas/preview flows without schema breakage
  - Upstream failure → graceful downstream behavior + logs/metrics

### CI required check
- Required check: `p04-forge-studio`
- Must run:
  - Project acceptance tests
  - Project integration tests
  - Baseline regression suite: `scripts/test_all.sh quick`
  - lint/typecheck for touched paths

### Delivery evidence (branch gate)
- Must add: `CAPSTONE/project_charters/P04_DELIVERY_README.md`
- Must include sections:
  - Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence,
  - Known Gaps, Rollback Plan, Demo Steps
- CI fails if missing

---

## 13) Telemetry and Monitoring (Minimum)
- Generation latency (p50/p95) by artifact type
- Export success rate by format + failure reasons
- Validator rejection rate (overflow/unreadable)
- Edit-loop success rate (instruction→applied change)
- Research usage rate + citation completeness (docs)

---

## 14) Risks and Mitigations
- **Layout quality variance (slides):** enforce validators + conservative defaults; template-driven layouts.
- **Export corruption edge cases:** “open-and-render” tests; strict validators.
- **Research hallucination risk:** cite only stored provenance; separate generated vs sourced.
- **Electron packaging complexity:** keep services modular; stub cloud-only features gracefully.
- **Collab scope creep:** near-real-time with locks/refresh + versioning only.

---

## 15) Decisions (Finalized)
- **Target environment:** Desktop **Electron** application.
- **Authentication + sharing:** **Not required** for P0.
- **Theme assets minimum:** **Any visually appealing assets**; ship a small curated set + procedural variants.
- **Collaboration:** **Least-effort** approach (near-real-time, no OT/CRDT).

