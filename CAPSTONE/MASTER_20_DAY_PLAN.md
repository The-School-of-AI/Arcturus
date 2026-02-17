# Arcturus Master Execution Plan (20 Days)

This is the execution document to use with the detailed project charters in `CAPSTONE/project_charters/`.

## Program Rule
- The source of truth for project scope is the original exhaustive charters (Nexus, Oracle, Forge, etc.) now split into separate files.
- Every project must ship visible output, acceptance tests, and a required CI check.

## Project Charters
- `CAPSTONE/project_charters/P01_nexus_omni_channel_communication_gateway.md`
- `CAPSTONE/project_charters/P02_oracle_ai_powered_search_research_engine.md`
- `CAPSTONE/project_charters/P03_spark_synthesized_content_pages_sparkpages.md`
- `CAPSTONE/project_charters/P04_forge_ai_document_slides_sheets_studio.md`
- `CAPSTONE/project_charters/P05_chronicle_ai_session_tracking_reproducibility.md`
- `CAPSTONE/project_charters/P06_canvas_live_visual_workspace_a2ui.md`
- `CAPSTONE/project_charters/P07_echo_voice_first_interaction_layer.md`
- `CAPSTONE/project_charters/P08_legion_multi_agent_swarm_orchestration.md`
- `CAPSTONE/project_charters/P09_bazaar_skills_agent_marketplace.md`
- `CAPSTONE/project_charters/P10_phantom_autonomous_browser_agent.md`
- `CAPSTONE/project_charters/P11_mnemo_real_time_memory_knowledge_graph.md`
- `CAPSTONE/project_charters/P12_aegis_guardrails_safety_trust_layer.md`
- `CAPSTONE/project_charters/P13_orbit_mobile_cross_platform_experience.md`
- `CAPSTONE/project_charters/P14_watchtower_admin_observability_operations_dashboard.md`
- `CAPSTONE/project_charters/P15_gateway_api_platform_integration_hub.md`

## Team Allocation
- Assign staffing dynamically per sprint based on current cohort size and project risk.
- Keep all 15 projects active in parallel, with each project having at least one accountable owner.
- Use floating support assignments for integration-heavy tracks (`P02`, `P04`, `P08`, `P12`, `P15`).

## 20-Day Cadence (All Teams)

### Sprint 1 (Days 1-5): Architecture Lock and Contracts
- Freeze API/schema contracts for each project.
- Finalize demo scenario and CI check name.
- Create acceptance test skeleton and failing baseline tests.

### Sprint 2 (Days 6-10): Core Implementation
- Implement primary backend/frontend flows.
- Wire project to shared services (memory, loop, MCP, gateway, observability).
- Achieve first end-to-end happy path.

### Sprint 3 (Days 11-15): Hardening and Integrations
- Add failure handling and retries.
- Complete cross-project integration tests.
- Fix performance and reliability regressions.

### Sprint 4 (Days 16-20): Release Readiness
- Stabilize CI and block merge on required checks.
- Produce demo script and runbook.
- Complete final demo with evidence artifacts.

## Mandatory Evidence Per Project
- One runnable demo script under `scripts/demos/`.
- One acceptance test module under `tests/acceptance/`.
- One integration test module under `tests/integration/`.
- One required CI check with stable name.
- One short runbook under `CAPSTONE/project_charters/` describing setup and known risks.
- One delivery report at `CAPSTONE/project_charters/PXX_DELIVERY_README.md` using `CAPSTONE/project_charters/DELIVERY_README_TEMPLATE.md`.

## Existing Baseline Regression Requirement
- In addition to project-specific gates, all student branches must keep the consolidated baseline green.
- Mandatory baseline command: `scripts/test_all.sh quick`.
- A project cannot be marked complete if project gates pass but baseline regression fails.

## Program-Wide CI Policy
- No project is marked complete unless its required check is green.
- No project is marked complete unless baseline regression (`scripts/test_all.sh quick`) is green.
- Final merge window (Days 19-20): only bugfixes and test fixes allowed.
- Any project with red CI by Day 18 triggers scope reduction to MVP with test parity preserved.

## Quality Gates
- Functional: feature demo passes live.
- Reliability: retries/failure paths tested.
- Security: policy/safety checks applied where relevant.
- Observability: traces/logs for critical path.
- Reproducibility: outputs can be regenerated from script + tests.
