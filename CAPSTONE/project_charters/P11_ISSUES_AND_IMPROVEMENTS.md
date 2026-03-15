# P11 Mnemo — Issues & Improvements (Post First Run)

**Run date:** 2026-03-15  
**Config:** ASYNC_KG_INGEST=false  
**Results:** 27 passed, 6 failed, 1 skipped  

---

## Test Run Summary

| Task Group | Passed | Skipped | Failed |
|------------|--------|---------|--------|
| TG1 (Guest, Single Space) | 15+ | 1 | 1 |
| TG2 (Guest, Multiple Spaces) | 6 | 0 | 3 |
| TG3 (Logged-in, Migration) | 4 | 0 | 0 |
| TG4 (Multi-install) | 2 | 0 | 0 |

### Known Failures (2026-03-15)

- **test_step_06_retrieve_when_met_jon** — Retrieval returns run/chronicle content (cat breeds) instead of user memories. Shared Qdrant may have run outputs that rank higher than RemMe memories.
- **test_recommend_luna_returns_cat**, **test_recommend_living_room_returns_home_decor** — Recommend-space returns `__global__` when shared Qdrant has many global memories that outrank space-scoped ones in top-15.
- **test_recommend_tuna_returns_cat** — Returns different space_id (pollution from other spaces in shared DB).

**Mitigation:** Run against an isolated/empty Qdrant for deterministic assertions. Suite is designed to surface bugs; many tests may fail initially in shared environments.

---

## Issues (by priority)

### P0 — Blocker

1. ~~**POST /runs invokes full agent loop, blocks on Gemini**~~ **FIXED**
   - **Fix:** Added dry-run mode: `RunRequest.dry_run=True` or `DRY_RUN_RUNS=true` env. Skips agent, writes minimal session JSON, returns immediately with status `completed`.

### P1 — High

2. ~~**TG3 and TG4 tests not implemented**~~ **FIXED**
   - **Fix:** Added `task_group_3_logged_in/test_auth_migration.py` (register, login, auth/me, migration). Added `task_group_4_sync/test_sync_api.py` (sync trigger, pull).

3. ~~**RAG and Notes CRUD not covered**~~ **FIXED**
   - **Fix:** Added `task_group_1_guest_single_space/test_rag_notes.py` (list documents, create file, delete).

### P2 — Medium

4. **Retrieval injection tests not implemented**
   - **Impact:** Plan cases TG1-03, TG1-05, TG1-06, TG1-08 verify that `retrieve(query)` injects Raleigh, Jon, episodic context into the agent. These require running the full run or calling `memory_retriever.retrieve()` directly with mocked agent context.
   - **Recommendation:** Add integration tests that call `memory_retriever.retrieve()` directly (or a thin API wrapper) and assert the returned context contains expected memory text and facts.

5. **Space isolation (run-scoped retrieval) not asserted**
   - **Impact:** TG2-03/04 (run in Global vs Cat space; different retrieval) require run creation. Since create_run is skipped, space-scoped retrieval is not validated.
   - **Recommendation:** Add tests that call `memory_retriever.retrieve(query, space_id=...)` directly and assert space filtering.

6. **pytest.ini excludes p11_automation by default**
   - **Impact:** Default `pytest` run skips these tests. Developers may not discover them.
   - **Recommendation:** Document in README and test plan; ensure CI has an explicit job that runs `scripts/run_p11_automation_tests.sh`.

### P3 — Low

7. **Episodic memory verification missing**
   - **Impact:** TG1-06 (episodic reference) and TG1-08 (when did I last meet Jon) depend on episodic store and run completion. Not covered.
   - **Recommendation:** Add episodic-related tests when run creation is mocked or a dedicated episodic API exists.

8. **Entity/Fact extraction quality not asserted**
   - **Impact:** Mock extractor returns deterministic entities; we do not validate that real extraction (or a richer mock) produces correct Neo4j graph state.
   - **Recommendation:** Add tests that query Neo4j for entities/facts after add and assert expected structure (optionally with real LLM in slow suite).

---

## Improvements (by priority)

### P0

1. **Mock AgentLoop4 for non-blocking run creation**
   - Enable `test_tg1_04_create_run` and future run-based tests without invoking Gemini.

### P1

2. **Implement TG3 and TG4 suites**
   - Per plan: registration, migration, logout, guest merge; multi-install sync with LWW.

3. **Add RAG and Notes automation tests**
   - Ensure RAG/Notes CRUD and space scoping work with mocked embeddings.

### P2

4. **Add retrieval injection tests**
   - Direct `retrieve()` calls with assertions on context content.

5. **Add space-scoped retrieval tests**
   - Assert `retrieve(query, space_id=cat_space)` excludes global memories.

### P3

6. **CI job for p11_automation**
   - Add `p11-mnemo-automation` job to `project-gates.yml` that runs `scripts/run_p11_automation_tests.sh` on schedule or manual trigger.

7. **Episodic and entity-quality tests**
   - When infrastructure allows (mocked runs or episodic API).

---

## How to Run

```bash
# Run P11 automation suite (excludes slow tests)
./scripts/run_p11_automation_tests.sh

# With ASYNC_KG_INGEST=true
ASYNC_KG_INGEST=true uv run pytest -m p11_automation -v --tb=short
```

Requires Qdrant and Neo4j running. Tests skip if services are unavailable.
