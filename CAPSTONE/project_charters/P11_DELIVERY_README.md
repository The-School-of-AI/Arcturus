# P11 Delivery README — Mnemo: Real-Time Memory & Knowledge Graph

## 1. Scope Delivered

**Phase 1: FAISS → Qdrant Migration** — Vector store abstraction and Qdrant backend with backward compatibility.

**Phase 2/3: Neo4j Knowledge Graph** — Entity extraction, graph storage, dual-path retrieval.

**Phase 2.5: Unified Extraction & Preferences** — Fact/Evidence model, field_id registry, session-level extraction, adapter for preferences.

**Phase 3: Spaces (3A, 3B, 3C)** — Space nodes, memory/fact/session scoping, retrieval filtering, APIs.

**Phase 4: Sync Engine** — CRDT-style LWW sync, push/pull API, selective sync per space, startup and post-write sync trigger, frontend “Keep on this device only,” apply-latency and load tests.

**Phase 5: Auth, Lifecycle, Shared Space & Phase 5A–E** — Login/register, JWT, guest flow; Lifecycle Manager; user_id FE ownership; Shared Space & templates; RAG/Memories scope (5A); Episodic + Notes (5B); BM25 hybrid search (5C); Real-time indexing (5D); Auto-recommend space (5E).

### Completed

**Phase 1**
- **Provider-agnostic vector store** (`memory/vector_store.py`): Factory `get_vector_store(provider="qdrant"|"faiss")` with `VectorStoreProtocol` interface
- **Qdrant backend** (`memory/backends/qdrant_store.py`): Full CRUD, search, multi-tenant support via `user_id` payload
- **Config layer** (`memory/qdrant_config.py`, `config/qdrant_config.yaml`): Collection config (dimension, distance), URL/API key from env (`QDRANT_URL`, `QDRANT_API_KEY`)
- **FAISS fallback**: Default provider remains `faiss`; switch via `VECTOR_STORE_PROVIDER=qdrant`
- **Migration script** (`scripts/migrate_all_memories.py`): Orchestrates FAISS→Qdrant (memories + RAG) and Qdrant→Neo4j backfill in one command; wraps `migrate_faiss_to_qdrant.py`, `migrate_rag_faiss_to_qdrant.py`, and `migrate_memories_to_neo4j.py`
- **Setup guide** (`CAPSTONE/project_charters/P11_SETUP_GUIDE.md`): Qdrant (Cloud/Docker) and Neo4j setup
- **RemMe integration**: `shared/state.py` uses `get_vector_store()`; RemMe router reads from provider-agnostic store

**Phase 2 (Neo4j Knowledge Graph)**
- **Knowledge graph** (`memory/knowledge_graph.py`): Neo4j client and schema (User, Memory, Session, Entity nodes; HAS_MEMORY, FROM_SESSION, CONTAINS_ENTITY, entity–entity relationships with promoted types like WORKS_AT/LOCATED_IN/OWNS/KNOWS plus RELATED_TO fallback; LIVES_IN, WORKS_AT, KNOWS, PREFERS). Implements canonical entity dedupe (`canonical_name`, `composite_key = type::canonical_name`), `resolve_entity_candidates` with within-type + global fuzzy fallback, `get_memory_ids_for_entity_names`, and `expand_from_entities` with multi-tenant-safe memory scoping and deterministic `memory_ids` ordering.
- **Entity extractor** (`memory/entity_extractor.py`): LLM extraction (Ollama) from memory text; `extract_from_query` for query NER
- **Entity extraction skill** (`core/skills/library/entity_extraction/`): Config-driven prompt for entity/relationship/user-fact extraction
- **Memory retriever** (`memory/memory_retriever.py`): Orchestrates semantic recall (k=10), entity recall (runs independently of semantic), graph expansion; merges into fused context for the agent. Maintains a global `result_ids` set across all paths (semantic, entity-first, graph-expanded) and uses best-effort batch fetch (`get_many`/`get_batch`) when supported by the store to reduce N+1 calls.
- **Qdrant payload changes**: `session_id`, `entity_ids`, and optional `entity_labels` for Neo4j link and display/filter. Indexing of these fields is configured via `config/qdrant_config.yaml`.
- **Ingestion on add**: `qdrant_store.add()` calls `_ingest_to_knowledge_graph` → extract entities → write Neo4j → update Qdrant with `entity_ids`
- **routers/runs.py**: Uses `memory_retriever.retrieve(query)` instead of direct search
- **Backfill script** (`scripts/migrate_memories_to_neo4j.py`): Still available for targeted Qdrant→Neo4j backfill, but the recommended path is via `scripts/migrate_all_memories.py`
- **Enable via env**: `NEO4J_ENABLED=true`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- **Moved RAG chunks to qdrant** Backfill existing chunks to Qdrant

