# P11 Mnemo — Unified Project Reference

**Use this file** when starting a new chat or when you need full context: it combines the project charter, delivery scope, Neo4j knowledge graph design, and current implementation status in **one self-contained place**. All details are inlined here (no need to open the design doc or explanation for remaining work). Update **§2 Status at a glance** and **§8 Remaining / next steps** as work progresses.

**Do not modify:** `P11_DELIVERY_README.md` (required by project; keep as-is).

**Original sources (attribution only):** `P11_EXPLANATION.md`, `P11_DELIVERY_README.md`, `P11_NEO4J_KNOWLEDGE_GRAPH_DESIGN.md`.

---

## 1. How to use this file

- **New chat:** Attach this file and say: *"Continue from @CAPSTONE/project_charters/P11_UNIFIED_REFERENCE.md"* or ask to implement the next item under **Remaining / next steps**.
- **Context refresh:** Read **§2 Status at a glance** and **§3 Big picture** for high level; **§6–§7** for what’s implemented; **§8** for what’s left.
- **Running updates:** Edit **§2** and **§8** as you complete work or reprioritize.

---

## 2. Status at a glance

| Area | Status | Notes |
|------|--------|------|
| **Phase 1: FAISS → Qdrant** | ✅ Done | Vector store abstraction, Qdrant backend, migration scripts, setup guide |
| **Phase 2/3: Neo4j knowledge graph** | ✅ Core done | Schema, ingestion, dual-path retrieval, backfill; see §7 for details |
| **Retrieval gap (semantic returns 0)** | ✅ Addressed | Entity-first path runs independently; k=10; graph expansion; multi-tenant safe |
| **Memory delete & orphan cleanup** | ✅ Done | `delete_memory` in `knowledge_graph.py`; qdrant_store calls it on delete |
| **Session-level extraction** | ⏳ Not done | §8.2 — one pass for memories + preferences + entities from session |
| **Preferences unification** | ⏳ Not done | §8.3 — move preferences/evidence into Qdrant + Neo4j |
| **Spaces / space_id** | ⏳ Reserved | §8.4 — no code; hook documented for when Spaces are added |
| **Entity-friendly Qdrant payload** | ⏳ Optional | §8.1 — beyond `entity_ids` + optional `entity_labels`; not implemented |
| **Expansion depth** | ⏳ Future | One-hop only; `depth` parameter reserved for multi-hop |
| **Spaces, sync, lifecycle, frontend** | ⏳ Deferred | Per delivery README |
| **user_id: FE ownership** | ⏳ Later phase | Move user_id generation & caching to frontend for server deployment; see §8.6 |

---

## 3. Big picture (what Mnemo is)

**Goal:** Turn Arcturus memory from a “messy filing cabinet” (JSON, local FAISS) into a **smart, interconnected system** that:

- Finds things quickly (vector search + graph)
- Shows how concepts connect (knowledge graph)
- Can later support sync and organization (Spaces, lifecycle)

**Phases (conceptual):**

- **Phase 1:** FAISS → Qdrant (cloud-capable vector store). **Done.**
- **Phase 2/3:** Neo4j knowledge graph (entities, relationships, dual-path retrieval). **Core done.**
- **Phase 3 (Spaces):** Spaces/collections. **Deferred.**
- **Phase 4:** Cross-device sync (CRDT). **Deferred.**
- **Phase 5:** Lifecycle (importance, archival, contradiction resolution). **Deferred.**

**Current systems (pre-Mnemo):**

- **Episodic memory** (`core/episodic_memory.py`): Session skeletons in `memory/session_summaries_index/` (JSON). No graph, local only.
- **RemMe** (`remme/store.py`): FAISS vector store for user preferences/facts; now abstracted behind `get_vector_store(provider=)` so Qdrant can be used.
- **RAG** (`mcp_servers/server_rag.py`): FAISS for documents; RAG chunks can be migrated to Qdrant via `migrate_rag_faiss_to_qdrant.py`.

