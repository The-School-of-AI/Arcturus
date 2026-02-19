# P04 Forge — First 5 Days Execution Guide

**Focus:** Outline-first generation and artifact schemas.  
**Charter:** [P04_forge_ai_document_slides_sheets_studio.md](./P04_forge_ai_document_slides_sheets_studio.md)  
**CI gate:** `p04-forge-studio` (acceptance + integration + `scripts/test_all.sh quick`)

---

## Goals for Days 1–5

1. **Artifact schemas** — Define and freeze schemas for slide deck, document, and spreadsheet artifacts (and their outlines) so downstream (export, Canvas preview, edit loop) can rely on them.
2. **Outline-first flow** — Implement “prompt → outline → approve → fill” for slides (and schema-only stubs for docs/sheets).
3. **Repo layout** — Create `studio/` package and `routers/studio.py` skeleton without duplicating existing patterns.
4. **Test alignment** — Keep acceptance (8+ tests) and integration (5+ scenarios) valid and add tests that satisfy the hard conditions (happy path, invalid input, export opens, layout validator, Oracle → Forge flow).

---

## Day 1: Repo structure and shared artifact schemas

### 1.1 Create directory layout

- `studio/` (package)
  - `studio/__init__.py`
  - `studio/schemas/` — shared Pydantic (or dataclass) models for outlines and artifacts
  - `studio/slides/` — slide engine (empty or `__init__.py` only for Day 1)
  - `studio/documents/` — doc engine (stub)
  - `studio/sheets/` — sheets engine (stub)
  - `studio/assets/` — placeholder for theme CSS/fonts/chart templates (can be empty)
- `routers/studio.py` — router module (skeleton only: router instance, one health/readiness route if desired)
- Frontend: `platform-frontend/src/features/studio/` — placeholder (e.g. `README.md` or single stub component) so the path exists

Do **not** move or duplicate existing RAG/docs logic; keep studio as the “creation from prompt” layer.

### 1.2 Define outline and artifact schemas (slides first)

Add under `studio/schemas/` (or a single `studio/schemas/artifacts.py` to stay under ~200 lines):

**Outline schemas (shared idea: “outline first, then fill”):**

- `SlideOutline` — list of slide entries, each with: `slide_index`, `slide_type` (e.g. title, content, two_column, comparison, timeline, chart, image_text, quote, code, team), `title` (optional), `bullet_points` or `content_hint` (optional).
- `DocumentOutline` — list of sections: `section_index`, `title`, `content_hint` (optional).
- `SheetOutline` — list of sheets/tables: `sheet_name`, `content_hint` (e.g. “Revenue assumptions”, “Unit economics”).

**Artifact schemas (what gets exported):**

- **Slides:** e.g. `SlideDeckArtifact` — `deck_id`, `theme_id`, `slides: List[SlideBlock]`. Each `SlideBlock`: `slide_type`, `title`, `body` (rich content: text, bullets, or structured blocks), optional `speaker_notes`, optional `chart_spec`, optional `image_ref`.
- **Documents:** e.g. `DocumentArtifact` — `doc_id`, `doc_type` (technical_spec, business_plan, etc.), `sections: List[SectionBlock]` (title, content, optional citations).
- **Sheets:** e.g. `SheetArtifact` — `workbook_id`, `sheets: List[SheetTable]` (name, rows, optional formula_refs).

Use **one** place for these definitions (e.g. `studio/schemas/artifacts.py`) and import from `studio.slides`, `studio.documents`, `studio.sheets` and from `routers/studio` to avoid duplication.

### 1.3 Oracle → Forge ingestion contract (for integration tests)

Define a small “research artifact” schema that Forge will accept from Oracle (or from tests). For example:

- `OracleResearchArtifact` (or name it per repo convention): `query`, `summary`, `sources: List[{url, title, snippet}]`, `citations: List[{claim, source_index}]`.  
- Add in `studio/schemas/` (e.g. `studio/schemas/ingestion.py`) and document: “Forge ingest expects this shape so research-to-slides integration does not break schema.”

No Oracle code changes required on Day 1; this is a contract so `test_forge_research_to_slides` can validate ingestion and rendering without schema breakage.

### 1.4 Checks

- `studio/` is a valid Python package; `studio.schemas` can be imported.
- `routers/studio.py` exists and app mounts it (if your app uses a central router list, add `studio` there).
- All existing acceptance and integration tests still pass (including `scripts/test_all.sh quick`).

---

## Day 2: Outline-first flow for slides

### 2.1 Prompt → outline (slides only)

- In `studio/slides/` add an outline generator: **input** = user prompt (string) + optional `OracleResearchArtifact`; **output** = `SlideOutline` (list of slide entries with `slide_type`, `title`, `content_hint`).
- Use a single LLM call (or a small prompt chain) that returns structured JSON matching `SlideOutline`; parse into your schema and validate (e.g. with Pydantic).
- No need for “approve” UI yet; an **approve** step can be a simple flag or “outline_accepted” in the API (e.g. POST that returns an outline, then POST that accepts outline and triggers fill).

