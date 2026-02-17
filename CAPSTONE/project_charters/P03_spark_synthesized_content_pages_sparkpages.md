# PROJECT 3: "Spark" — Synthesized Content Pages (Sparkpages)


> **Inspired by:** GenSpark (Sparkpages, multi-agent orchestration, interactive copilot)
> **Team:** AI Content Engineering · **Priority:** P0 · **Duration:** 4 weeks

### Objective
Generate **dynamic, query-specific content pages** (Arcturus Pages) that consolidate and synthesize information into structured, interactive, shareable artifacts — rivaling GenSpark's Sparkpages.

### Detailed Features

#### 3.1 Page Generation Engine
- **Multi-agent page builder:** Orchestrate specialized sub-agents for different page sections:
  - `OverviewAgent` — executive summary and context
  - `DetailAgent` — deep-dive into each key topic
  - `ComparisonAgent` — side-by-side analysis when multiple entities are involved
  - `DataAgent` — extract and present quantitative data, charts, tables
  - `SourceAgent` — curate and validate sources
- **Page template library:** Pre-built templates for common queries:
  - Topic Overview, Product Comparison, How-To Guide, Market Analysis, Research Brief, Person/Company Profile
- **Dynamic section generation:** Auto-determine section structure based on query type and available data

#### 3.2 Interactive Page Features
- **Embedded copilot:** Each page has an inline chat assistant for follow-up questions, drill-downs
- **Live data binding:** Pages can include live widgets (stock ticker, weather, etc.) that update in real-time
- **Section-level refinement:** Click any section to ask the copilot to expand, simplify, add examples, or cite more sources
- **Export formats:** One-click export to PDF, Markdown, HTML, DOCX
- **Sharing:** Generate shareable public URLs with optional password protection

#### 3.3 Page Collections
- **User library:** All generated pages saved and searchable
- **Folders & tags:** Organize pages into folders, apply tags for easy retrieval
- **Version history:** Track page regenerations and edits
- **Collaboration:** Share pages with team members, allow collaborative editing

#### 3.4 Deliverables
- `content/page_generator.py` — multi-agent page orchestrator
- `content/templates/` — page template definitions (YAML + Jinja2)
- `content/section_agents/` — specialized agents for each page section type
- `content/export.py` — multi-format export engine (PDF via WeasyPrint, DOCX via python-docx)
- Frontend: `features/pages/` — rich page renderer with inline copilot, section editing, export controls
- `routers/pages.py` — API for page CRUD, sharing, export

### Strategy
- Start with "Topic Overview" template as MVP, then rapidly add more templates
- Reuse Project 2 (Oracle) search pipeline as the data ingestion layer for pages
- Page rendering in React with component-per-section architecture for maximum flexibility

---

## 20-Day Execution Addendum

### Team Split
- Student A: Section planning and page generator backend.
- Student B: Interactive widgets, citations UI, section regeneration.

### Day Plan
- Days 1-5: Page schema + section agent contracts.
- Days 6-10: Multi-agent page assembly with charts/media blocks.
- Days 11-15: Interactive blocks and section-level refresh.
- Days 16-20: Collection management, polish, and test stabilization.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p03_spark/test_structured_page_not_text_wall.py`
- Integration: `tests/integration/test_spark_oracle_data_pipeline.py`
- CI required check: `p03-spark-pages`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. Generated page must contain structured sections (not a single markdown block), with at least one chart/media element and section-level citation anchors.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Spark page generation consumes Oracle outputs and can hand off export-ready structures to Forge.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p03-spark-pages must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P03_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 4.0s first render after generation.
