# Project Gate Manifest

| Project | Key | CI Check | Acceptance | Integration |
|---|---|---|---|---|
| P01 | p01_nexus | p01-nexus-gateway | `tests/acceptance/p01_nexus/test_multichannel_roundtrip.py` | `tests/integration/test_nexus_session_affinity.py` |
| P02 | p02_oracle | p02-oracle-research | `tests/acceptance/p02_oracle/test_citations_back_all_claims.py` | `tests/integration/test_oracle_source_diversity.py` |
| P03 | p03_spark | p03-spark-pages | `tests/acceptance/p03_spark/test_structured_page_not_text_wall.py` | `tests/integration/test_spark_oracle_data_pipeline.py` |
| P04 | p04_forge | p04-forge-studio | `tests/acceptance/p04_forge/test_exports_open_and_render.py` | `tests/integration/test_forge_research_to_slides.py` |
| P05 | p05_chronicle | p05-chronicle-replay | `tests/acceptance/p05_chronicle/test_rewind_restores_exact_state.py` | `tests/integration/test_chronicle_git_checkpoint_alignment.py` |
| P06 | p06_canvas | p06-canvas-runtime | `tests/acceptance/p06_canvas/test_generated_ui_schema_is_safe.py` | `tests/integration/test_canvas_preview_router_coverage.py` |
| P07 | p07_echo | p07-echo-voice | `tests/acceptance/p07_echo/test_voice_command_roundtrip.py` | `tests/integration/test_echo_with_gateway_and_agentloop.py` |
| P08 | p08_legion | p08-legion-swarm | `tests/acceptance/p08_legion/test_swarm_completes_with_worker_failure.py` | `tests/integration/test_legion_chronicle_capture.py` |
| P09 | p09_bazaar | p09-bazaar-marketplace | `tests/acceptance/p09_bazaar/test_tampered_skill_is_blocked.py` | `tests/integration/test_bazaar_skill_install_execution.py` |
| P10 | p10_phantom | p10-phantom-browser | `tests/acceptance/p10_phantom/test_multistep_workflow_completes.py` | `tests/integration/test_phantom_oracle_data_capture.py` |
| P11 | p11_mnemo | p11-mnemo-memory | `tests/acceptance/p11_mnemo/test_memory_influences_planner_output.py` | `tests/integration/test_mnemo_oracle_cross_project_retrieval.py` |
| P12 | p12_aegis | p12-aegis-safety | `tests/acceptance/p12_aegis/test_injection_attempts_blocked.py` | `tests/integration/test_aegis_enforcement_on_oracle_and_legion.py` |
| P13 | p13_orbit | p13-orbit-mobile | `tests/acceptance/p13_orbit/test_mobile_sync_and_action.py` | `tests/integration/test_orbit_with_nexus_echo_mnemo.py` |
| P14 | p14_watchtower | p14-watchtower-ops | `tests/acceptance/p14_watchtower/test_trace_path_is_complete.py` | `tests/integration/test_watchtower_with_gateway_api_usage.py` |
| P15 | p15_gateway | p15-gateway-api | `tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py` | `tests/integration/test_gateway_to_oracle_spark_forge.py` |
