## Forge — 20-Day Plan Converted into Testable Phases

This rewrites the 20-day plan into **distinct phases** where each phase can be **developed independently** and has **clear test/acceptance gates** before moving on.

---

## Phase 1 — Foundations: Artifact Schema + Outline-First Core (Days 1–5)

### Scope
- Define **canonical artifact schemas** for Slides / Docs / Sheets (`schema_version`, `content_tree`, `assets`, `revisions`, `exports`).
- Implement **Outline-first generation pipeline**:
  - Prompt → outline/plan JSON → approve/accept → generate draft content_tree.
- Establish **revision model** and basic diff metadata.

### Deliverables
- Schema definitions + validators (JSON-schema or typed models)
- Outline-first orchestrator (shared)
- Minimal preview renderer stubs (can render structured content_tree)

### Phase test gates
- Unit tests:
  - Schema validation: valid examples pass; malformed payloads return controlled errors.
  - Outline-first flow: outline created → accepted → draft created with correct schema.
- Contract tests:
  - `content_tree` round-trip serialization/deserialization.

### Exit criteria
- Can create an artifact of each type that passes schema validation and has a revision.

---

## Phase 2 — Slides MVP: Prompt-to-Deck + Base Export (Days 6–8)

### Scope
- Slides generator MVP:
  - Prompt-to-deck producing 8–15 slides using supported slide types.
  - Speaker notes generation (baseline).
- Minimal theming (start with a small curated set, e.g., 5–8 base themes).
- Export MVP: **PPTX** (python-pptx) must open.

### Deliverables
- Slides generation engine producing a usable deck
- PPTX exporter + basic “open” validation

### Phase test gates
- Unit tests:
  - Slide type mapping correctness
  - Deterministic generation given fixed inputs (seeded)
- Acceptance tests:
  - “Happy-path pitch deck” exports to PPTX and opens without corruption

### Exit criteria
- A generated PPTX opens and contains expected slide count + speaker notes.

---

## Phase 3 — Slides Quality Pass: Themes + Charts + Notes (Days 9–10)

### Scope
- Expand themes to target “100+” via:
  - 12–20 curated bases + procedural variants (palette/font/background).
- Auto-chart placement from structured data (bar/line/pie/funnel/scatter).
- Improve speaker notes quality.
- Add **layout-quality validator** (overflow/unreadable detection).

### Deliverables
- Theme bundle system (base themes + variants)
- Chart rendering + layout rules
- Slide layout-quality validator

### Phase test gates
- Visual/layout validation tests:
  - Validator rejects overflow/unreadable slides for known bad cases
  - Validator passes known-good deck baselines
- Export tests:
  - Decks with charts/themes export and open

### Exit criteria
- Slides meet baseline quality rules and validator is active in pipeline.

---

## Phase 4 — Docs MVP: Outline → Draft + Export (Days 11–13)

### Scope
- Document generator MVP for core types:
  - Technical Spec, Report, Proposal (expand later).
- Outline-first workflow fully functional.
- Export: **DOCX** (python-docx) + **PDF** (WeasyPrint) must open.
- Citation plumbing (store provenance slots even if minimal).

### Deliverables
- Document generation engine + outline-first UI hooks
- DOCX/PDF export pipeline

### Phase test gates
- Unit tests:
  - Outline structure correctness for each doc type
  - Section rendering + revision creation
- Acceptance tests:
  - DOCX and PDF export open without corruption

### Exit criteria
- Prompt-to-document works end-to-end with DOCX/PDF export.

---

## Phase 5 — Sheets MVP: Prompt-to-Spreadsheet + Data Upload Analysis (Days 14–15)

### Scope
- Prompt-to-spreadsheet with formulas and basic formatting.
- Upload CSV/Excel/JSON → generate:
  - summary stats, correlations/trends, anomaly flags, pivot/crosstab.
- Export: **XLSX** (openpyxl) + CSV must open.

### Deliverables
- Spreadsheet generation engine
- Data analysis agent for uploads
- XLSX/CSV export pipeline

### Phase test gates
- Unit tests:
  - Formula translation validity (syntactic + range refs)
  - Analysis outputs for known fixture datasets
- Acceptance tests:
  - XLSX opens, key sheets/tables exist, formulas evaluated by Excel/compatible viewer

### Exit criteria
- Can generate or analyze a spreadsheet and export valid XLSX.

---

## Phase 6 — Edit Loop + Versioning (Days 16–18)

### Scope
- Chat-driven edit loop for Slides/Docs/Sheets:
  - Targeting (slide index/section/table)
  - Patch application to `content_tree`
  - Revision creation + diff summary
- Least-effort collaboration behavior for docs:
  - single-writer locking OR optimistic saves + conflict warning

### Deliverables
- Unified edit router + patch engine
- Revision browsing + diff visualization (basic)

### Phase test gates
- Unit tests:
  - Patch application idempotency for repeated edits
  - Invalid edit instructions return controlled errors
- Integration tests:
  - Create → edit → export still valid (no schema breakage)

### Exit criteria
- Users can apply 3–5 representative edits per artifact type and exports remain valid.

---

## Phase 7 — Hardening: Regression Suite + Demo Artifacts (Days 19–20)

### Scope
- Lock in mandatory gates:
  - Acceptance test file has ≥ 8 tests
  - Integration test file has ≥ 5 scenarios
  - Oracle→Slides integration coverage
  - Failure propagation + logs/metrics
- Produce demo-ready artifacts:
  - Pitch deck, tech spec, SaaS model
- Fill delivery evidence doc:
  - `CAPSTONE/project_charters/P04_DELIVERY_README.md`

### Deliverables
- Full CI check `p04-forge-studio`
- Demo set + scripts
- Delivery README

### Phase test gates
- CI gates:
  - acceptance + integration + baseline regression + lint/typecheck all green
- Benchmark check:
  - P95 draft artifact generation < 10s for benchmark prompt (record evidence)

### Exit criteria
- All hard conditions satisfied and demo artifacts reproducible.