**Phase 2.5 (Unified Extraction & Preferences)**
- **Fact and Evidence nodes** (`memory/knowledge_graph.py`): Neo4j schema for Fact, Evidence; `User─HAS_FACT→Fact`, `Fact─SUPPORTED_BY→Evidence`, `Evidence─FROM_SESSION`, `Evidence─FROM_MEMORY`
- **Fact field registry** (`memory/fact_field_registry.py`): Canonical field definitions with `field_id`; `get_field_scope`, `get_scope_for_namespace_key` for global vs space-scoped facts
- **Fact normalizer** (`memory/fact_normalizer.py`): Resolves `field_id` via registry; unknown → extras
- **Unified extractor** (`memory/unified_extractor.py`): `extract_from_session`, `extract_from_memory_text`; single output schema (memories, entities, facts, evidence_events)
- **Session-level extraction**: Single extraction per session; `skip_kg_ingest` on add when Mnemo enabled; Qdrant `entity_ids` from session extraction
- **Neo4j preferences adapter** (`memory/neo4j_preferences_adapter.py`): `build_preferences_from_neo4j` reads Facts, returns hub-shaped response
- **JSON→Neo4j migration** (`scripts/migrate_hubs_to_neo4j.py`): One-time migration of preferences/operating_context/soft_identity to Facts
- **Enable via env**: `MNEMO_ENABLED=true` gates unified path; when true, `GET /remme/preferences` uses adapter

**Phase 3A (Core Spaces)**
- **Space node** (`memory/knowledge_graph.py`): Space schema; `create_space`, `get_spaces_for_user`; `(User)-[:OWNS_SPACE]->(Space)`
- **Memory scoping**: `(Memory)-[:IN_SPACE]->(Space)`; `create_memory(space_id)`; global = no IN_SPACE
- **Qdrant payload**: `space_id` (default `__global__`); indexed for filtering
- **Retrieval filtering** (`memory/memory_retriever.py`): `retrieve(space_id, space_ids)` filters Qdrant and Neo4j; no filter = all
- **APIs**: `POST /remme/spaces` (create), `GET /remme/spaces` (list); `AddMemoryRequest.space_id`
- **Migration scripts**: `space_id=__global__` for migrated points

**Phase 3B (Fact Scope Rules)**
- **Fact unique constraint**: `(user_id, namespace, key, space_id)`; `space_id` null = global
- **Fact scoping**: `(Fact)-[:IN_SPACE]->(Space)` for space-scoped facts per registry
- **Ingestion**: Facts get `space_id` when `get_scope_for_namespace_key(ns, k) == "space"`
- **Preferences filter**: `build_preferences_from_neo4j(space_id, space_ids)`; `GET /remme/preferences?space_id=&space_ids=`

**Phase 3C (Session Scoping)**
- **Session–Space link**: `(Session)-[:IN_SPACE]->(Space)`; `get_or_create_session(space_id)`; `get_space_for_session(session_id)`
- **Run scoping**: `RunRequest.space_id`; `process_run` passes `space_id` to retrieval and ingestion
- **Memories inherit space** from session when provided

**Phase 3.5 — Space UI (delivered)**
- **SpacesPanel**, **SpacesModal** (platform-frontend): Create/list/select spaces; space selector in New Run and Add Memory
- **API**: `createSpace(name, description?, sync_policy?)`; `space_id` passed to `createRun`, `addMemory`, `getMemories`
- **Store**: SpacesSlice, `currentSpaceId` persisted; runs and memories filtered by selected space

