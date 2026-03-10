# P11 Mnemo — Unified Project Reference

**Use this file** when starting a new chat or when you need full context: it combines the project charter, delivery scope, Neo4j knowledge graph design, unified extraction design, and current implementation status in **one self-contained place**. All details are inlined here. For future phases (Phase 3, 4, 5), **attach only this file** — no need for `p11_unified_extraction_design.md` or other design docs.

Update **§2 Status at a glance** and **§8 Remaining / next steps** as work progresses.

**Do not modify:** `P11_DELIVERY_README.md` (required by project; keep as-is).

**Original sources (attribution only):** `P11_EXPLANATION.md`, `P11_DELIVERY_README.md`, `P11_NEO4J_KNOWLEDGE_GRAPH_DESIGN.md`, `p11_unified_extraction_design.md`.

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
| **Phase 2.5: Unified extractor (field_id)** | ✅ Done | Registry-owned canonical facts; LLM emits field_id only; see §6.7 |
| **Retrieval gap (semantic returns 0)** | ✅ Addressed | Entity-first path runs independently; k=10; graph expansion; multi-tenant safe |
| **Memory delete & orphan cleanup** | ✅ Done | `delete_memory` in `knowledge_graph.py`; qdrant_store calls it on delete |
| **Preferences unification** | ✅ Done | Fact/Evidence, adapter, migration; backend ready for UI edits |
| **Session-level extraction** | ⏳ Phase 3/4 | One pass for memories + preferences + entities from session |
| **Spaces / space_id** | ⏳ Phase 3 | Schema ready; retrieval scoping deferred |
| **UI edit (frontend + backend)** | ⏳ Phase 5 | Backend ready; frontend deferred |
| **Entity-friendly Qdrant payload** | ⏳ Optional | §8.1 — beyond `entity_ids` + optional `entity_labels` |
| **Expansion depth** | ⏳ Future | One-hop only; `depth` parameter reserved for multi-hop |
| **user_id: FE ownership** | ⏳ Phase 5 | Move user_id to frontend for server deployment; see §8.6 |

---

## 3. Big picture (what Mnemo is)

**Goal:** Turn Arcturus memory from a “messy filing cabinet” (JSON, local FAISS) into a **smart, interconnected system** that:

- Finds things quickly (vector search + graph)
- Shows how concepts connect (knowledge graph)
- Can later support sync and organization (Spaces, lifecycle)

**Phases (conceptual):**

- **Phase 1:** FAISS → Qdrant (cloud-capable vector store). **Done.**
- **Phase 2/3:** Neo4j knowledge graph (entities, relationships, dual-path retrieval). **Core done.**
- **Phase 2.5:** Unified extractor with registry-owned fact identity (field_id). **Done.**
- **Phase 3:** Spaces/collections; session-level extraction. **Deferred.**
- **Phase 4:** Cross-device sync (CRDT). **Deferred.**
- **Phase 5:** UI edit frontend, lifecycle (importance, archival, contradiction resolution), user_id FE ownership. **Deferred.**

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

**Phase 2.5 (Unified extractor, field_id)**

- `memory/fact_field_registry.py` — field_id → namespace, key, value_type, append, hub_path; `get_field_def`, `get_valid_field_ids`, `resolve_field_id_to_canonical`, `get_fact_to_hub_mappings`
- `memory/fact_normalizer.py` — Resolves field_id via registry; unknown → extras; list merge
- `memory/unified_extraction_schema.py` — FactItem with field_id (required); `_derive_user_facts_from_facts` uses registry
- `memory/unified_extractor.py` — `_normalize_facts` expects field_id; prompt injects `{{VALID_FIELD_IDS}}`
- `core/skills/library/unified_extraction/SKILL.md` — field_id-only facts; valid field_ids from registry
- `memory/neo4j_preferences_adapter.py` — `FACT_TO_HUB_PATH` derived from registry
- `knowledge_graph.py` — `merge_list_fact`, normalizer used in ingest_memory and ingest_from_unified_extraction

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

# Phase 2.5 (Unified extractor, field_id)
memory/fact_field_registry.py       — field_id as canonical; FIELD_DEFS, get_field_def, get_valid_field_ids, resolve_field_id_to_canonical
memory/fact_normalizer.py           — normalize_facts(facts with field_id) → canonical (namespace, key) from registry
memory/unified_extraction_schema.py — FactItem(field_id, ...); _derive_user_facts_from_facts
core/skills/library/unified_extraction/ — SKILL.md with {{VALID_FIELD_IDS}}
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
| **Fact** | `id`, `user_id`, `namespace`, `key`, `value_type`, `value_text`/`value_number`/`value_bool`/`value_json`, `confidence`, `source_mode`, `status`, `first_seen_at`, `last_seen_at`, `last_confirmed_at`, `editability` | Canonical user fact/preference; unique on (user_id, namespace, key) |
| **Evidence** | `id`, `source_type`, `source_ref`, `timestamp` | Provenance for a fact (optional later: signal_category, raw_excerpt, confidence_delta) |

