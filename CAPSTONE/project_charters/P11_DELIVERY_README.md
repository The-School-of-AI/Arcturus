# P11 Delivery README — Mnemo: Real-Time Memory & Knowledge Graph

## 1. Scope Delivered

**Phase 1: FAISS → Qdrant Migration** — Vector store abstraction and Qdrant backend with backward compatibility.

**Phase 2/3: Neo4j Knowledge Graph** — Entity extraction, graph storage, dual-path retrieval.

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

### Deferred (Phase 2+)
- **Session-level extraction** (design doc §9.2): Single pass for memories + preferences + entities from session summary
- **Unifying preferences** (design doc §9.3): Move preferences/evidence into Qdrant + Neo4j
- Spaces and collections (`memory/spaces.py`)
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
config/qdrant_config.yaml        — Collection specs; session_id, entity_labels indexed
scripts/migrate_faiss_to_qdrant.py   — FAISS → Qdrant memories (used by migrate_all_memories.py)
scripts/test_qdrant_setup.py

# Phase 2/3 (Neo4j Knowledge Graph)
memory/knowledge_graph.py        — Neo4j client, schema, resolve_entity_candidates, expand_from_entities
memory/entity_extractor.py       — LLM extraction; extract_from_query for query NER
memory/memory_retriever.py       — Dual-path retrieval (semantic + entity recall), graph expansion
core/skills/library/entity_extraction/ — Entity extraction skill (SKILL.md, registry)
scripts/migrate_memories_to_neo4j.py  — Backfill Qdrant → Neo4j (used by migrate_all_memories.py)
scripts/migrate_all_memories.py       — Run all migrations in order (FAISS→Qdrant memories, RAG→Qdrant, Qdrant→Neo4j)
```

### Data Flow
```
RemMe / Oracle / Planner
  → get_vector_store(provider=) or shared state
    → QdrantVectorStore (url/api_key from qdrant_config or QDRANT_* env)
      → QdrantClient → Qdrant (local Docker or Cloud)
      → On add: _ingest_to_knowledge_graph → EntityExtractor → KnowledgeGraph → Neo4j
    → FaissVectorStore (default, backward compatible)

Memory retrieval (runs.py → memory_retriever.retrieve)
  → Path 1: Semantic recall (Qdrant vector search, k=10)
  → Path 2: Entity recall (query NER → Neo4j resolve → memory_ids → Qdrant fetch) — runs independently
  → Graph expansion from semantic entity_ids
  → Merge → fused context for agent
```

### Backward Compatibility
- Default `VECTOR_STORE_PROVIDER` is `faiss`; existing RemMe behavior unchanged unless switched
- `episodic_memory.py` / RemMe store uses same protocol; no API contract changes

## 3. API And UI Changes

### Backend
- **No new REST endpoints**; vector store and knowledge graph are internal to RemMe memory flow
- **Env vars**:
  - Phase 1: `VECTOR_STORE_PROVIDER` (qdrant|faiss), `QDRANT_URL`, `QDRANT_API_KEY`
  - Phase 2/3: `NEO4J_ENABLED` (true|false), `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- **Programmatic**:
  - `from memory.vector_store import get_vector_store; store = get_vector_store(provider="qdrant")`
  - `from memory.knowledge_graph import get_knowledge_graph; kg = get_knowledge_graph()` (when `NEO4J_ENABLED=true`)

### Frontend
- No new UI; memory retrieval and knowledge graph remain internal to agent flow

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

## 6. Existing Baseline Regression Status
- **Command**: `scripts/test_all.sh quick`
- **Expected**: Backend and frontend tests pass; no regressions from P11 changes
- Run and record: `scripts/test_all.sh quick` → note pass/fail and any P11-related failures

## 7. Security And Safety Impact
- **Qdrant credentials**: `QDRANT_URL` and `QDRANT_API_KEY` stored in `.env` (gitignored); never committed
- **No new public endpoints**: Vector store access is internal; no new attack surface
- **Local Docker**: No auth by default; suitable for dev only
- **Qdrant Cloud**: Uses API key authentication; ensure keys are scoped and rotated as needed

## 8. Known Gaps
- **Session-level extraction** (design doc §9.2): Entities currently extracted from memory text only; session summary could produce memories + preferences + entities in one pass
- **Unifying preferences** (design doc §9.3): Preferences/evidence in JSON vs Qdrant/Neo4j — potential drift
- **Spaces & collections**: No space management or shared spaces yet
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