---

## 4. Scope delivered (from P11 Delivery README)

### 4.1 Completed

**Phase 1**

- Provider-agnostic vector store: `memory/vector_store.py` — `get_vector_store(provider="qdrant"|"faiss")`, `VectorStoreProtocol`
- Qdrant backend: `memory/backends/qdrant_store.py` — CRUD, search, multi-tenant via `user_id`; on add → `_ingest_to_knowledge_graph`
- Config: `memory/qdrant_config.py`, `config/qdrant_config.yaml` — collection config, URL/API key from env
- FAISS fallback: default provider `faiss`; switch with `VECTOR_STORE_PROVIDER=qdrant`
- Migration: `scripts/migrate_all_memories.py` — FAISS→Qdrant (memories + RAG) and Qdrant→Neo4j in one command
- Setup guide: `CAPSTONE/project_charters/P11_mnemo_SETUP_GUIDE.md`
- RemMe: `shared/state.py` uses `get_vector_store()`; RemMe router uses provider-agnostic store

**Phase 2/3 (Neo4j)**

- Knowledge graph: `memory/knowledge_graph.py` — Neo4j client, schema (User, Memory, Session, Entity), canonical dedupe (`canonical_name`, `composite_key`), `resolve_entity_candidates`, `get_memory_ids_for_entity_names`, `expand_from_entities`, `delete_memory` + orphan cleanup
- Entity extractor: `memory/entity_extractor.py` — LLM extraction (Ollama), `extract_from_query` for query NER
- Entity extraction skill: `core/skills/library/entity_extraction/` — config-driven prompt (SKILL.md, registry)
- Memory retriever: `memory/memory_retriever.py` — semantic (k=10) + entity recall (independent) + graph expansion; global `result_ids` dedupe; batch fetch (`get_many`/`get_batch`) when supported
- Qdrant payload: `session_id`, `entity_ids`, optional `entity_labels`; indexing in `config/qdrant_config.yaml`
- Ingestion on add: `qdrant_store.add()` → `_ingest_to_knowledge_graph` → extract → Neo4j → update Qdrant `entity_ids`
- Runs: `routers/runs.py` uses `memory_retriever.retrieve(query)`
- Backfill: `scripts/migrate_memories_to_neo4j.py` (also invoked by `migrate_all_memories.py`)
- Env: `NEO4J_ENABLED=true`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- RAG chunks: backfill to Qdrant supported

### 4.2 Deferred (from delivery README)

- Session-level extraction (§8.2), preferences unification (§8.3), Spaces/collections (§8.4), sync, lifecycle, frontend (graph explorer, spaces manager), performance tuning (e.g. retrieval P95 < 250ms benchmark).

---

## 5. Architecture and modules

### 5.1 New / modified modules

```
# Phase 1
memory/vector_store.py              — get_vector_store(), VectorStoreProtocol
memory/backends/qdrant_store.py     — QdrantVectorStore; add() → _ingest_to_knowledge_graph
memory/backends/faiss_store.py      — FaissVectorStore (wraps RemmeStore)
memory/qdrant_config.py             — get_collection_config(), get_qdrant_url(), get_qdrant_api_key()
config/qdrant_config.yaml           — collection specs; session_id, entity_labels indexed
scripts/migrate_faiss_to_qdrant.py  — FAISS → Qdrant memories
scripts/test_qdrant_setup.py

# Phase 2/3 (Neo4j)
memory/knowledge_graph.py           — Neo4j client, schema, resolve_entity_candidates, expand_from_entities, delete_memory
memory/entity_extractor.py          — LLM extraction; extract_from_query for query NER
memory/memory_retriever.py          — Dual-path retrieval (semantic + entity), graph expansion
core/skills/library/entity_extraction/ — Entity extraction skill (SKILL.md, skill.py, registry)
scripts/migrate_memories_to_neo4j.py — Qdrant → Neo4j backfill
scripts/migrate_all_memories.py     — All migrations in order (FAISS→Qdrant memories, RAG→Qdrant, Qdrant→Neo4j)
```

