# PROJECT 4: "Forge" — AI Document, Slides & Sheets Studio


> **Inspired by:** GenSpark (AI Slides/Sheets), Skywork AI (slides agent)
> **Team:** AI Content Creation · **Priority:** P0 · **Duration:** 4 weeks

### Objective
Build a full **AI-powered document creation suite** that generates professional presentations, documents, and spreadsheets from natural language prompts — an alternative to Google Workspace + AI.

### Detailed Features

#### 4.1 AI Slides Engine
- **Prompt-to-deck:** "Create a 15-slide pitch deck for a Series A raise for an AI startup" → complete deck
- **Theme system:** 100+ professional themes (Corporate, Creative, Minimal, Dark, Gradient, Academic)
- **Slide types:** Title, Content, Two-Column, Comparison, Timeline, Chart, Image+Text, Quote, Code, Team
- **Content intelligence:**
  - Auto-research: Pull relevant data from web using Project 2 (Oracle)
  - Auto-chart: Generate charts from data (bar, line, pie, funnel, scatter)
  - Auto-image: Generate or source relevant images using image generation API
  - Speaker notes: Auto-generate presenter notes for each slide
- **Edit loop:** Chat-driven editing: "Make slide 3 more visual", "Add a competitor comparison on slide 7"
- **Export:** PPTX (via python-pptx), PDF, HTML (interactive), Google Slides link (via API)
- **Template marketplace:** Users can share and discover slide templates

#### 4.2 AI Document Writer
- **Prompt-to-document:** "Write a technical specification for a microservices migration" → structured doc
- **Document types:** Technical Spec, Business Plan, Research Paper, Blog Post, Legal Brief, Report, Proposal, White Paper
- **Structured outline first:** Generate outline → user approves → fill sections → iterate
- **Citation integration:** Auto-cite sources when research is involved (APA, MLA, Chicago, IEEE)
- **Collaborative editing:** Real-time collaborative editing with AI suggestions inline
- **Version control:** Full document version history with diff visualization
- **Export:** DOCX (via python-docx), PDF (via WeasyPrint), Markdown, LaTeX, Google Docs

#### 4.3 AI Sheets/Data Analysis
- **Prompt-to-spreadsheet:** "Create a financial model for a SaaS startup" → full model with formulas
- **Formula generation:** Natural language → Excel/Sheets formula translation
- **Data analysis agent:** Upload CSV/Excel/JSON → auto-generate:
  - Statistical summaries (mean, median, std, distributions)
  - Correlations and trend analysis
  - Anomaly detection
  - Pivot tables and cross-tabulations
- **Visualization agent:** Auto-generate charts from data with best-fit chart type selection
- **Export:** XLSX (via openpyxl), CSV, Google Sheets (via API)

#### 4.4 Deliverables
- `studio/slides/` — slide generation engine, themes, PPTX export
- `studio/documents/` — document generation engine, templates, multi-format export
- `studio/sheets/` — spreadsheet generation, formula engine, data analysis
- `studio/assets/` — theme CSS, font bundles, chart templates
- Frontend: `features/studio/` — WYSIWYG editor components for slides, docs, and sheets
- `routers/studio.py` — API endpoints for creation, editing, export, sharing

### Strategy
- Begin with slides (highest visual impact) → documents → sheets
- Use separate specialized LLM prompts per content type for optimal quality
- Partner slide themes with the frontend team for pixel-perfect rendering

---

## 20-Day Execution Addendum

### Team Split
- Student A: Slides and template/layout engine.
- Student B: Docs/sheets generation and export pipeline.

### Day Plan
- Days 1-5: Outline-first generation and artifact schemas.
- Days 6-10: Slides quality pass (themes, chart placement, notes).
- Days 11-15: Docs and sheets generation with export validators.
- Days 16-20: Edit loop, regression suite, and demo artifacts.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p04_forge/test_exports_open_and_render.py`
- Integration: `tests/integration/test_forge_research_to_slides.py`
- CI required check: `p04-forge-studio`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. Slides/docs/sheets exports must open without corruption, and at least one layout-quality validator must reject overflow or unreadable slide output.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Forge can ingest Oracle research artifacts and render through Canvas/preview flows without schema breakage.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p04-forge-studio must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P04_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 10s draft artifact generation for benchmark prompt.