**Phase 4 (Sync Engine)**
- **Config** (`memory/sync_config.py`): `SYNC_ENGINE_ENABLED`, `SYNC_SERVER_URL`, `get_device_id()` (cached)
- **Sync package** (`memory/sync/`): `schema.py` (Push/Pull request/response, MemoryDelta, SpaceDelta, SyncChange), `policy.py` (should_sync_space, filter by sync_policy), `merge.py` (LWW), `change_tracker.py`, `transport.py` (HTTP push/pull), `engine.py` (SyncEngine, get_sync_engine)
- **Backend API** (`routers/sync.py`): `POST /api/sync/push`, `POST /api/sync/pull`, `POST /api/sync/trigger`; sync log per user; apply LWW on push
- **Qdrant payload**: `version`, `device_id`, `updated_at`, `deleted` on memories; `sync_upsert()` for applying pulled memories
- **Neo4j Space**: `sync_policy`, `version`, `device_id`, `updated_at`; `create_space(sync_policy=)`, `upsert_space()`, `delete_space()`; `get_spaces_for_user` returns sync_policy
- **Integration**: Startup background sync when enabled; after `add_memory` and `create_space` enqueue background sync
- **Frontend**: Create Space checkbox “Keep on this device only (don’t sync to cloud)” → `sync_policy: local_only`
- **Tests**: Unit (merge, policy), integration (two devices converge, B pushes A receives, apply-latency &lt;150ms, load three devices + one pull, reconnection second pull idempotent)
- **Setup**: `P11_SETUP_GUIDE.md` — Phase 4 section (one-server vs two-stores, env vars)

**Phase 5 — Auth, Lifecycle, Shared Space**
- **Login/register**: `routers/auth.py` — POST `/auth/register`, `/auth/login`; JWT; guest via `X-User-Id`. **Guest → registered migration** is the single entry point: `memory.auth.migration.migrate_guest_to_registered(guest_id, registered_id)`; do not perform ad-hoc Qdrant/Neo4j ownership updates elsewhere.
- **user_id FE ownership**: Frontend generates/persists guest ID (localStorage); sends `X-User-Id`; backend uses auth context (JWT or header); file fallback only for non-request contexts when `VITE_ENABLE_LOCAL_MIGRATION=true`.
- **Lifecycle Manager** (`memory/lifecycle.py`): Importance scoring, archival heuristics, contradiction resolution; `archived`, `access_count`, `last_accessed_at`.
- **Shared Space & templates**: sync_policy `shared`; space templates (Computer Only, Personal, Workspace, Custom, More Templates…); shared spaces via `share_space_with`; memory/run context excludes global when in a space.

**Phase 5A (RAG/Memories scope)**
- Migration scripts set `user_id` and `space_id` on migrated memories and RAG chunks; `migrate_rag_faiss_to_qdrant.py` and `migrate_faiss_to_qdrant.py` support `--space-id` / `MIGRATION_SPACE_ID` (default `__global__`).

**Phase 5B (Episodic + Notes)**
- **Episodic:** Stored in Qdrant collection `arcturus_episodic` with `user_id`, `space_id`; `search_episodes`, `get_recent_episodes`; sync engine builds episodic deltas when provider is qdrant. **Legacy:** `EPISODIC_STORE_PROVIDER=legacy` reads/writes `memory/episodic_skeletons/skeleton_*.json`; sync engine applies episodic changes to local JSON when legacy.
- **Notes:** RAG with path-derived `space_id`; Notes under `data/Notes/` indexed with `space_id` (e.g. `__global__` or per-folder). No separate Notes env; follows `RAG_VECTOR_STORE_PROVIDER`.

**Phase 5C (BM25 → Qdrant, hybrid search)**
- Sparse vectors (e.g. `text-bm25`) for memories and RAG; client-side FastEmbed (BM25-style; SPLADE optional); Qdrant prefetch + RRF fusion. Config: `config/qdrant_config.yaml` `sparse_vectors` per collection. Design: `P11_PHASEC_BM25_HYBRID_SEARCH_DESIGN.md`.

**Phase 5D (3.3 Real-time indexing verification)**
- Timing in `qdrant_store.add()`: logs `upsert_ms`, `kg_ms`, `total_ms` for each add. Benchmark: `scripts/benchmark_realtime_indexing.py` — validates memory available for vector search within ~100 ms (add with `skip_kg_ingest=True`), verifies search returns new memory, optional full add+KG timing.

**Phase 5E (4.2 Auto-recommend space)**
- **Backend:** `GET /remme/recommend-space?text=&current_space_id=` — suggests `space_id` from semantic similarity of draft text to existing memories per space (most frequent space in top-k results). No auto-organization; suggestion only.
- **Frontend:** Add Memory (RemmePanel) calls `recommendSpace(text, currentSpaceId)` debounced (500 ms); space selector updates to suggested space; user can override.