### 5.2 Data flow

```
RemMe / Oracle / Planner
  → get_vector_store(provider=) or shared state
    → QdrantVectorStore (QDRANT_* or qdrant_config)
      → QdrantClient → Qdrant
      → On add: _ingest_to_knowledge_graph → EntityExtractor → KnowledgeGraph → Neo4j
    → FaissVectorStore (default)

Memory retrieval (runs.py → memory_retriever.retrieve)
  → Path 1: Semantic recall (Qdrant, k=10)
  → Path 2: Entity recall (query NER → Neo4j resolve → memory_ids → Qdrant) — independent of semantic
  → Graph expansion from semantic entity_ids
  → Merge → fused context for agent
```

### 5.3 Backward compatibility

- Default `VECTOR_STORE_PROVIDER` is `faiss`; RemMe unchanged unless switched.
- `episodic_memory.py` / RemMe store use same protocol; no API contract changes.

---

## 6. Neo4j knowledge graph design

### 6.1 Overview

Neo4j stores **extracted entities and relationships** from Remme memories. Link to Qdrant via `memory_id` (Qdrant point id) and `entity_ids` (Neo4j entity ids in Qdrant payload).

### 6.2 Schema

**Nodes**

| Label   | Properties | Purpose |
|--------|------------|--------|
| **User** | `id`, `user_id` | Multi-tenant anchor |
| **Memory** | `id` (Qdrant id), `category`, `source`, `created_at` | Bridge to Qdrant; future: `space_id` or `IN_SPACE` |
| **Session** | `id`, `session_id`, `original_query`, `created_at` | Provenance |
| **Entity** | `id`, `type`, `name`, `canonical_name`, `composite_key`, `created_at` | Person, Company, Concept, etc. `name` = display; `canonical_name` = normalized; `composite_key` = `type::canonical_name` for dedupe |

**Relationships**

| Relationship | From → To | Purpose |
|-------------|-----------|--------|
| HAS_MEMORY | User → Memory | Ownership; multi-tenant |
| FROM_SESSION | Memory → Session | Provenance |
| CONTAINS_ENTITY | Memory → Entity | Memory mentions entity |
| Entity–Entity | Entity → Entity | First-class: WORKS_AT, LOCATED_IN, MET, MET_AT, OWNS, PART_OF, MEMBER_OF, KNOWS, EMPLOYED_BY, LIVES_IN, BASED_IN (`ENTITY_REL_TYPES` in `knowledge_graph.py`). Fallback: RELATED_TO with `type`, `value`, `confidence`, `source_memory_ids` |
| RELATED_TO | Entity → Entity | When extractor type not in ENTITY_REL_TYPES |
| LIVES_IN, WORKS_AT, KNOWS, PREFERS | User → Entity | Derived user facts (with `source_memory_ids`) |
| CONTRADICTS | (Phase 5) | Reserved for conflicting facts |

### 6.3 Qdrant payload (arcturus_memories)

- `user_id` (existing), `session_id`, `entity_ids` (list of Neo4j entity ids). Optional: `entity_labels` for display/filter.
- `config/qdrant_config.yaml`: `indexed_payload_fields` includes `session_id`, `entity_labels`.

### 6.4 Ingestion flow

1. Memory added to Qdrant (with `user_id`, `session_id`).
2. Create/get **User** and **Session** in Neo4j.
3. Create **Memory**; link User–HAS_MEMORY–Memory, Memory–FROM_SESSION–Session.
4. Extract entities/relationships from memory text (LLM via entity_extractor).
5. Create **Entity** nodes (canonical_name, composite_key); link Memory–CONTAINS_ENTITY–Entity.
6. Create entity–entity relationships (first-class types or RELATED_TO).
7. Infer user facts → User–LIVES_IN|WORKS_AT|KNOWS|PREFERS–Entity.
8. Update Qdrant payload with `entity_ids`.