**Relationships**

| Relationship | From → To | Purpose |
|-------------|-----------|--------|
| HAS_MEMORY | User → Memory | Ownership; multi-tenant |
| FROM_SESSION | Memory → Session | Provenance |
| CONTAINS_ENTITY | Memory → Entity | Memory mentions entity |
| Entity–Entity | Entity → Entity | First-class: WORKS_AT, LOCATED_IN, MET, MET_AT, OWNS, PART_OF, MEMBER_OF, KNOWS, EMPLOYED_BY, LIVES_IN, BASED_IN (`ENTITY_REL_TYPES` in `knowledge_graph.py`). Fallback: RELATED_TO with `type`, `value`, `confidence`, `source_memory_ids` |
| RELATED_TO | Entity → Entity | When extractor type not in ENTITY_REL_TYPES |
| LIVES_IN, WORKS_AT, KNOWS, PREFERS | User → Entity | Derived from Fact+REFERS_TO (step 3); optional `confidence`, `source_memory_ids` |
| HAS_FACT | User → Fact | User owns fact |
| SUPPORTED_BY | Fact → Evidence | Evidence supports fact |
| FROM_MEMORY, FROM_SESSION | Evidence → Memory, Evidence → Session | Evidence provenance |
| REFERS_TO | Fact → Entity | Fact references an entity |
| SUPERSEDES | Fact → Fact | Fact supersedes another |
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

### 6.7 Phase 2.5: field_id as canonical fact identity (Done)

**Core principle:** The LLM must NOT invent canonical storage coordinates (namespace, key). Canonical fact identity is fully owned by the code registry, not the model.

**Architecture:**

- **`field_id`** is the only canonical selector. LLM returns `{ "field_id": "personal_hobbies", "value": ["Running"], "value_type": "json" }` — never namespace or key.
- **`memory/fact_field_registry.py`** — Single source of truth. Defines: `field_id` → `namespace`, `key`, `value_type`, `append`, `hub_path`, aliases. Functions: `get_field_def(field_id)`, `get_valid_field_ids()`, `resolve_field_id_to_canonical(field_id)`, `get_fact_to_hub_mappings()` (for adapter).
- **`memory/fact_normalizer.py`** — Resolves facts via registry using `field_id`. Unknown `field_id` → log warning, route to `namespace=extras`, `key=field_id`. Merges list-valued facts by canonical (ns, key).
- **`memory/unified_extraction_schema.py`** — `FactItem` has `field_id` (required), no namespace/key from model. `_derive_user_facts_from_facts()` uses registry to get namespace for rel_type.
- **Extractor skill** — `core/skills/library/unified_extraction/SKILL.md`. Valid `field_id`s injected from `get_valid_field_ids()` via `{{VALID_FIELD_IDS}}` placeholder. LLM selects only from this list.
- **Flow:** LLM extraction (field_id only) → fact_normalizer (registry lookup) → canonical (namespace, key) → Neo4j upsert. Adapter reads Facts from Neo4j (namespace, key) and maps via `get_fact_to_hub_mappings()`.

**Old pipeline mapping (from design doc):**

| Old | New |
|-----|-----|
| LLM invents namespace+key | LLM emits field_id only |
| Normalizer maps raw→canonical | Registry owns canonical; normalizer resolves field_id |
| Staging JSON | Removed; direct to Neo4j |
| Unknown fields → extras | `namespace=extras`, `key=field_id` |

**Tests:** `tests/unit/memory/test_fact_registry_and_normalizer.py`, `test_unified_extraction_schema.py`, `test_unified_extractor_normalize.py`, `test_neo4j_preferences_adapter_registry.py`, `test_fact_ingestion_pipeline.py`.

---

## 7. Implementation status (verified in code)