### 2.2 Outline → fill (stub or minimal)

- Add a function that takes `SlideOutline` and produces `SlideDeckArtifact` (filled slides). Day 2 can implement a **minimal fill**: e.g. turn each outline entry into one slide with title + placeholder body so that the artifact is valid and export can be hooked later.
- Prefer a single module under `studio/slides/` (e.g. `outline.py` and `fill.py`, or `generator.py`) to keep files under 200 lines.

### 2.3 Router

- In `routers/studio.py` add two endpoints (or one that does both):
  - e.g. `POST /studio/slides/outline` — body: `{ "prompt": "...", "research": {...} }` → returns `SlideOutline`.
  - e.g. `POST /studio/slides/draft` — body: `{ "outline": {...} }` → returns `SlideDeckArtifact` (minimal fill).
- Use the same schemas from `studio.schemas` for request/response so the API is consistent with the artifact schemas.

### 2.4 Tests

- One **acceptance** test: happy path “prompt → outline → draft” (e.g. call API, assert outline and draft conform to schemas and draft has expected slide count).
- Keep total acceptance tests ≥ 8 (you already have 8 scaffold tests; you can replace one with this flow or add a 9th).

---

## Day 3: Slide artifact quality and first export

### 3.1 Theme and slide-type alignment

- In `studio/assets/` (or `studio/slides/themes.py`) define a **theme registry**: theme_id → display name (e.g. Corporate, Minimal, Dark). No need for 100+ themes; implement 3–5 so the pipeline accepts `theme_id` and passes it through to export.
- Ensure `SlideDeckArtifact` and each `SlideBlock` support the slide types from the charter (title, content, two_column, comparison, timeline, chart, image_text, quote, code, team). Add fields only as needed (e.g. `chart_spec`, `image_ref`) so layout/export can stay simple.

### 3.2 PPTX export (python-pptx)

- In `studio/slides/` add an export module (e.g. `export_pptx.py`) that takes `SlideDeckArtifact` and writes a valid `.pptx` (via `python-pptx`).
- Requirements: file opens in PowerPoint/LibreOffice without corruption; at least title and content slides render with text (no requirement for charts/images on Day 3).
- Add `studio` dependency in project’s dependency file (e.g. `pyproject.toml` or `requirements.txt`) for `python-pptx` if not already present.

### 3.3 Layout-quality validator (for tests)

- Add a small validator in `studio/slides/` (e.g. `validate_layout.py`): given a `SlideDeckArtifact`, check that no slide has overflowing or obviously unreadable content (e.g. title length below a max, bullet count below a max). This satisfies the hard condition: “at least one layout-quality validator must reject overflow or unreadable slide output.”
- Use this validator in an **acceptance** test: one test that passes a “good” artifact and one that passes a “bad” one (e.g. extremely long title) and assert the validator rejects the bad one.

### 3.4 Tests

- Acceptance: “export PPTX from draft and open without corruption” (e.g. generate file, run a lightweight check: open with python-pptx and assert slide count and at least one shape per slide).
- Acceptance: layout-quality validator accepts valid artifact and rejects invalid one (overflow/unreadable).
- All 8+ acceptance tests still pass; integration tests unchanged if no schema break.

---

## Day 4: Docs and sheets schemas + router wiring

### 4.1 Document outline and artifact (stub)

- Reuse `DocumentOutline` and `DocumentArtifact` from Day 1. Add under `studio/documents/` a minimal “outline generator” that returns a stub `DocumentOutline` (e.g. 3 sections) and a “fill” that returns a stub `DocumentArtifact` (e.g. one section with placeholder text). No LLM required if time is short; focus on schema and API shape.
- Optional: one document type (e.g. Technical Spec) with a simple prompt → outline → fill using LLM.

### 4.2 Sheets outline and artifact (stub)

- Same idea: `SheetOutline` and `SheetArtifact` already defined. In `studio/sheets/` add stub “outline” and “fill” that return minimal workbooks (e.g. one sheet, a few rows). No formula generation yet; just schema and API consistency.

### 4.3 Router

- Add endpoints for docs and sheets, e.g.:
  - `POST /studio/documents/outline` → `DocumentOutline`
  - `POST /studio/documents/draft` → `DocumentArtifact`
  - `POST /studio/sheets/outline` → `SheetOutline`
  - `POST /studio/sheets/draft` → `SheetArtifact`
- Reuse schemas from `studio.schemas`; keep request/response typed.

### 4.4 Invalid-input and errors

- Ensure all POST handlers validate input (e.g. missing `prompt`, invalid JSON) and return **controlled errors** (4xx, no crashes). Add one **acceptance** test per artifact type (or one shared test) that sends invalid/malformed payload and asserts non-500 and predictable error shape. This satisfies “Invalid-input and malformed-payload behavior must return controlled errors.”

### 4.5 Tests

