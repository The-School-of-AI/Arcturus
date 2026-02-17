# PROJECT 11: "Mnemo" — Real-Time Memory & Knowledge Graph


> **Inspired by:** Perplexity (Spaces & Collections, internal knowledge), existing scaling plan (Project "Archive")
> **Team:** AI Memory Engineering · **Priority:** P0 · **Duration:** 4 weeks

### Objective
Overhaul Arcturus's memory system from local JSON/FAISS to a **scalable, real-time knowledge graph** with cross-device sync, semantic search, and collaborative knowledge spaces.

### Detailed Features

#### 11.1 Distributed Vector Store
- **Migration from FAISS to Qdrant/Weaviate:** Cloud-hosted vector DB with multi-tenancy
- **Hybrid search:** Combined vector similarity + keyword search + metadata filtering
- **Real-time indexing:** New memories indexed within 100ms of creation
- **Sharding strategy:** Per-user shards with cross-user federated search (for shared spaces)

#### 11.2 Knowledge Graph Layer
- **Entity extraction:** Auto-extract entities (people, companies, concepts, dates) from conversations
- **Relationship mapping:** Build and maintain entity-relationship graph as agent learns
- **Temporal awareness:** Track when facts were learned and whether they've been superseded
- **Graph queries:** Agent can reason over the knowledge graph: "What do I know about X and how does it relate to Y?"
- **Visualization:** Interactive knowledge graph explorer in the frontend

#### 11.3 Spaces & Collections
- **Personal spaces:** Dedicated knowledge areas per project/topic (e.g., "Startup Research", "Home Renovation")
- **Shared spaces:** Team members can contribute to and query shared knowledge spaces
- **Auto-organization:** Agent suggests which space new information belongs to
- **Space templates:** Pre-configured spaces for common use cases (Research Project, Code Repository, Client Management)

#### 11.4 Cross-Device Sync
- **CRDT-based sync:** Conflict-free replication across devices using CRDTs
- **Offline-first:** Full functionality offline, sync when connected
- **Selective sync:** Per-space sync policies (some spaces local-only for privacy)

#### 11.5 Memory Lifecycle
- **Importance scoring:** Auto-score memory importance, promote frequently accessed memories
- **Decay & archival:** Gradually archive low-importance memories (retrievable but not in active search)
- **Contradiction resolution:** When new info conflicts with existing memory, present both and let user/agent resolve
- **Privacy controls:** Per-memory privacy levels, user can mark memories as private/shareable/public

#### 11.6 Deliverables
- `memory/vector_store.py` — Qdrant/Weaviate adapter with hybrid search
- `memory/knowledge_graph.py` — entity extraction + relationship graph (Neo4j or in-memory networkx)
- `memory/spaces.py` — spaces and collections manager
- `memory/sync.py` — CRDT-based cross-device synchronization
- `memory/lifecycle.py` — importance scoring, decay, archival
- Migrate `core/episodic_memory.py` to new system with backward compatibility
- Frontend: `features/memory/` — knowledge graph explorer, spaces manager, memory browser

### Strategy
- Phase 1: Migrate FAISS → Qdrant with feature parity (2 weeks)
- Phase 2: Add knowledge graph layer (3 weeks)
- Phase 3: Spaces & Collections (2 weeks)
- Phase 4: Cross-device sync (3 weeks)
- Maintain backward compatibility with existing `episodic_memory.py` API

---

## 20-Day Execution Addendum

### Team Split
- Student A: Vector memory architecture and retrieval APIs.
- Student B: Knowledge graph relations, spaces/collections UX.

### Day Plan
- Days 1-5: Memory schema and ingestion path.
- Days 6-10: Retrieval ranking and relevance tuning.
- Days 11-15: Knowledge graph construction and contradiction rules.
- Days 16-20: Sync/lifecycle policies and load testing.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p11_mnemo/test_memory_influences_planner_output.py`
- Integration: `tests/integration/test_mnemo_oracle_cross_project_retrieval.py`
- CI required check: `p11-mnemo-memory`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. Memory ingestion, retrieval ranking, contradiction handling, and lifecycle archival policies must each have explicit acceptance coverage.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Mnemo retrieval affects Planner/Oracle behavior before plan generation, not only post-response.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p11-mnemo-memory must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P11_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 250ms top-k retrieval latency.
