# P11 Delivery README — Mnemo: Real-Time Memory & Knowledge Graph

## 1. Scope Delivered

**Phase 1: FAISS → Qdrant Migration** — Vector store abstraction and Qdrant backend with backward compatibility.

### Completed
- **Provider-agnostic vector store** (`memory/vector_store.py`): Factory `get_vector_store(provider="qdrant"|"faiss")` with `VectorStoreProtocol` interface
- **Qdrant backend** (`memory/backends/qdrant_store.py`): Full CRUD, search, multi-tenant support via `user_id` payload
- **Config layer** (`memory/qdrant_config.py`, `config/qdrant_config.yaml`): Collection config (dimension, distance), URL/API key from env (`QDRANT_URL`, `QDRANT_API_KEY`)
- **FAISS fallback**: Default provider remains `faiss`; switch via `VECTOR_STORE_PROVIDER=qdrant`
- **Migration script** (`scripts/migrate_faiss_to_qdrant.py`): Migrate existing FAISS memories to Qdrant
- **Setup guide** (`CAPSTONE/project_charters/P11_mnemo_SETUP_GUIDE.md`): Option 1 (Qdrant Cloud) and Option 2 (Docker local)
- **RemMe integration**: `shared/state.py` uses `get_vector_store()`; RemMe router reads from provider-agnostic store

### Deferred (Phase 2+)
- Moving RAG chunks to qdrant?
- Moving Episodic to qdrant?
- Moving session memories to qdrant?
- Need to think more whether to keep Preferences/hubs in json or move - will be done as part of Phase 3 (spaces)
- Knowledge graph (`memory/knowledge_graph.py`), entity extraction, Neo4j/NetworkX
- Spaces and collections (`memory/spaces.py`)
- Cross-device sync (`memory/sync.py`), CRDT
- Lifecycle manager (`memory/lifecycle.py`), importance scoring, archival
- Frontend: knowledge graph explorer, spaces manager
- performance and optimization (qdrant index optimization)

## 2. Architecture Changes

### New Modules
```
memory/vector_store.py           — get_vector_store() factory, VectorStoreProtocol
memory/backends/qdrant_store.py  — QdrantVectorStore implementation
memory/backends/faiss_store.py   — FaissVectorStore (wraps RemmeStore)
memory/qdrant_config.py          — get_collection_config(), get_qdrant_url(), get_qdrant_api_key()
config/qdrant_config.yaml        — Collection specs (arcturus_memories: dimension 768, cosine)
scripts/migrate_faiss_to_qdrant.py
scripts/test_qdrant_setup.py
```

### Data Flow
```
RemMe / Oracle / Planner
  → get_vector_store(provider=) or shared state
    → QdrantVectorStore (url/api_key from qdrant_config or QDRANT_* env)
      → QdrantClient → Qdrant (local Docker or Cloud)
    → FaissVectorStore (default, backward compatible)
```

### Backward Compatibility
- Default `VECTOR_STORE_PROVIDER` is `faiss`; existing RemMe behavior unchanged unless switched
- `episodic_memory.py` / RemMe store uses same protocol; no API contract changes

## 3. API And UI Changes

### Backend
- **No new REST endpoints**; vector store is internal to RemMe memory flow
- **Env vars**: `VECTOR_STORE_PROVIDER` (qdrant|faiss), `QDRANT_URL`, `QDRANT_API_KEY` (for Qdrant Cloud or custom URL)
- **Programmatic**: `from memory.vector_store import get_vector_store; store = get_vector_store(provider="qdrant")`

### Frontend
- No new UI in Phase 1; memory retrieval remains internal to agent flow

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
- **Knowledge graph**: Entity extraction, relationships, graph queries not implemented
- **Spaces & collections**: No space management or shared spaces yet
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
4. Migrate FAISS → Qdrant (optional):
   ```bash
   export VECTOR_STORE_PROVIDER=qdrant
   uv run python scripts/migrate_faiss_to_qdrant.py
   ```
5. Use Qdrant in RemMe: `export VECTOR_STORE_PROVIDER=qdrant` or add `VECTOR_STORE_PROVIDER=qdrant` in your `.env` file before starting API