### 6.5 Retrieval flow (current)

```
Query
  ├─ Path 1: Semantic (Qdrant vector search, k=10) → top 3 for context; all 10 for entity_ids → graph expansion
  ├─ Path 2: Entity recall (independent)
  │     — Extract entities from query (EntityExtractor.extract_from_query)
  │     — Resolve vs Neo4j (resolve_entity_candidates, fuzzy; within-type then global fallback)
  │     — get_memory_ids_for_entity_names / expand_from_entities → memory_ids → fetch from Qdrant
  └─ Merge: PREVIOUS + RELATED ENTITIES + ADDITIONAL MEMORIES + USER FACTS → fused context
```

- **Multi-tenant:** `expand_from_entities` scopes by `(User {user_id})-[:HAS_MEMORY]->(Memory)`.
- **Dedupe:** Single `result_ids` set across semantic, entity-first, and graph-expanded; deterministic ordering (e.g. by `Memory.created_at DESC` then de-duped in Python).

### 6.6 Implementation order (already followed)

1. Neo4j client + schema → 2. Entity extraction pipeline → 3. Ingestion on memory add → 4. Qdrant payload (user_id, session_id, entity_ids) → 5. Retrieval (Qdrant + Neo4j expansion) → 6. Migration script (backfill).

---

## 7. Implementation status (verified in code)

- **knowledge_graph.py:** `ENTITY_REL_TYPES` (WORKS_AT, LOCATED_IN, MET, MET_AT, OWNS, PART_OF, MEMBER_OF, KNOWS, EMPLOYED_BY, LIVES_IN, BASED_IN); canonical_name/composite_key; `resolve_entity_candidates` (exact → within-type fuzzy → global fallback); `expand_from_entities` (one-hop, user-scoped); `delete_memory` with orphan cleanup (`DETACH DELETE` for unreferenced entities).
- **entity_extractor.py:** LLM extraction from memory text; `extract_from_query` for query NER; uses `entity_extraction` skill and model from config.
- **memory_retriever.py:** `retrieve()` — semantic k=10; entity path independent; `result_ids` global dedupe; `_store_get_many`/`get_batch` for batch fetch; `expand_from_entities` and entity-first path both used.
- **qdrant_store.py:** `_ingest_to_knowledge_graph` on add; on delete calls `kg.delete_memory(memory_id)` when KG enabled.
- **routers/runs.py:** Calls `retrieve(...)` from memory_retriever for memory context.
- **config/qdrant_config.yaml:** `indexed_payload_fields` includes `session_id`, `entity_labels` for arcturus_memories.
- **core/skills/registry.json:** `entity_extraction` → `core/skills/library/entity_extraction`.
- **scripts:** `migrate_memories_to_neo4j.py`, `migrate_all_memories.py` (docker/cloud modes) present and wired.

---

## 8. Remaining / next steps (running list)

Use this section as the single list of what to do next; update as you complete items.

### 8.1 Optional: Entity-friendly payload in Qdrant

- **Idea:** Store something more readable than raw `entity_ids` in Qdrant (e.g. composite keys like `Person::Jon`, `Company::Google`, or a small list of `{type, name}` objects) so we can do entity-based matching or display without always querying Neo4j.
- **Status:** Not implemented. Current: `entity_ids` + optional `entity_labels`.
- **Practice and tradeoffs:** Keeping only foreign IDs in the vector store is common (single source of truth in the graph). Denormalizing entity names/types into the payload is also common when you need filter-by-entity or hybrid search (e.g. keyword/entity filters in Qdrant) or to avoid a Neo4j round-trip for every read. Tradeoff: payload size and consistency (if an entity is renamed in Neo4j, you’d need to update Qdrant). A practical approach is to store both: `entity_ids` (for Neo4j link) and something like `entity_labels` or `entity_composite_keys` (for display and optional filter/expansion) so reads and entity-first retrieval can work without always hitting Neo4j.
- **Possible future tweaks (if needed):** Tune k, top_for_context, fuzzy_threshold; or add entity labels to Qdrant for filter/display without Neo4j round-trip.