- **knowledge_graph.py:** `ENTITY_REL_TYPES`, `USER_ENTITY_REL_TYPES`, `FACT_DERIVATION_TABLE`; Fact/Evidence schema; `upsert_fact()`, `create_evidence()`, `upsert_fact_from_ui()` (step 7); `_derive_user_entity_from_facts()`; `ingest_memory(..., facts=, evidence_events=)` writes Fact/Evidence and derives User–Entity; `ingest_from_unified_extraction()` for session pipeline; optional `space_id` on `create_memory()` and `upsert_fact()` (step 6); `last_confirmed_at` set when source_mode=ui_edit; canonical_name/composite_key; `resolve_entity_candidates`; `expand_from_entities`; `delete_memory`; `create_user_entity_relationship(..., confidence=)`.
- **entity_extractor.py:** LLM extraction from memory text; `extract_from_query` for query NER; uses `entity_extraction` skill and model from config.
- **memory_retriever.py:** `retrieve()` — semantic k=10; entity path independent; `result_ids` global dedupe; `_store_get_many`/`get_batch` for batch fetch; `expand_from_entities` and entity-first path both used.
- **qdrant_store.py:** `_ingest_to_knowledge_graph` on add; when MNEMO_ENABLED uses unified extractor and `to_legacy_entity_result()`; else EntityExtractor; on delete calls `kg.delete_memory(memory_id)` when KG enabled.
- **memory/unified_extraction_schema.py:** Pydantic models for UnifiedExtractionResult, FactItem (field_id only, no namespace/key from model), EvidenceEventItem; `to_legacy_entity_result()`, `_derive_user_facts_from_facts()` uses registry.
- **memory/unified_extractor.py:** UnifiedExtractor (extract_from_session, extract_from_memory_text); single LLM output schema.
- **memory/mnemo_config.py:** `is_mnemo_enabled()` from MNEMO_ENABLED env.
- **routers/runs.py**, **routers/remme.py:** Branch on `is_mnemo_enabled()`; Mnemo path uses get_unified_extractor(), no hub/staging writes.
- **memory/neo4j_preferences_adapter.py:** `build_preferences_from_neo4j()`; `FACT_TO_HUB_PATH` from `get_fact_to_hub_mappings()`.
- **memory/fact_field_registry.py:** FIELD_DEFS, get_field_def, get_valid_field_ids, resolve_field_id_to_canonical; ALIAS_TO_FIELD for adapter read path.
- **memory/fact_normalizer.py:** normalize_facts(raw_facts) — field_id → canonical (namespace, key); unknown → extras.
- **knowledge_graph.py:** `get_facts_for_user()`, `get_evidence_count_for_user()` for adapter.
- **routers/runs.py:** Calls `retrieve(...)` from memory_retriever for memory context.
- **config/qdrant_config.yaml:** `indexed_payload_fields` includes `session_id`, `entity_labels` for arcturus_memories.
- **core/skills/registry.json:** `entity_extraction` → `core/skills/library/entity_extraction`.
- **routers/remme.py:** `PUT /remme/preferences/facts` for UI fact edits (step 7); `UpdateFactRequest`; requires MNEMO_ENABLED.
- **scripts:** `migrate_memories_to_neo4j.py`, `migrate_all_memories.py` (docker/cloud modes) present and wired.

---

## 8. Remaining / next steps (running list)

Use this section as the single list of what to do next; update as you complete items.

**Step 1 (Neo4j schema Fact + Evidence):** Done. Fact and Evidence node types, relationships (User─HAS_FACT→Fact, Fact─SUPPORTED_BY→Evidence, Evidence─FROM_MEMORY→Memory, Evidence─FROM_SESSION→Session, Fact─REFERS_TO→Entity, Fact─SUPERSEDES→Fact), and constraints (Fact unique on `(user_id, namespace, key)`, Evidence unique on `id`) added in `memory/knowledge_graph.py`. User–Entity edges documented as derived from Fact+REFERS_TO (step 3); optional `confidence` on User–Entity for backward compatibility. SchemaField nodes deferred.

**Step 2 (Unified extractor + feature flag):** Done. Pydantic schema in `memory/unified_extraction_schema.py` (UnifiedExtractionResult, FactItem with **field_id only** — no namespace/key from model, EvidenceEventItem). Unified extractor in `memory/unified_extractor.py`; `memory/fact_field_registry.py` owns canonical fact identity; `memory/fact_normalizer.py` resolves field_id → (namespace, key). LLM emits field_id only; registry provides canonical coordinates. Feature flag `MNEMO_ENABLED`; when true: unified extractor, Neo4j Fact/Evidence, adapter. When false: legacy RemMe extractor, normalizer, staging, JSON hubs.

