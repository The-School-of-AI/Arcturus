# ACTUAL PLAN Test Map

Curated CI-gated tests mapped to `/Users/rohanshravan/TSAI/Arcturus/CAPSTONE/ACTUAL PLAN.md`.

## Core Architecture (Phase 1)
- `tests/test_registry.py`
- `tests/test_dynamic_injection.py`
- `tests/test_planner_injection.py`
- `tests/test_serialization_resume.py`

## MCP & Tooling (Phase 2)
- `tests/test_mcp_inspector.py`
- `tests/test_tool_schema.py`

## Skills & Prompt Consolidation (Phase 3)
- `tests/test_skills.py`
- `tests/test_skill_injection.py`
- `tests/test_runtime_toggle.py`
- `tests/test_bootstrap_skills.py`
- `tests/test_bootstrap_runner.py`

## Active Memory (Phase 4)
- `tests/test_episodic_retrieval.py`
- `tests/test_preplan_retrieval.py`
- `tests/test_semantic_injection.py`
- `tests/test_profile_loader.py`
- `tests/test_profile_injection.py`
- `tests/test_steerability.py`
- `tests/test_preference_enforcement.py`
- `tests/test_user_profiling.py`

## Frontend/App Generation (Phase 5)
- `tests/test_ui_schema.py`
- `tests/test_ui_generator.py`
- `tests/test_self_correction.py` (external opt-in)
- `tests/test_production_build.py` (build opt-in)

## Unified Previews (Phase 6)
- `tests/test_unified_previews.py`

## Unified Sandbox (Phase 7)
- `tests/test_universal_sandbox.py`

## Stress & E2E (Phase 9, opt-in)
- `tests/stress_tests/test_budget.py`
- `tests/stress_tests/mini_sandbox_test.py`
- `tests/stress_tests/test_hot_reload.py`
- `tests/stress_tests/test_skill_toggle.py`