### 8.2 Session-level extraction

- **Current limitation:** Session summaries are used to extract memories (and preferences) via the existing extractor. Those memories are then stored in Qdrant and, on add, we run entity extraction on the **memory text only**. So we can lose entities and relationships that existed in the full session but were compressed or dropped when the memory snippet was written.
- **Target (single session-level extraction):** Update the extractor (and its output schema) so that when processing a **session summary** (or full session), it produces in one shot: (1) **Memories** (as today: add/update/delete commands or text snippets), (2) **Preferences** (as today: key-value or structured for hubs), (3) **Entities and relationships** (same structure as current entity extractor: entities, entity_relationships, user_facts). One JSON structure from the extractor that includes all three. The ingestion pipeline then writes memories to Qdrant (and Neo4j: Memory, Session, User, entities, relationships, user_facts) using that single extraction result, so entities are derived from the **full session context**, not from the shortened memory text.
- **Manual memory add stays separate:** When the user adds a memory directly from the UI, we only have that single text. Keep the current flow: add to Qdrant → run entity extraction on that text → write to Neo4j and update Qdrant. No change to that path; only the **session-based** path becomes “one extraction, memories + preferences + entities.”
- **Extractor change:** The remme extractor (or a unified extraction prompt/skill) would need an updated JSON schema that includes both the existing memory commands and preferences and the new entities/entity_relationships/user_facts. Downstream: same Neo4j ingestion, same Qdrant payload updates; preferences can still be written to staging/hubs as today.

### 8.3 Preferences unification (longer-term)

- **Observation:** Extracted entities and user_facts (LIVES_IN, WORKS_AT, KNOWS, PREFERS) are very similar to what is stored in JSON files (e.g. `evidence_log.json`, `preferences_hub.json`, etc.). Having two places for “user preferences and facts” can lead to duplication and drift.
- **Direction:** Move preferences / evidence into Qdrant + Neo4j so that preference-like facts are stored as memories (Qdrant) and/or as user–entity relationships and entities (Neo4j), giving one source of truth for “what we know about the user” for retrieval and reasoning.
- **UI and existing consumers:** Keep the current UX “more or less” the same by adding an **adapter or service layer** that reads from Qdrant/Neo4j (and optionally from existing JSON for backward compatibility) and exposes the same or similar structure that the UI and hubs expect (e.g. same categories, same field names). Over time, the UI can be pointed only at the new store.
- **Extraction pipeline:** As in 8.2, the session-level extractor would output memories, preferences, and entities; the ingestion path would write preferences into the new store (and optionally still to JSON for a transition period). This may require mapping current hub schema (e.g. dietary_style, verbosity) to entities/concepts and user_facts (e.g. PREFERS → Concept "vegetarian") so that both the graph and the UI stay consistent.

### 8.4 Space / space_id — reserved (do not implement yet)

- **Context:** Mnemo spec includes Spaces/Collections. The graph is currently scoped by `user_id` and `session_id` only; there is no space dimension. When Spaces are introduced, cross-project retrieval could become noisy without scoping.
- **Reserved design (no code yet):**
  - **Option A:** Add `(:Memory)-[:IN_SPACE]->(:Space)` and a `Space` node; constrain all retrieval paths (entities for user, expand, resolve) to memories in the requested space(s).
  - **Option B:** Add `space_id` as a property on `Memory` and filter queries with `WHERE m.space_id = $space_id` (or `IN $space_ids`).
- **Where to add the hook when implementing:** In `memory/knowledge_graph.py`, all user-scoped reads that traverse memories (e.g. `get_entities_for_user`, `expand_from_entities`, `get_memory_ids_for_entity_names`, and any Qdrant call that uses `entity_ids` from the graph) should accept an optional `space_id` (or `space_ids`) and constrain to memories in that space. Ingestion (`create_memory`, `ingest_memory`) would accept optional `space_id` and set the relationship or property. Qdrant payload would include `space_id` for filtered search.