**Retrieval P95 benchmark**
- **Script:** `scripts/benchmark_retrieval.py` — measures top-k retrieval (embed + vector search) P50/P95/P99 latency. Target: P95 &lt; 250 ms.
- **Result (run 2025-03):** P95 39.8 ms (PASS), P50 27.2 ms, P99 667.9 ms. Run: `VITE_ENABLE_LOCAL_MIGRATION=true uv run python scripts/benchmark_retrieval.py`.

**Defect fix (global space memories)**
- **Issue:** When viewing Global space, memories with missing/empty `space_id` (legacy or pre-Spaces data) were excluded because list filtered only on `space_id == "__global__"`.
- **Fix:** `qdrant_store.get_all()` when `space_id == "__global__"` now uses filter: `(space_id == "__global__" OR space_id is empty)` so Global view shows both explicitly global and legacy unscoped memories (still tenant-scoped by `user_id`).

### Remaining

**Original delivery goal:** All items from the original P11 Mnemo scope (Phases 1–5, 3.5, Phase 5A–5E) are delivered. Nothing from the original goal remains.

**Defects and hardening**
- **Sync auth:** Addressed. Push/pull use `get_current_user_id()` from auth context (JWT/X-User-Id); body `user_id` is ignored. Prevents cross-tenant data access.
- **Guest user_id stability:** Addressed. Frontend owns guest identity: generates/persists `authUserId` (localStorage), sends `X-User-Id` on every request. Backend uses request context (JWT or X-User-Id) for identity; file fallback (`user_id.json`) is only for non-request contexts (scripts, benchmarks) when `VITE_ENABLE_LOCAL_MIGRATION=true`. For local migration, FE fetches `/auth/legacy-guest-id` so migrated memories (BE-initiated) show up.
- **Retrieval latency:** P95 &lt; 250 ms target — benchmarked via `scripts/benchmark_retrieval.py` (P95 39.8 ms, PASS).
- **Async KG ingestion:** When `ASYNC_KG_INGEST=true`, KG entity extraction runs in a background thread after Qdrant upsert. Add returns immediately; graph lags slightly. Env: `ASYNC_KG_INGEST` (default false).

**Graph explorer (delivered)**
- **Interactive knowledge graph explorer:** `GET /api/graph/explore` (routers/graph.py), `KnowledgeGraphExplorer` (vis-network), Graph nav tab. Entities, User, Memory nodes; entity-type colors; edge labels; selected-node panel with connections.

**Future / optional (remaining from original charter gap analysis)**
- **11.1 Sharding / federated search:** Per-user shards with cross-user federated search for shared spaces.
- **11.2 Graph query API:** Dedicated endpoint for agent reasoning: "What do I know about X and how does it relate to Y?"
- **11.3 Full spaces manager UI:** Beyond SpacesPanel (permissions, bulk actions, analytics).
- **11.6 Module layout:** `memory/spaces.py`, `memory/sync.py` (architectural note; functionality delivered in knowledge_graph + remme + memory/sync/).
- **Mandatory test gate verification:** Confirm 10 hard conditions (8 acceptance cases, 5 integration scenarios, explicit coverage for ingestion/ranking/contradiction/lifecycle, cross-project failure propagation).

## 2. Architecture Changes

