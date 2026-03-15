# P11 Mnemo — Integration & Automation Test Plan

**Purpose:** Document and execute an extensive suite of integration/automation tests for all P11 Mnemo work. This plan is designed for review before implementation. Reference: `P11_UNIFIED_REFERENCE.md`, `P11_DELIVERY_README.md`.

---

## 1. Goal & Success Criteria

**Goal:** Automated test cases that exercise the application end-to-end so we can:
- Identify defects before production
- Validate behaviors across user modes (guest, registered), spaces, sync policies, and multi-install scenarios
- Surface improvements in retrieval, extraction, sync, and auth flows

**Success Criteria:**
- All critical user journeys have automated coverage
- Tests run with both `ASYNC_KG_INGEST=true` and `ASYNC_KG_INGEST=false`
- Tests run with Qdrant + Neo4j enabled (full Mnemo path)
- LLM calls are mocked where feasible; real LLM used only when necessary (with rate-limiting and sleeps for Gemini)
- Post-execution: prioritized list of **Issues** and **Improvements**

### 1.1 Separate Test Suite — Not Run by Default

These integration/automation tests form a **separate test suite** (e.g. `automation` or `p11_mnemo_automation`). They **must not be executed by default** when running the standard test suite (e.g. `pytest`, `scripts/test_all.sh quick`). To run them, use:

- A **dedicated script** (e.g. `scripts/run_p11_automation_tests.sh`), or
- An **explicit pytest invocation** that targets only this suite (e.g. `pytest tests/automation/p11_mnemo/ -v` or `pytest -m p11_automation`).

This keeps the default CI and developer workflow fast while allowing on-demand or scheduled runs of the full P11 automation suite.

---

## 2. Test Environment Configuration

### 2.1 Mandatory Environment

All integration tests must run with:

| Variable | Value | Notes |
|----------|-------|-------|
| `VECTOR_STORE_PROVIDER` | `qdrant` | Use Qdrant backend |
| `RAG_VECTOR_STORE_PROVIDER` | `qdrant` | RAG in Qdrant |
| `EPISODIC_STORE_PROVIDER` | `qdrant` | Episodic in Qdrant |
| `NEO4J_ENABLED` | `true` | Knowledge graph enabled |
| `MNEMO_ENABLED` | `true` | Unified extractor path |
| `QDRANT_URL` | From `.env` | e.g. `http://localhost:6333` |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | From `.env` | Local or cloud |

### 2.2 Dual ASYNC_KG_INGEST Mode

- **Run 1:** `ASYNC_KG_INGEST=false` — synchronous KG ingestion; immediate entity extraction.
- **Run 2:** `ASYNC_KG_INGEST=true` — background KG ingestion; add returns immediately; tests that rely on graph state must include retries or short sleeps (e.g. 2–5s) before assertions.

### 2.3 Optional (for full E2E)

- `SYNC_ENGINE_ENABLED=true`, `SYNC_SERVER_URL` — when testing sync (Task Groups 3–4).
- `VITE_ENABLE_LOCAL_MIGRATION=true` — for migration flows.

---

## 3. Mocking & LLM Strategy

### 3.1 Where to Mock

| Component | Strategy | Rationale |
|-----------|----------|-----------|
| **Embeddings** | Mock (return deterministic vector, e.g. zeros) | Avoid API calls; tests are deterministic |
| **Unified extractor (LLM)** | Mock when verifying CRUD, sync, space isolation | Fast, no rate limits |
| **Entity extractor (LLM)** | Mock when testing KG wiring, delete, retrieval structure | Same as above |
| **Memory retrieval** | No mock for retrieval tests that validate injection | Need real semantic/entity recall |
| **Planner / Agent** | Mock or bypass when not under test | Focus on memory layer |

### 3.2 When to Use Real LLM (with caution)

- **Extraction quality tests:** Memory text → entities/facts correctness.
- **Retrieval injection tests:** Query → context includes expected memories/facts.
- Use Gemini sparingly; add sleep (e.g. 2–5s) between calls to avoid blocking.
- Prefer Ollama for local runs when available.

### 3.3 Test Labels

- `@pytest.mark.p11_automation` — marks all tests in this suite; used to exclude from default runs and to run this suite explicitly.
- `@pytest.mark.fast` — no LLM, no real Qdrant/Neo4j if mocked.
- `@pytest.mark.integration` — uses real Qdrant + Neo4j.
- `@pytest.mark.slow` — full E2E with real LLM; use for nightly/CI extended suite.

---

## 4. Task Group 1 — Guest User, Single Space, Single Install

**Scope:** Most common early usage: one global space, guest identity, one install.

### 4.1 Setup