### 8.5 Other known gaps (from delivery README)

- Expansion depth: one-hop only; `depth` reserved for multi-hop.
- Spaces, sync, lifecycle, frontend (graph explorer, spaces manager): deferred.
- Retrieval P95 < 250ms: to be benchmarked.
- Acceptance/integration tests: structural tests in place; feature-level tests (memory influences planner, cross-project retrieval) to be expanded per charter.

### 8.6 user_id: frontend ownership (later phase, for server deployment)

- **Current:** `user_id` is created and maintained at server level (generation and caching on the backend).
- **Target (standard practice for server env):** When the backend is deployed to a server environment, **user_id generation and caching should move to the frontend (FE)**. The FE should generate or obtain a stable user identifier (e.g. anonymous id or auth-derived id), persist it (e.g. localStorage / cookie), and send it with each request so the backend uses it only as an opaque tenant key (no server-side user_id generation or long-lived server cache). Backend remains stateless with respect to user identity.
- **Scope:** Define contract (header or body field for `user_id`), FE changes to own generation and caching, backend to accept and use client-provided `user_id` only; remove or narrow server-side user_id creation/caching where present.

---

## 9. Testing, env, and demo

### 9.1 Mandatory test gates

- **Acceptance:** `tests/acceptance/p11_mnemo/test_memory_influences_planner_output.py` (e.g. 8 cases).
- **Integration:** `tests/integration/test_mnemo_oracle_cross_project_retrieval.py` (e.g. 5 scenarios).
- **CI:** `p11-mnemo-memory`; baseline: `scripts/test_all.sh quick`.

### 9.2 Env vars

- **Phase 1:** `VECTOR_STORE_PROVIDER` (qdrant|faiss), `QDRANT_URL`, `QDRANT_API_KEY`
- **Phase 2/3:** `NEO4J_ENABLED` (true|false), `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`

### 9.3 Demo and migrations

- **Setup:** See `CAPSTONE/project_charters/P11_mnemo_SETUP_GUIDE.md`.
- **Qdrant:** `uv run python scripts/test_qdrant_setup.py`
- **All migrations:** `uv run python scripts/migrate_all_memories.py` (default: docker); or `migrate_all_memories.py cloud`. This runs FAISS→Qdrant (memories), RAG→Qdrant, then Qdrant→Neo4j.
- **Neo4j only backfill:** `uv run python scripts/migrate_memories_to_neo4j.py`
- **Use Qdrant in app:** `VECTOR_STORE_PROVIDER=qdrant` (and `RAG_VECTOR_STORE_PROVIDER=qdrant` if desired). Neo4j: `NEO4J_ENABLED=true` and connection vars.

### 9.4 Rollback

- Set `VECTOR_STORE_PROVIDER=faiss` (or unset) to revert to FAISS. Code falls back to FAISS by default.

---

## 10. Quick reference

| What | Where |
|------|--------|
| Vector store factory | `memory/vector_store.py` — `get_vector_store()` |
| Knowledge graph | `memory/knowledge_graph.py` — `get_knowledge_graph()` when NEO4J_ENABLED |
| Retrieval entrypoint | `memory/memory_retriever.retrieve()` called from `routers/runs.py` |
| Entity extraction | `memory/entity_extractor.py`; skill: `core/skills/library/entity_extraction/` |
| Qdrant config | `config/qdrant_config.yaml`; loader: `memory/qdrant_config.py` |
| Delivery checklist (fixed) | `CAPSTONE/project_charters/P11_DELIVERY_README.md` |
| Setup (Qdrant, Neo4j) | `CAPSTONE/project_charters/P11_mnemo_SETUP_GUIDE.md` |

**Continue in a new chat:** Attach this file and say: *"Continue from P11_UNIFIED_REFERENCE.md"* or *"Implement [item] from §8 Remaining / next steps."*