**Step 3 (Ingestion pipelines):** Done. **knowledge_graph.py:** `upsert_fact()`, `create_evidence()`, `_derive_user_entity_from_facts()`, `FACT_DERIVATION_TABLE`. `ingest_memory()` accepts optional `facts` and `evidence_events`. `ingest_from_unified_extraction()` for session pipeline. **Session pipeline:** runs.py and remme.py call `kg.ingest_from_unified_extraction()`. **Direct memory add:** qdrant_store passes facts/evidence into `ingest_memory()`.

**Step 4 (Adapter):** Done. `memory/neo4j_preferences_adapter.py` — `build_preferences_from_neo4j(user_id)` reads Facts from Neo4j via `kg.get_facts_for_user()` and `kg.get_evidence_count_for_user()`, maps Fact namespace+key to hub-shaped response (output_contract, operating_context, soft_identity, evidence, meta), resolves conflicts by confidence and last_seen_at. `GET /remme/preferences` uses adapter when MNEMO_ENABLED; fallback to JSON hubs when disabled. `get_remme_profile` also uses adapter when MNEMO_ENABLED for profile prompt context.

**Step 5 (Migration):** Done. `scripts/migrate_hubs_to_neo4j.py` loads `preferences_hub.json`, `operating_context_hub.json`, `soft_identity_hub.json` from `memory/user_model/`, maps hub fields to Fact `(namespace, key, value)` with `source_mode=migration`, upserts Facts and creates Evidence nodes. Usage: `uv run python scripts/migrate_hubs_to_neo4j.py` or `--dry-run`. Null/empty values skipped. Add to §9.3 migrations list as needed.

**Step 6 (Spaces):** Done (schema preparation). Optional `space_id` added to `create_memory()` and `upsert_fact()`. No retrieval scoping yet; reserved for Phase 3.

**Step 7 (UI edit pipeline):** Backend done. `knowledge_graph.upsert_fact_from_ui()`, `PUT /remme/preferences/facts` with `UpdateFactRequest` (namespace, key, value_type, value/...). **Frontend deferred to Phase 5.**

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

### 8.4 Space / space_id — schema ready (retrieval scoping deferred)

- **Context:** Mnemo spec includes Spaces/Collections. Optional `space_id` added to `create_memory()` and `upsert_fact()` (step 6). Retrieval scoping by space not yet implemented.
- **Reserved design (no code yet):**
  - **Option A:** Add `(:Memory)-[:IN_SPACE]->(:Space)` and a `Space` node; constrain all retrieval paths (entities for user, expand, resolve) to memories in the requested space(s).
  - **Option B:** Add `space_id` as a property on `Memory` and filter queries with `WHERE m.space_id = $space_id` (or `IN $space_ids`).
- **Where to add the hook when implementing:** In `memory/knowledge_graph.py`, all user-scoped reads that traverse memories (e.g. `get_entities_for_user`, `expand_from_entities`, `get_memory_ids_for_entity_names`, and any Qdrant call that uses `entity_ids` from the graph) should accept an optional `space_id` (or `space_ids`) and constrain to memories in that space. Ingestion (`create_memory`, `ingest_memory`) would accept optional `space_id` and set the relationship or property. Qdrant payload would include `space_id` for filtered search.

### 8.5 Other known gaps (from delivery README)

- Expansion depth: one-hop only; `depth` reserved for multi-hop.
- Spaces, sync, lifecycle, frontend (graph explorer, spaces manager): deferred.
- Retrieval P95 < 250ms: to be benchmarked.
- Acceptance/integration tests: structural tests in place; feature-level tests (memory influences planner, cross-project retrieval) to be expanded per charter.

### 8.6 user_id: frontend ownership (Phase 5, for server deployment)

- **Current:** `user_id` is created and maintained at server level.
- **Target:** Move user_id generation and caching to the frontend. FE persists stable user id (localStorage/cookie) and sends with each request. Backend uses as opaque tenant key only.
- **Scope:** Contract (header/body for `user_id`); FE owns generation; backend accepts client-provided `user_id` only.

### 8.7 Phase 5: UI edit, lifecycle, user_id (consolidated remaining work)

**Phase 5 items** (to implement when starting Phase 5):

1. **UI edit (frontend)** — Build UI to edit preferences/facts. Backend ready: `PUT /remme/preferences/facts`, `UpdateFactRequest` (namespace, key, value_type, value). Adapter returns hub shape from Neo4j. UI must present canonical fields (from registry) for editing; display GET /preferences response.

2. **UI edit flow (from design doc)** — On user edit: (1) upsert Fact with `source_mode=ui_edit`, `confidence=1.0`, `last_confirmed_at`; (2) create Evidence with `source_type=ui_edit`; (3) re-run derivation for User–Entity edges if edited fact implies entity relationship. Backend implements this; frontend calls the API.