- Fresh Qdrant + Neo4j (or isolated collections/tenant).
- Guest `user_id` via `X-User-Id` header (e.g. `00000000-0000-0000-0000-000000000001`).
- Space: `__global__` (default).

### 4.2 Test Cases

| ID | Description | Verification | Mocking |
|----|-------------|--------------|---------|
| TG1-01 | Create sample runs | Runs created; session persisted; `space_id` set | Mock agent/LLM |
| TG1-02 | Add memory: "I moved from New Jersey to Raleigh, NC last year. I am loving it here as the weather is really great" | Memory stored; facts extracted (current_location, weather preference); Neo4j Fact for `current_location`; user facts injected in later runs | Mock or real LLM |
| TG1-03 | Run: "Planning to go for a run, can you check current weather" | Context includes user location (Raleigh) from facts; retrieval injects location into agent context | Mock agent; real retrieval |
| TG1-04 | Add memory: "My friend Jon recently moved from California to Durham. He works at Google. He may need help settling down" | Entities: Jon, Google, Durham; relations: Jon–WORKS_AT–Google; Jon–LOCATED_IN–Durham; correctly stored in Neo4j | Mock or real LLM |
| TG1-05 | Run: "Can you check next week's weather as I am planning to meet Jon at his office" | Context includes Jon, his office (Google/Durham), location; entities from memory correctly injected | Mock agent; real retrieval |
| TG1-06 | Run: "Can you check today's weather?" | Episodic memory referenced (today's prior run) | Mock agent; real retrieval |
| TG1-07 | Add memory: "I met Jon today at his office and had a good chat about local food and weather" | Memory stored; entities linked | Mock or real LLM |
| TG1-08 | Run: "When did I last meet Jon?" | Correct episodic/memory retrieval; answer references today's meeting | Mock agent; real retrieval |
| TG1-09 | Add RAG document | RAG chunk ingested; searchable | Mock embedding if needed |
| TG1-10 | Delete RAG document | RAG removed from store | — |
| TG1-11 | Add note (Notes path) | Note stored with space_id | Mock embedding if needed |
| TG1-12 | Delete memory | Memory removed from Qdrant; Neo4j orphan cleanup | — |
| TG1-13 | Retrieve after delete | Deleted memory not in retrieval results | — |

### 4.3 Sample Example Set (from charter)

A single flow that exercises the above cases in sequence:

1. **Memory Add:** "I moved from New Jersey to Raleigh, NC last year. I am loving it here as the weather is really great"
   - Verify: user facts (current location, weather preference) extracted and stored.

2. **Run 1:** "Planning to go for a run, can you check current weather"
   - Verify: Raleigh location injected from facts into context.

3. **Memory Add:** "My friend Jon recently moved from California to Durham. He works at Google. He may need help settling down"
   - Verify: Jon, Google, Durham entities; Jon–WORKS_AT–Google; Jon–LOCATED_IN–Durham.

4. **Run 2:** "Can you check next week's weather as I am planning to meet Jon at his office"
   - Verify: Jon, office, Durham/Google context injected.

5. **Run 3:** "Can you check today's weather?"
   - Verify: episodic memory (Run 1) referenced.

6. **Memory Add:** "I met Jon today at his office and had a good chat about local food and weather"

7. **Run 4:** "When did I last meet Jon?"
   - Verify: correct episodic/memory retrieval; reference to today's meeting.

8. **RAG / Notes:** Add and delete RAG docs and notes; verify CRUD and retrieval.

### 4.4 Verifications (automated)

- Memory in `get_all(space_id=__global__)`.
- Neo4j: Entity nodes, User–Entity edges (e.g. LIVES_IN, KNOWS).
- Neo4j: Fact nodes with `space_id=__global__`.
- `retrieve(query)` response contains expected memory text / fact-derived context.

---

## 5. Task Group 2 — Guest User, Multiple Spaces (local_only), Single Install

**Scope:** Same install; multiple spaces; space-scoped isolation.

### 5.1 Setup

- Create spaces: e.g. "Cat" (cat-related entities/memories), "Home Decor".
- All `sync_policy=local_only` for this group.

### 5.2 Test Cases

| ID | Description | Verification | Mocking |
|----|-------------|--------------|---------|
| TG2-01 | Add memory in "Cat" space: "My cat Luna loves tuna" | Memory in Cat space only; entity Luna | Mock or real LLM |
| TG2-02 | Add memory in "Home Decor" space: "Planning to repaint the living room blue" | Memory in Home Decor only | — |
| TG2-03 | Run in Global space: "What do I know about Luna?" | No Cat memory injected (space isolation) | Mock agent; real retrieval |
| TG2-04 | Run in Cat space: "What does Luna like?" | Cat memory injected | — |
| TG2-05 | Add memory in Home Decor: "Luna scratched the new couch" | Recommend space suggests Cat (or neutral); user can override | — |
| TG2-06 | GET `/remme/recommend-space?text=Luna&current_space_id=...` | Returns Cat space_id when draft mentions Luna | — |
| TG2-07 | User facts (e.g. current_location) in Global | Same facts available in all spaces (profile scoping) | — |
| TG2-08 | Switch space; list memories | Only space-specific memories returned | — |

### 5.3 Verifications

- Space A memories not injected for runs in Space B.
- Global/user-level facts available across spaces.
- Recommend-space returns semantically appropriate space.

---

## 6. Task Group 3 — Logged-in User, Multiple Spaces (Different sync_policy), Single Install

**Scope:** Registration, migration, logout, new guest, merge.

### 6.1 Setup

- Auth endpoints: `POST /auth/register`, `POST /auth/login`.
- Guest creates runs/memories → registers → migration.
- Multiple spaces with `sync`, `local_only`, `shared` policies.

### 6.2 Test Cases

| ID | Description | Verification | Mocking |
|----|-------------|--------------|---------|
| TG3-01 | Guest: add runs, memories, RAG, notes | All stored under guest_id | — |
| TG3-02 | Guest registers with `guest_id` | Migration: data reassigned to registered user | Mock or skip password hash for speed |
| TG3-03 | Logged-in: list runs, memories | Same data visible | — |
| TG3-04 | Create spaces: sync, local_only, shared | Each has correct sync_policy | — |
| TG3-05 | Add memory in shared space | Memory stored; sync engine includes it in push (if enabled) | — |
| TG3-06 | Logout | No memories, runs, RAG, notes visible (new guest context) | — |
| TG3-07 | As new guest: add runs, memories | Stored under new guest_id; no injection of old logged-in data | — |
| TG3-08 | New guest logs in | Merge: newer guest data + existing account data | — |
| TG3-09 | Verify merged data | Runs/memories from both guest sessions present | — |
| TG3-10 | Sync: push after add; pull on "second device" (same server) | Local store receives pulled memories | Mock second device store if needed |

### 6.3 Verifications

- Migration transaction: no partial state.
- Logout clears context; new guest gets fresh identity.
- Merge is additive; no data loss.

---

## 7. Task Group 4 — Multiple Users, Multiple Spaces, Multiple Installs

**Scope:** 1 central server + 2+ client installs; different users; sync and conflict behavior.

### 7.1 Architecture

- **Server A (port 8000):** Full install; acts as sync server + API.
- **Server B (port 8001), Server C (port 8002):** Individual installs; `SYNC_SERVER_URL` → Server A.

### 7.2 Test Cases

| ID | Description | Verification | Mocking |
|----|-------------|--------------|---------|
| TG4-01 | User U1 on Server A: add memory | Memory stored; push to central | — |
| TG4-02 | User U1 on Server B: pull | Memory received; applied via sync_upsert | — |
| TG4-03 | User U2 on Server B: add memory | U2 data isolated; no U1 data | — |
| TG4-04 | User U2 on Server A: pull | U2 memory received; no U1 corruption | — |
| TG4-05 | LWW conflict: same memory edited on A and B; push both; pull | Last-writer-wins; deterministic merge | — |
| TG4-06 | Shared space: U1 shares with U2 | U2 can see and add memories in shared space | — |
| TG4-07 | U2 add memory in shared space; U1 pull | U1 sees U2's contribution | — |

### 7.3 Verifications

- Tenant isolation (user_id) enforced on push/pull.
- LWW merge produces consistent state.
- Shared space access correct.

---

## 8. Additional Test Areas (Recommended)

### 8.1 API Contract Tests

| Endpoint | Coverage |
|----------|----------|
| `POST /remme/add` | space_id, visibility, category |
| `GET /remme/memories?space_id=` | Filtering |
| `POST /remme/spaces` | sync_policy |
| `GET /remme/recommend-space?text=&current_space_id=` | Suggestion logic |
| `POST /runs` | space_id, retrieval scoping |
| `POST /api/sync/push`, `POST /api/sync/pull` | Auth, tenant isolation |
| `GET /api/graph/explore?space_id=` | Subgraph filtering |

### 8.2 Lifecycle & Contradiction

- Importance scoring: access_count, last_accessed_at updated on retrieval.
- Archived memories excluded from default retrieval.
- Contradicting facts: CONTRADICTS edge; adapter surfaces both for clarification.

### 8.3 Real-time Indexing (Phase 5D)

- `scripts/benchmark_realtime_indexing.py` — memory searchable within ~100 ms (with `skip_kg_ingest=True`).

### 8.4 Episodic & Notes

- Episodic: session summaries in Qdrant with space_id.
- Notes: RAG path-derived space_id; retrieval scoped by space.

---

## 9. Execution Strategy

### 9.1 Separate Suite / No Default Run

These tests live in a **separate automation suite** and **are excluded from default test runs** (e.g. `pytest` without args, `scripts/test_all.sh`). To execute them:

- **Via script:** `scripts/run_p11_automation_tests.sh` (to be created)
- **Via pytest:** `uv run pytest -m p11_automation -v` or `uv run pytest tests/automation/p11_mnemo/ -v`

Ensure `pytest.ini` or `pyproject.tomaml` does **not** include `p11_automation` in the default `-m` filter, so these tests are opt-in.

### 9.2 Test Layout

```
tests/
  automation/
    p11_mnemo/
      conftest.py              # Fixtures: client, env, mock embedding
      task_group_1_guest_single_space/
        test_runs_memories_rag_notes.py
        test_memory_facts_injection.py
      task_group_2_guest_multi_space/
        test_space_isolation.py
        test_recommend_space.py
      task_group_3_logged_in/
        test_registration_migration.py
        test_logout_new_guest_merge.py
      task_group_4_multi_install/
        test_sync_cross_installs.py   # Marked slow; optional
# API tests in tests/api/p11_mnemo/ — mark p11_automation if excluded from default runs
      test_remme_api.py
      test_runs_api.py
      test_sync_api.py
      test_auth_api.py
```

### 9.3 Execution Commands

Use these **only when running the P11 automation suite explicitly** (not part of default `pytest`):

```bash
# Via script (recommended)
./scripts/run_p11_automation_tests.sh

# Via pytest (direct)
# Fast (mocked, excludes slow)
uv run pytest -m "p11_automation and not slow" -v --tb=short

# With ASYNC_KG_INGEST=false
ASYNC_KG_INGEST=false uv run pytest -m "p11_automation and not slow" -v

# With ASYNC_KG_INGEST=true (add retries where graph-dependent)
ASYNC_KG_INGEST=true uv run pytest -m "p11_automation and not slow" -v

# Full suite (including slow)
uv run pytest -m p11_automation -v
```

### 9.4 CI Integration

- Add an **optional** `p11-mnemo-automation` job to `project-gates.yml` that runs this suite on demand or on a schedule (e.g. nightly). **Do not** add these tests to the default CI pipeline that runs on every commit.
- Run with `ASYNC_KG_INGEST=false` for determinism in CI.
- Mark Task Group 4 as optional (requires multiple servers).

---

## 10. Post-Execution: Issues & Improvements

After each run, capture:

### 10.1 Issues (Priority Order)

1. **P0 — Blocker:** Core flow broken (add memory, run, retrieval).
2. **P1 — High:** Migration, sync, or auth defect; data loss/corruption.
3. **P2 — Medium:** Space isolation, recommend-space, or extraction incorrect.
4. **P3 — Low:** UX, performance, or edge cases.

### 10.2 Improvements (Priority Order)

1. **P0:** Latency, reliability, or security improvements.
2. **P1:** Extraction quality, retrieval relevance, or sync robustness.
3. **P2:** UX (e.g. space recommendation accuracy), observability.
4. **P3:** Code quality, test coverage, documentation.

### 10.3 Output Format

```markdown
## P11 Integration Test Run — YYYY-MM-DD

### Config
- ASYNC_KG_INGEST: true/false
- Qdrant: ✓ | Neo4j: ✓

### Results
- TG1: X/Y passed
- TG2: X/Y passed
- TG3: X/Y passed
- TG4: X/Y passed (if run)

### Issues
1. [P0] ...
2. [P1] ...

### Improvements
1. [P0] ...
2. [P1] ...
```

---

## 11. Environment Variables (from .env)

Tests may load from project `.env` for:

- `QDRANT_URL`, `QDRANT_API_KEY` (if using Qdrant Cloud)
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `GEMINI_API_KEY` (when using real Gemini; add sleep between calls)

Override as needed for CI or isolated runs. See §2 for mandatory test configuration.

---

## 12. Dependencies & Prerequisites

- **Qdrant:** Running (Docker or Cloud); collections created.
- **Neo4j:** Running; schema initialized.
- **Ollama (optional):** For local entity extraction when not mocking.
- **Python:** `uv run pytest`; conftest patches where needed.

---

## 13. Approval Checklist (for Review)

- [ ] Separate automation suite / no default run agreed (script or explicit `-m p11_automation`)
- [ ] Task Group 1–4 scope acceptable
- [ ] Mocking strategy agreed
- [ ] ASYNC_KG_INGEST dual run confirmed
- [ ] Additional areas (API, lifecycle, episodic) desired
- [ ] Test layout and execution commands approved
- [ ] Post-execution output format useful

---

**Next Step:** Upon approval, implement tests per this plan and run the suite. Produce the Issues & Improvements report as specified in §10.
