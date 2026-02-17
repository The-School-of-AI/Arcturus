# PROJECT 6: "Canvas" — Live Visual Workspace & A2UI


> **Inspired by:** OpenClaw (Live Canvas, Agent-to-UI rendering, A2UI protocol)
> **Team:** Frontend Engineering · **Priority:** P1 · **Duration:** 4 weeks

### Objective
Build a **live, agent-controlled visual workspace** where the AI can render interactive UIs, data visualizations, and rich content directly — moving beyond text-only agent output.

### Detailed Features

#### 6.1 Canvas Runtime
- **A2UI protocol:** Agent can push HTML/CSS/JS bundles to the canvas for immediate rendering
- **Sandboxed rendering:** Canvas content runs in an isolated iframe with controlled permissions
- **Live updates:** Agent can update canvas content in real-time (WebSocket push)
- **Snapshot capture:** Agent can take screenshots of canvas content for its own reasoning

#### 6.2 Built-in Canvas Widgets
- **Data visualization:** Charts (D3.js, Chart.js), tables, heatmaps, network graphs
- **Code editor:** Embedded Monaco editor for live code editing with agent suggestions
- **Whiteboard:** Freeform drawing canvas for brainstorming (Excalidraw-based)
- **Map view:** Geographic data visualization (Leaflet/Mapbox)
- **Image gallery:** Grid/carousel layout for generated or fetched images
- **Kanban board:** Task management visualization
- **Timeline:** Historical/project timeline visualization
- **Form builder:** Dynamic form generation for structured data collection

#### 6.3 Canvas Interactions
- **User → Agent:** User interactions in canvas (clicks, form submits, drawing) sent back to agent as events
- **Agent → Canvas:** Agent can `canvas.push` (full replace), `canvas.update` (partial DOM update), `canvas.eval` (execute JS)
- **Canvas persistence:** Save/load canvas states, share canvas via URL
- **Multi-canvas:** Support multiple simultaneous canvases (e.g., code canvas + visualization canvas)

#### 6.4 Deliverables
- `canvas/runtime.py` — canvas server with A2UI protocol handler
- `canvas/widgets/` — pre-built widget library (React components)
- `canvas/sandbox.py` — iframe sandbox security layer
- Frontend: `features/canvas/` — canvas host component, widget toolkit, interaction handler
- WebSocket: `canvas/ws_handler.py` — real-time canvas update channel

### Strategy
- Start with simple HTML rendering in iframe, then add widget library iteratively
- Integrate with existing `apps/` generator for agent-generated full apps in canvas
- Ensure canvas works in both desktop Electron and web client modes

---

## 20-Day Execution Addendum

### Team Split
- Student A: A2UI schema compiler/runtime.
- Student B: Canvas rendering system and component registry.

### Day Plan
- Days 1-5: Schema v1 and runtime loader.
- Days 6-10: Core widget registry and live state bindings.
- Days 11-15: Preview router integration for files/web/content.
- Days 16-20: Validation, error boundaries, and UX polish.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p06_canvas/test_generated_ui_schema_is_safe.py`
- Integration: `tests/integration/test_canvas_preview_router_coverage.py`
- CI required check: `p06-canvas-runtime`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. Invalid schemas must be rejected safely, valid schemas must render deterministically, and sandbox isolation must block forbidden script access.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Canvas preview routing works for Spark pages, Forge artifacts, and Phantom/browser content.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p06-canvas-runtime must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P06_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 1.5s widget update propagation.
