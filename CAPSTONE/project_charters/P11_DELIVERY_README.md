# P11 Delivery README — Mnemo: Real-Time Memory & Knowledge Graph

## 1. Scope Delivered

**Phase 1: FAISS → Qdrant Migration** — Vector store abstraction and Qdrant backend with backward compatibility.

**Phase 2/3: Neo4j Knowledge Graph** — Entity extraction, graph storage, dual-path retrieval.

**Phase 2.5: Unified Extraction & Preferences** — Fact/Evidence model, field_id registry, session-level extraction, adapter for preferences.

**Phase 3: Spaces (3A, 3B, 3C)** — Space nodes, memory/fact/session scoping, retrieval filtering, APIs.

### Completed

**Phase 1**
- **Provider-agnostic vector store** (`memory/vector_store.py`): Factory `get_vector_store(provider="qdrant"|"faiss")` with `VectorStoreProtocol` interface
- **Qdrant backend** (`memory/backends/qdrant_store.py`): Full CRUD, search, multi-tenant support via `user_id` payload
- **Config layer** (`memory/qdrant_config.py`, `config/qdrant_config.yaml`): Collection config (dimension, distance), URL/API key from env (`QDRANT_URL`, `QDRANT_API_KEY`)
- **FAISS fallback**: Default provider remains `faiss`; switch via `VECTOR_STORE_PROVIDER=qdrant`
- **Migration script** (`scripts/migrate_all_memories.py`): Orchestrates FAISS→Qdrant (memories + RAG) and Qdrant→Neo4j backfill in one command; wraps `migrate_faiss_to_qdrant.py`, `migrate_rag_faiss_to_qdrant.py`, and `migrate_memories_to_neo4j.py`
- **Setup guide** (`CAPSTONE/project_charters/P11_mnemo_SETUP_GUIDE.md`): Qdrant (Cloud/Docker) and Neo4j setup
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

### Next: Space Introduction in UI

**First priority after Phase 3** — Add Space UI so users can create, select, and manage spaces:
- Create space (call `POST /remme/spaces`)
- Space selector when starting a run or adding a memory
- Pass `space_id` in `POST /runs` and `POST /remme/add` when a space is selected
- List and manage spaces (call `GET /remme/spaces`)

### Deferred
- Space introduction in UI (first priority; see **Next** above)
- Cross-device sync (`memory/sync.py`), CRDT
- Lifecycle manager (`memory/lifecycle.py`), importance scoring, archival
- Frontend: knowledge graph explorer, spaces manager
- Performance and optimization (qdrant index optimization)

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
memory/knowledge_graph.py        — Neo4j client, schema (User, Memory, Session, Entity, Fact, Evidence, Space)
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
memory/space_constants.py        — SPACE_ID_GLOBAL = "__global__"
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
- **New REST endpoints (Phase 3)**:
  - `POST /api/remme/spaces` — Create space (`CreateSpaceRequest`: name, description)
  - `GET /api/remme/spaces` — List user spaces
  - `POST /api/remme/add` — Add memory (optional `space_id` in body)
  - `GET /api/remme/preferences` — Get preferences (optional `space_id`, `space_ids` query params)
  - `POST /api/runs` — Start run (optional `space_id` in body)
- **Env vars**:
  - Phase 1: `VECTOR_STORE_PROVIDER` (qdrant|faiss), `QDRANT_URL`, `QDRANT_API_KEY`
  - Phase 2/3: `NEO4J_ENABLED` (true|false), `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
  - Phase 2.5/3: `MNEMO_ENABLED` (true|false) — gates unified extractor, Neo4j Fact/Evidence, adapter
- **Programmatic**:
  - `from memory.vector_store import get_vector_store; store = get_vector_store(provider="qdrant")`
  - `from memory.knowledge_graph import get_knowledge_graph; kg = get_knowledge_graph()` (when `NEO4J_ENABLED=true`)

### Frontend
- No new UI yet; memory retrieval and knowledge graph remain internal to agent flow
- **Next: Space introduction in UI** — create/select space, pass `space_id` when starting runs or adding memories

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

## 6. Existing Baseline Regression Status
- **Command**: `scripts/test_all.sh quick`
- **Expected**: Backend and frontend tests pass; no regressions from P11 changes
- Run and record: `scripts/test_all.sh quick` → note pass/fail and any P11-related failures

## 7. Security And Safety Impact
- **Qdrant credentials**: `QDRANT_URL` and `QDRANT_API_KEY` stored in `.env` (gitignored); never committed
- **Phase 3 APIs**: `POST /api/remme/spaces`, `GET /api/remme/spaces`, `GET /api/remme/preferences` (with optional space filter); require same auth as existing RemMe endpoints
- **Local Docker**: No auth by default; suitable for dev only
- **Qdrant Cloud**: Uses API key authentication; ensure keys are scoped and rotated as needed

## 8. Known Gaps
- **Space introduction in UI**: Backend ready; users cannot yet create/select spaces in the UI (first priority)
- **Graph expansion depth & payload:** `expand_from_entities` currently does one-hop expansion; `depth` is reserved for future multi-hop traversal. Entity-friendly payloads (composite keys or richer labels in Qdrant) remain optional and are not yet implemented beyond `entity_ids` + optional `entity_labels`.
- **Sync**: No cross-device or CRDT sync
- **Lifecycle**: No importance scoring, archival, or contradiction resolution
- **Retrieval latency**: P95 < 250ms target to be benchmarked; not yet measured
- **Acceptance/integration**: Current tests are structural (charter, files, CI); feature-level tests (memory influences planner, cross-project retrieval) to be expanded per charter contract

## 9. Rollback Plan
- **Config rollback**: Set `VECTOR_STORE_PROVIDER=faiss` (or unset); application reverts to FAISS
- **Code rollback**: Revert branch; `get_vector_store()` falls back to FAISS by default
- **Data**: FAISS index unchanged; Qdrant data in `./data/qdrant_storage/` (Docker) or cloud cluster

## 10. Demo Steps
- **Script**: `scripts/demos/p11_mnemo.sh` (scaffold; replace with end-to-end demo as features mature)

### Quick Qdrant Demo
1. Set up Qdrant (see `CAPSTONE/project_charters/P11_mnemo_SETUP_GUIDE.md`): Docker or Cloud
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