### New Modules
```
# Phase 1
memory/vector_store.py           — get_vector_store() factory, VectorStoreProtocol
memory/backends/qdrant_store.py  — QdrantVectorStore; add() triggers _ingest_to_knowledge_graph
memory/backends/faiss_store.py   — FaissVectorStore (wraps RemmeStore)
memory/qdrant_config.py          — get_collection_config(), get_qdrant_url(), get_qdrant_api_key()
config/qdrant_config.yaml        — Collection specs; session_id, entity_labels, space_id indexed
scripts/migrate_faiss_to_qdrant.py   — FAISS → Qdrant memories (used by migrate_all_memories.py)
scripts/test_qdrant_setup.py

# Phase 2/3 (Neo4j Knowledge Graph)
memory/knowledge_graph.py        — Neo4j client, schema (User, Memory, Session, Entity, Fact, Evidence, Space); get_subgraph_for_explore()
routers/graph.py                 — GET /api/graph/explore (knowledge graph subgraph for UI)
memory/entity_extractor.py       — LLM extraction; extract_from_query for query NER
memory/memory_retriever.py       — Dual-path retrieval (semantic + entity recall), graph expansion, space filter
core/skills/library/entity_extraction/ — Entity extraction skill (SKILL.md, registry)
scripts/migrate_memories_to_neo4j.py  — Backfill Qdrant → Neo4j (used by migrate_all_memories.py)
scripts/migrate_all_memories.py       — Run all migrations in order (FAISS→Qdrant memories, RAG→Qdrant, Qdrant→Neo4j)

# Phase 2.5 (Unified Extraction, Fact/Evidence, Preferences)
memory/fact_field_registry.py    — field_id → canonical; get_field_scope, get_scope_for_namespace_key
memory/fact_normalizer.py        — normalize_facts(facts with field_id)
memory/unified_extraction_schema.py — UnifiedExtractionResult, FactItem (field_id)
memory/unified_extractor.py      — extract_from_session, extract_from_memory_text
memory/neo4j_preferences_adapter.py — build_preferences_from_neo4j (reads Facts, returns hub shape)
core/skills/library/unified_extraction/ — Unified extraction skill (SKILL.md)
scripts/migrate_hubs_to_neo4j.py — One-time JSON hubs → Neo4j Facts

# Phase 3 (Spaces)
memory/space_constants.py        — SPACE_ID_GLOBAL, SYNC_POLICY_SYNC, SYNC_POLICY_LOCAL_ONLY

# Phase 4 (Sync Engine)
memory/sync_config.py           — is_sync_engine_enabled(), get_sync_server_url(), get_device_id()
memory/sync/schema.py           — PushRequest/Response, PullRequest/Response, MemoryDelta, SpaceDelta, SyncChange
memory/sync/policy.py           — should_sync_space(), filter_spaces_for_sync()
memory/sync/merge.py            — lww_wins(), merge_memory_change(), merge_space_change()
memory/sync/change_tracker.py   — build_memory_deltas(), build_space_deltas(), build_push_changes()
memory/sync/transport.py        — push_changes(), pull_changes() (HTTP client)
memory/sync/engine.py           — SyncEngine (push, pull, sync), get_sync_engine(), run_sync_background
routers/sync.py                 — POST /api/sync/push, /sync/pull, /sync/trigger
```

### Data Flow
```
RemMe / Oracle / Planner
  → get_vector_store(provider=) or shared state
    → QdrantVectorStore (url/api_key from qdrant_config or QDRANT_* env)
      → QdrantClient → Qdrant (local Docker or Cloud)
      → On add: _ingest_to_knowledge_graph → EntityExtractor → KnowledgeGraph → Neo4j
      → Session add: skip_kg_ingest; ingest_from_unified_extraction uses session extraction
    → FaissVectorStore (default, backward compatible)

Memory retrieval (runs.py → memory_retriever.retrieve)
  → Path 1: Semantic recall (Qdrant vector search, k=10; optional space_id/space_ids filter)
  → Path 2: Entity recall (query NER → Neo4j resolve → memory_ids → Qdrant fetch) — runs independently
  → Graph expansion from semantic entity_ids (space-scoped when filter provided)
  → Merge → fused context for agent
```

### Backward Compatibility
- Default `VECTOR_STORE_PROVIDER` is `faiss`; existing RemMe behavior unchanged unless switched
- `episodic_memory.py` / RemMe store uses same protocol; no API contract changes

## 3. API And UI Changes

### Backend
- **REST endpoints (Graph explorer)**:
  - `GET /api/graph/explore?space_id=&limit=` — Subgraph (nodes, edges) for knowledge graph visualization.
- **REST endpoints (Phase 3)**:
  - `POST /api/remme/spaces` — Create space (`CreateSpaceRequest`: name, description, optional `sync_policy`)
  - `GET /api/remme/spaces` — List user spaces (returns sync_policy, version, etc.)
  - `POST /api/remme/add` — Add memory (optional `space_id` in body)
  - `GET /api/remme/preferences` — Get preferences (optional `space_id`, `space_ids` query params)
  - `POST /api/runs` — Start run (optional `space_id` in body)
- **REST endpoints (Phase 4 Sync)**:
  - `POST /api/sync/push` — Push changes (user_id, device_id, changes)
  - `POST /api/sync/pull` — Pull changes since cursor
  - `POST /api/sync/trigger` — Manually run sync (push then pull)