3. **user_id FE ownership** — See §8.6.

4. **Lifecycle (optional)** — Importance, archival, contradiction resolution. CONTRADICTS relationship reserved in schema.

5. **Other** — Expansion depth (multi-hop), Spaces retrieval scoping, graph explorer, spaces manager — per delivery README.

### 8.8 Future Phase (post–Phase 5) — Spaces and beyond

Items deferred from Phase 4 Spaces UI; to consider in future phases:

1. **Per-space model choice and custom instructions** — Like Perplexity: allow users to override the default model and set custom system instructions per Space, so the assistant behaves differently inside each Space.

2. **Collaboration and sharing** — Invite others to a Space as viewers or “research partners”; permissions (read, add threads, ask follow-ups); for teams/Enterprise: admin control of org-wide Spaces and visibility.

3. **File upload into a Space** — RAG documents scoped to Space; files attached to a Space become searchable context for runs in that Space (e.g. policies, PDFs, class notes). Requires RAG backend support for `space_id`.

4. **Storage limits per Space** — Per-space quotas (e.g. max files, max memories); higher limits for Pro/Enterprise plans.

5. **Space delete** — Backend support for deleting a Space (cascade or soft-delete of associated memories/sessions) if not yet implemented.

### 8.9 Key design principles (from design doc, for future reference)

1. **Neo4j = structured truth** — Entities, relationships, Facts, Evidence.
2. **Qdrant = semantic recall** — Memory text, vector search. Not source of truth for profile.
3. **Registry owns canonical fact identity** — LLM emits field_id only; never namespace/key.
4. **Evidence explains why facts exist** — source_type, source_ref, timestamp.
5. **Derived edges support retrieval** — User–Entity from Fact+REFERS_TO via FACT_DERIVATION_TABLE.
6. **Adapter = read model** — GET /preferences builds hub shape from Neo4j Facts; JSON hubs no longer written.

---

## 9. Testing, env, and demo

### 9.1 Mandatory test gates

- **Acceptance:** `tests/acceptance/p11_mnemo/test_memory_influences_planner_output.py` (e.g. 8 cases).
- **Integration:** `tests/integration/test_mnemo_oracle_cross_project_retrieval.py` (e.g. 5 scenarios).
- **CI:** `p11-mnemo-memory`; baseline: `scripts/test_all.sh quick`.

### 9.2 Env vars

- **Phase 1:** `VECTOR_STORE_PROVIDER` (qdrant|faiss), `QDRANT_URL`, `QDRANT_API_KEY`
- **Phase 2/3:** `NEO4J_ENABLED` (true|false), `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- **P11 Mnemo unified path:** `MNEMO_ENABLED` (true|false). When true: unified extractor, Neo4j Fact/Evidence (step 3), adapter for preferences (step 4). When false: legacy RemMe extractor, normalizer, JSON hubs.

### 9.3 Demo and migrations

- **Setup:** See `CAPSTONE/project_charters/P11_mnemo_SETUP_GUIDE.md`.
- **Qdrant:** `uv run python scripts/test_qdrant_setup.py`
- **All migrations:** `uv run python scripts/migrate_all_memories.py` (default: docker); or `migrate_all_memories.py cloud`. This runs FAISS→Qdrant (memories), RAG→Qdrant, then Qdrant→Neo4j.
- **Neo4j only backfill:** `uv run python scripts/migrate_memories_to_neo4j.py`
- **Hubs → Neo4j (one-time):** `uv run python scripts/migrate_hubs_to_neo4j.py` (or `--dry-run`)
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
| Unified extraction (field_id) | `memory/unified_extractor.py`; skill: `core/skills/library/unified_extraction/` |
| Fact field registry | `memory/fact_field_registry.py` — get_field_def, get_valid_field_ids |
| Fact normalizer | `memory/fact_normalizer.py` — normalize_facts() |
| Preferences adapter | `memory/neo4j_preferences_adapter.py` — build_preferences_from_neo4j() |
| Qdrant config | `config/qdrant_config.yaml`; loader: `memory/qdrant_config.py` |
| Delivery checklist (fixed) | `CAPSTONE/project_charters/P11_DELIVERY_README.md` |
| Setup (Qdrant, Neo4j) | `CAPSTONE/project_charters/P11_mnemo_SETUP_GUIDE.md` |

**Continue in a new chat:** Attach this file only and say: *"Continue from P11_UNIFIED_REFERENCE.md"* or *"Implement [Phase 5 item] from §8.7."*