- Acceptance: invalid/malformed payload → controlled error (counts toward 8+).
- Optional: happy-path doc and sheet outline → draft (stub) to lock API contract.

---

## Day 5: Edit loop hook, integration scenarios, CI readiness

### 5.1 Edit loop (minimal hook)

- Add a single endpoint or extend existing draft endpoint for “edit”: e.g. `POST /studio/slides/edit` with `{ "deck": SlideDeckArtifact, "instruction": "Make slide 3 more visual" }` → returns updated `SlideDeckArtifact`. Implementation can be a stub (e.g. return same deck with a note) so the **contract** exists for Days 16–20. This keeps the edit loop in scope without full implementation.

### 5.2 Integration: Oracle → Forge → preview

- In `tests/integration/test_forge_research_to_slides.py` add **executable scenarios** (≥5 total, including existing contract tests):
  1. **Ingest:** Build a minimal `OracleResearchArtifact` (or mock), call Forge ingest (or the slides/outline endpoint with `research`); assert no schema break (e.g. outline or draft returned with expected keys).
  2. **Render:** Forge produces a `SlideDeckArtifact` from that research; assert structure matches `SlideDeckArtifact` schema.
  3. **Export:** From that artifact, export PPTX; assert file exists and opens (e.g. with python-pptx) without corruption.
  4. **Canvas/preview:** If the repo has a preview or Canvas flow that can render a “deck” payload, call it with the artifact and assert no schema break (e.g. 200 and valid response). If not, document “Preview flow: TBD” and assert at least “artifact is valid for preview” (schema check).
  5. **Failure propagation:** Simulate upstream failure (e.g. invalid or empty research) and assert Forge returns graceful error (no 500, logged or measurable). This satisfies “Cross-project failure propagation must be tested.”

Ensure the integration file has at least 5 executable test cases (current scaffold has 5; replace or extend with the above so they are real scenarios).

### 5.3 Retry/idempotency (if applicable)

- If any studio endpoint calls external services or queued tasks, add one acceptance test that validates retry or idempotency behavior (e.g. same request twice returns same outline or safe duplicate handling). If nothing is async/queued yet, add a short comment in the test file: “Retry/idempotency: N/A for sync endpoints; add when queue/external calls exist.”

### 5.4 CI and delivery README

- Run locally: `./ci/run_project_gate.sh p04-forge-studio tests/acceptance/p04_forge/test_exports_open_and_render.py tests/integration/test_forge_research_to_slides.py` and fix any failures.
- Update `CAPSTONE/project_charters/P04_DELIVERY_README.md` with:
  - **Scope Delivered (Days 1–5):** Outline-first slides (and stub docs/sheets), artifact schemas, PPTX export, layout validator, studio router skeleton, Oracle ingestion contract, acceptance and integration scenarios.
  - **Test Evidence:** List which tests cover happy path, invalid input, export open, layout validator, Oracle → Forge, failure propagation.
- Do **not** remove or rename the required sections; fill them in so CI (and the “README file missing” check) is satisfied.

### 5.5 Checklist end of Day 5

- [ ] `studio/` package with `schemas`, `slides`, `documents`, `sheets`, `assets`; `routers/studio.py` mounted.
- [ ] Outline-first flow for slides (prompt → outline → draft) with minimal fill and PPTX export.
- [ ] Stub outline + draft for documents and sheets; all use shared artifact schemas.
- [ ] Acceptance: ≥8 tests (happy path, invalid input, export opens, layout validator, etc.).
- [ ] Integration: ≥5 scenarios (Oracle ingest, render, export, preview/schema, failure propagation).
- [ ] `scripts/test_all.sh quick` passes.
- [ ] `ci/run_project_gate.sh p04-forge-studio ...` passes.
- [ ] `P04_DELIVERY_README.md` updated with Scope, Test Evidence, and other required sections.

---

## Team split (reminder)

- **Student A (Slides):** Days 1–3 focus on slide schemas, outline-first slides, themes, PPTX export, layout validator. Day 4–5 support router and integration tests.
- **Student B (Docs/Sheets):** Days 1–2 support shared schemas and Oracle ingestion contract; Days 3–4 own document and sheet outline/draft stubs and their endpoints; Day 5 integration scenarios and delivery README.

Coordinate on `studio/schemas/` and `routers/studio.py` to avoid merge conflicts (e.g. one owns schemas, one owns router wiring).

---

## References

- Charter: [P04_forge_ai_document_slides_sheets_studio.md](./P04_forge_ai_document_slides_sheets_studio.md)
- Acceptance tests: `tests/acceptance/p04_forge/test_exports_open_and_render.py`
- Integration tests: `tests/integration/test_forge_research_to_slides.py`
- CI: `.github/workflows/project-gates.yml` (check `p04-forge-studio`), `ci/run_project_gate.sh`
- Baseline: `scripts/test_all.sh quick`
- Delivery: `CAPSTONE/project_charters/P04_DELIVERY_README.md`