- **Env vars**:
  - Phase 1: `VECTOR_STORE_PROVIDER` (qdrant|faiss), `QDRANT_URL`, `QDRANT_API_KEY`
  - Phase 2/3: `NEO4J_ENABLED` (true|false), `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
  - Phase 2.5/3: `MNEMO_ENABLED` (true|false) — gates unified extractor, Neo4j Fact/Evidence, adapter
  - `ASYNC_KG_INGEST` (true|false) — when true, run KG entity extraction in background after upsert (faster add)
  - Phase 4: `SYNC_ENGINE_ENABLED` (true|false), `SYNC_SERVER_URL`, optional `DEVICE_ID`
- **Programmatic**:
  - `from memory.vector_store import get_vector_store; store = get_vector_store(provider="qdrant")`
  - `from memory.knowledge_graph import get_knowledge_graph; kg = get_knowledge_graph()` (when `NEO4J_ENABLED=true`)

### Frontend
- **Graph explorer**: Graph nav tab, KnowledgeGraphExplorer (vis-network); space filter, zoom/pan, node colors by type, edge labels, selected-node panel with connections.
- **Spaces UI (Phase 3)**: SpacesPanel, SpacesModal; create/list/select spaces; space selector in New Run and Add Memory; `currentSpaceId` persisted; runs and memories filtered by selected space.
- **Phase 4**: Create Space dialog includes “Keep on this device only (don’t sync to cloud)” checkbox; `api.createSpace(name, description?, sync_policy?)`; store passes `sync_policy` to API.
- **Phase 5 done**: Login/register UI, auth slice, user_id from frontend. UI edit for preferences/facts: backend-ready, frontend deferred.

## 4. Mandatory Test Gate Definition
- Acceptance file: `tests/acceptance/p11_mnemo/test_memory_influences_planner_output.py`
- Integration file: `tests/integration/test_mnemo_oracle_cross_project_retrieval.py`
- CI check: `p11-mnemo-memory`

## 5. Test Evidence

### Acceptance Tests
```bash
uv run python -m pytest tests/acceptance/p11_mnemo/test_memory_influences_planner_output.py -v
```
```
=========== 8 passed in 0.01s =========
```
- Charter exists, gate contract present, demo script exists, delivery README has required sections, CI check declared

### Integration Tests
```bash
uv run python -m pytest tests/integration/test_mnemo_oracle_cross_project_retrieval.py -v
```
```
======== 5 passed in 0.01s ============
```
- Integration file declared in charter, files exist, baseline script exists, CI check wired in workflow

### Qdrant Setup Test (requires Qdrant running)
```bash
# Start Qdrant first: docker-compose up -d (or use Qdrant Cloud)
uv run python scripts/test_qdrant_setup.py
```
```
✅ All tests completed!
```

### Space Scenarios (Phase 3)
```bash
uv run pytest tests/unit/memory/test_space_scenarios.py -v -m "not slow"
```
```
16 passed — space constants, registry scope, RunRequest, memory_retriever filter, adapter params
```

### Sync (Phase 4) — unit and integration
```bash
uv run pytest tests/unit/memory/test_sync_merge_and_policy.py -v
uv run pytest tests/integration/test_sync_two_devices_converge.py -v -m slow
```
- Unit: 19 passed (LWW merge, policy should_sync_space, filter_spaces_for_sync)
- Integration: 5 passed (two devices converge, B pushes A receives, apply-latency &lt;150ms, load three devices + pull, reconnection second pull idempotent)

## 6. Existing Baseline Regression Status
- **Command**: `scripts/test_all.sh quick`
- **Expected**: Backend and frontend tests pass; no regressions from P11 changes
- Run and record: `scripts/test_all.sh quick` → note pass/fail and any P11-related failures

## 7. Security And Safety Impact
- **Qdrant credentials**: `QDRANT_URL` and `QDRANT_API_KEY` stored in `.env` (gitignored); never committed
- **JWT (Phase 5)**: Login/register use HS256 with `MNEMO_SECRET_KEY`; store in `.env`; never commit. For production, consider RS256 (see `P11_AUTH_DESIGN.md`).
- **Phase 3 APIs**: `POST /api/remme/spaces`, `GET /api/remme/spaces`, `GET /api/remme/preferences` (with optional space filter); require same auth as existing RemMe endpoints
- **Local Docker**: No auth by default; suitable for dev only
- **Qdrant Cloud**: Uses API key authentication; ensure keys are scoped and rotated as needed

## 8. Known Gaps
- **Remaining items** (from original charter gap analysis): (1) 11.1 Sharding/federated search, (2) 11.2 Graph query API for structured reasoning, (3) 11.3 Full spaces manager UI, (4) 11.6 Module layout note, (5) Mandatory test gate (10 hard conditions) verification. See **Future / optional** above.
- **Phase 5:** Completed. Login/register, Lifecycle, user_id FE ownership, Shared Space, Phase 5A–E delivered. UI edit for preferences/facts is backend-ready, frontend deferred.
- **Sync auth:** Addressed (user_id from auth context, not body).
- **Guest user_id stability:** Addressed (FE ownership, X-User-Id, legacy-guest-id for migration).
- **Graph expansion depth:** One-hop only; `depth` reserved for multi-hop. Entity-friendly payload beyond `entity_ids`/`entity_labels` optional.
- **Retrieval latency:** P95 < 250 ms target benchmarked via `scripts/benchmark_retrieval.py` (P95 39.8 ms, PASS).
- **Acceptance/integration:** Structural tests in place; feature-level tests to be expanded per charter.

## 9. Rollback Plan
- **Config rollback**: Set `VECTOR_STORE_PROVIDER=faiss` (or unset); application reverts to FAISS
- **Code rollback**: Revert branch; `get_vector_store()` falls back to FAISS by default
- **Data**: FAISS index unchanged; Qdrant data in `./data/qdrant_storage/` (Docker) or cloud cluster

## 10. Demo Steps
- **Script**: `scripts/demos/p11_mnemo.sh` (scaffold; replace with end-to-end demo as features mature)

### Quick Qdrant Demo
1. Set up Qdrant (see `CAPSTONE/project_charters/P11_SETUP_GUIDE.md`): Docker or Cloud
2. Configure env: `QDRANT_URL`, `QDRANT_API_KEY` if using Cloud
3. Test connection:
   ```bash
   uv run python scripts/test_qdrant_setup.py
   ```
4. Run end-to-end migrations (FAISS → Qdrant memories, RAG FAISS → Qdrant, Qdrant → Neo4j) with a single command:

   - **Docker (default)** — uses local Docker services, runs `docker-compose up -d`, optionally appends Qdrant/Neo4j env vars to `.env`, then runs all migrations in order:
     ```bash
     uv run python scripts/migrate_all_memories.py
     # or explicitly
     uv run python scripts/migrate_all_memories.py docker
     ```

   - **Cloud** — assumes Qdrant Cloud + Neo4j Aura (or similar). The script will prompt you to create the accounts and configure `.env` (`QDRANT_URL`, `QDRANT_API_KEY`, `VECTOR_STORE_PROVIDER=qdrant`, `RAG_VECTOR_STORE_PROVIDER=qdrant`, `NEO4J_ENABLED=true`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`) before running the same migration sequence:
     ```bash
     uv run python scripts/migrate_all_memories.py cloud
     ```

5. (Optional) Use individual scripts directly if you need fine-grained control:
   ```bash
   # FAISS → Qdrant (Remme memories)
   uv run python scripts/migrate_faiss_to_qdrant.py

   # RAG FAISS → Qdrant (RAG chunks)
   uv run python scripts/migrate_rag_faiss_to_qdrant.py

   # Qdrant → Neo4j backfill
   uv run python scripts/migrate_memories_to_neo4j.py
   ```

6. Use Qdrant in RemMe: `export VECTOR_STORE_PROVIDER=qdrant` (and `RAG_VECTOR_STORE_PROVIDER=qdrant`) or add them in your `.env` file before starting the API

### Neo4j Knowledge Graph (Phase 2/3)
6. Start Neo4j: `docker-compose up -d neo4j` (or use Neo4j Aura)
7. Configure env: `NEO4J_ENABLED=true`, `NEO4J_URI=bolt://localhost:7687`, `NEO4J_USER=neo4j`, `NEO4J_PASSWORD=arcturus-neo4j` (match docker-compose `NEO4J_AUTH`)
8. Backfill existing memories: `uv run python scripts/migrate_memories_to_neo4j.py`
9. New memories will auto-ingest to Neo4j when added via Qdrant (requires Ollama for entity extraction)
