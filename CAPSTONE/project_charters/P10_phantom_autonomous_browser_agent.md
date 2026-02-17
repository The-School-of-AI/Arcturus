# PROJECT 10: "Phantom" — Autonomous Browser Agent


> **Inspired by:** OpenClaw (browser control, CDP, snapshots), Perplexity (web crawling)
> **Team:** Browser Automation · **Priority:** P1 · **Duration:** 4 weeks

### Objective
Build a **full-featured autonomous browser agent** that can navigate, interact with, and extract information from any website — supporting complex multi-step web tasks.

### Detailed Features

#### 10.1 Browser Control Engine
- **Managed browser:** Arcturus-controlled Chromium instance via Playwright/Puppeteer
- **CDP integration:** Full Chrome DevTools Protocol support for low-level control
- **Multiple profiles:** Isolated browser profiles per task (separate cookies, sessions, storage)
- **Stealth mode:** Anti-detection measures (random user agents, human-like timing, fingerprint randomization)

#### 10.2 Page Understanding
- **DOM snapshot:** Structured representation of page content for agent reasoning
- **Visual snapshot:** Screenshot capture with element annotation (bounding boxes on interactive elements)
- **Accessibility tree:** Parse ARIA labels and semantic structure for reliable element identification
- **Content extraction:** Smart extraction of article text, tables, forms, lists, media

#### 10.3 Action Capabilities
- **Navigation:** URL navigation, back/forward, tab management, multi-window
- **Interaction:** Click, type, select, scroll, drag-and-drop, file upload, form filling
- **Authentication:** Support for login flows, 2FA handling, OAuth consent screens, session persistence
- **Downloads:** File download management with auto-save to workspace
- **Monitoring:** Watch pages for changes, trigger alerts on content updates

#### 10.4 Workflow Automation
- **Multi-step workflows:** Chain browser actions into complex workflows (e.g., "Log into admin panel, export user report, download as CSV, analyze")
- **Conditional logic:** If-then flows based on page content
- **Error recovery:** Retry failed actions, alternate selectors, screenshot-based fallback navigation
- **Recording:** Record user browser actions and convert to replayable automation scripts

#### 10.5 Deliverables
- Enhance `mcp_servers/server_browser.py` with full Playwright integration
- `browser/controller.py` — browser lifecycle and page interaction engine
- `browser/extractor.py` — intelligent content extraction
- `browser/workflow.py` — multi-step workflow sequencer
- `browser/recorder.py` — action recording and script generation
- Frontend: `features/browser/` — browser control panel, live preview, workflow editor

### Strategy
- Existing `server_browser.py` provides foundation — extend with Playwright for reliability
- Integrate browser content extraction as a data source for Project 2 (Oracle search)
- Add browser as a tool available to all agents in Project 8 (Legion)

---

## 20-Day Execution Addendum

### Team Split
- Single owner: Browser control actions, state model, and workflow runner.

### Day Plan
- Days 1-5: Core browser actions and DOM snapshot model.
- Days 6-10: Agent action loop and checkpointing.
- Days 11-15: Workflow templates and artifact extraction.
- Days 16-20: Retry/anti-stall behavior and stability tests.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p10_phantom/test_multistep_workflow_completes.py`
- Integration: `tests/integration/test_phantom_oracle_data_capture.py`
- CI required check: `p10-phantom-browser`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. A multi-step browser workflow (5 or more steps) must complete with artifact capture; anti-stall logic must abort safely on navigation deadlocks.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Phantom outputs can be consumed by Oracle and are recorded by Chronicle with full action trace.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p10-phantom-browser must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P10_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 3.5s median action loop cycle.
