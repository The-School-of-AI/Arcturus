# P11 Mnemo: Neo4j Knowledge Graph Design

> **Status:** Implemented. Core: `memory/knowledge_graph.py`, `memory/entity_extractor.py`, `scripts/migrate_memories_to_neo4j.py`. Retrieval (9.1): `memory/memory_retriever.py`, dual-path recall, multi-tenant-safe expansion. See §9 for remaining work.
> **Context:** Phase 3 of Mnemo — Neo4j layer for Remme memories (entities, relationships, User/Session nodes).

---

## 1. Overview

Neo4j stores extracted entities and relationships from Remme memories. It ties to Qdrant via `memory_id` (Qdrant point id) and `entity_ids` (Neo4j entity ids in Qdrant payload).

### 1.1 Implementation status (Mar 2026)

- **Implemented (code landed):**
  - **Canonical entity dedupe:** Entity nodes now store `canonical_name` and `composite_key = type::canonical_name` so `"Google"` and `"google"` (same type) merge; display `name` is preserved.
  - **Relationship modeling:** Entity–entity relationships use a promoted set of first-class Neo4j relationship types (`ENTITY_REL_TYPES` in `knowledge_graph.py`, e.g. `WORKS_AT`, `LOCATED_IN`, `OWNS`) with `RELATED_TO` as a fallback when the extractor emits an unknown type.
  - **Entity resolution:** `resolve_entity_candidates` does exact match, then fuzzy match **within-type first**, then **global fallback** so wrong NER types (e.g. `"John"` as Concept) can still match existing `Person` entities.
  - **Graph expansion:** `expand_from_entities` traverses all entity relationship types (first-class + `RELATED_TO`), scopes memories to the requesting user via `(u:User {user_id})-[:HAS_MEMORY]->(m)` to avoid multi-tenant leakage, and returns deterministically ordered `memory_ids` (by `m.created_at DESC`, then de-duped in Python while preserving order).
  - **Retrieval orchestrator:** `memory_retriever.retrieve` runs semantic (k=10) and entity recall independently, uses a **global `result_ids` dedupe set** across all paths (semantic, entity-first, graph-expanded), and batch-fetches memories where the store supports it (`get_many`/`get_batch`) to reduce N+1 calls.
  - **Backfill:** `scripts/migrate_memories_to_neo4j.py` backfills existing Qdrant memories via `KnowledgeGraph.ingest_memory`, which now applies canonicalization and relationship modeling automatically.
  - **Memory delete & orphan cleanup:** When a memory is deleted (`delete_memory`), the Memory node and its relationships are removed; entities that are no longer referenced by any Memory (orphans) are then removed via `DETACH DELETE`, along with their entity-entity and user-entity relationships, so the graph does not retain dead data (e.g. "Jon" and "Google" that existed only in that memory).

- **Remaining / future work:**
  - **Entity-friendly payload in Qdrant (optional)** — §9.1. Still using `entity_ids` plus optional `entity_labels`; composite keys and richer payloads are a design option, not yet implemented.
  - **Session-level extraction** — §9.2. Single extractor pass for memories + preferences + entities from session summary.
  - **Preferences unification** — §9.3. Move evidence/preferences into Qdrant + Neo4j as the single source of truth.
  - **Spaces / `space_id` dimension** — §9.4. Reserved; not yet wired into ingestion or retrieval.
  - **Expansion depth:** `expand_from_entities` currently performs one-hop expansion only; `depth` is reserved for future multi-hop traversal.

---

## 2. Neo4j Schema

### Nodes

| Node Label | Properties | Purpose |
|------------|------------|---------|
| **User** | `id`, `user_id` | Central node; multi-tenant; anchor for derived facts |
| **Memory** | `id` (Qdrant point id), `category`, `source`, `created_at` | Bridge to Qdrant. *Future:* `space_id` or `(:Memory)-[:IN_SPACE]->(:Space)` to scope retrieval by Space/Collection (Mnemo spec). |
| **Session** | `id`, `session_id`, `original_query`, `created_at` | Provenance; temporal grouping |
| **Entity** | `id`, `type`, `name`, `canonical_name`, `composite_key`, `created_at` | Person, Company, Concept, etc. `name` = display; `canonical_name` = normalized (lowercase, stripped); `composite_key` = `type::canonical_name` for dedupe so "Google" and "google" merge. |

### Relationships

| Relationship | From → To | Properties | Purpose |
|--------------|-----------|------------|---------|
| **HAS_MEMORY** | User → Memory | — | Ownership; multi-tenant |
| **FROM_SESSION** | Memory → Session | — | Provenance; "which session produced this memory" |
| **CONTAINS_ENTITY** | Memory → Entity | — | Memory mentions this entity |
| **Entity–Entity** | Entity → Entity | — | First-class: WORKS_AT, LOCATED_IN, MET, MET_AT, OWNS, PART_OF, MEMBER_OF, KNOWS, EMPLOYED_BY, LIVES_IN, BASED_IN (see `ENTITY_REL_TYPES` in knowledge_graph.py). Fallback: RELATED_TO with `type`, `value`, `confidence`, `source_memory_ids`. |
| **RELATED_TO** | Entity → Entity | `type`, `value`, `confidence`, `source_memory_ids` | Used when extractor type is not in ENTITY_REL_TYPES |
| **LIVES_IN** | User → Entity | `source_memory_ids` | Derived: user lives in City |
| **WORKS_AT** | User → Entity | `source_memory_ids` | Derived: user works at Company |
| **KNOWS** | User → Entity | `source_memory_ids` | Derived: user knows Person |
| **PREFERS** | User → Entity | `source_memory_ids` | Derived: user prefers Concept (e.g. dietary) |
| **CONTRADICTS** | (Phase 5) | — | Mark conflicting facts |

### Example Graph

```
(User {user_id: "abc"})
  -[:HAS_MEMORY]-> (Memory {id: "qdrant-123"})
  -[:FROM_SESSION]-> (Session {session_id: "run_456"})
  -[:CONTAINS_ENTITY]-> (Entity {type: "Person", name: "John"})
  -[:CONTAINS_ENTITY]-> (Entity {type: "Company", name: "Google"})

(Entity {name: "John"}) -[:WORKS_AT {source_memory_ids: ["qdrant-123"]}]-> (Entity {name: "Google"})

(User) -[:LIVES_IN {source_memory_ids: ["qdrant-123"]}]-> (Entity {type: "City", name: "Morrisville"})
```

---

## 3. Qdrant Changes

### Payload additions for `arcturus_memories`

| Field | Type | Purpose |
|-------|------|---------|
| `user_id` | string | Already exists (multi-tenant) |
| `session_id` | string | Run/session id; link to Session node |
| `entity_ids` | list[string] | Neo4j entity ids; enables Qdrant ↔ Neo4j link |

### Config

- Add `session_id` and `entity_ids` to `indexed_payload_fields` in `config/qdrant_config.yaml` if filtered search is needed.

---

## 4. Ingestion Flow

1. New memory added to Qdrant (with `user_id`, `session_id` in payload).
2. Create or get **User** and **Session** nodes in Neo4j.
3. Create **Memory** node; link `(User)-[:HAS_MEMORY]->(Memory)` and `(Memory)-[:FROM_SESSION]->(Session)`.
4. Extract entities and relationships from memory text (LLM or NER).
5. Create **Entity** nodes; link `(Memory)-[:CONTAINS_ENTITY]->(Entity)`.
6. Create entity–entity relationships using first-class types (e.g. `WORKS_AT`, `LOCATED_IN`, `OWNS`, `KNOWS`) when recognized; otherwise create `(Entity)-[:RELATED_TO {type: "...", source_memory_ids: [...] }]->(Entity)` as a generic fallback.
7. Infer user-centric facts → create `(User)-[:LIVES_IN|WORKS_AT|KNOWS|PREFERS]->(Entity)` with `source_memory_ids`.
8. Update Qdrant memory payload with `entity_ids`.

---

## 5. Retrieval Flow (Current Implementation)

```
Query: "Planning to meet John again at his office? Check weather next week?"
         │
         ├─► Path 1: Semantic recall (Qdrant vector search, k=10)
         │   - Top 3 used for direct memory context
         │   - All 10 used for entity_ids → graph expansion
         │
         ├─► Path 2: Entity recall (runs INDEPENDENTLY when kg enabled)
         │   - Extract entities from query (EntityExtractor.extract_from_query)
         │   - Resolve against Neo4j (KnowledgeGraph.resolve_entity_candidates, fuzzy)
         │   - Fallback: stop-word tokens → get_memory_ids_for_entity_names
         │   - Expand → memory_ids → fetch from Qdrant
         │   - Rescues when semantic returns 0 (e.g. "John" in query, "Jon" in memory)
         │
         └─► Merge: PREVIOUS MEMORIES + RELATED ENTITIES + ADDITIONAL MEMORIES + USER FACTS
         │
         ▼
    Fused context for agent
```

Orchestrated by `memory/memory_retriever.py`; `routers/runs.py` calls `retrieve(query)`.

Key retrieval behaviors in the current implementation:
- **Dual-path recall:** Semantic (k=10) and entity-first recall run independently; entity recall still runs when semantic returns 0.
- **Global dedupe & ordering:** A single `result_ids` set is maintained across semantic, entity-first, and graph-expanded memories; graph and entity paths batch-fetch memories when possible and append up to a small fixed number for readability. Graph-expanded `memory_ids` are ordered by `Memory.created_at DESC` (then de-duped) for deterministic results.
- **Multi-tenant safety:** Graph expansion (`expand_from_entities`) scopes memories by `(u:User {user_id})-[:HAS_MEMORY]->(m)` when `user_id` is provided, preventing cross-tenant leakage even when entities are globally deduped by `composite_key`.

---

## 6. Implementation Order

1. Add Neo4j client + schema (User, Memory, Session, Entity, relationships).
2. Entity extraction pipeline (LLM or NER).
3. Ingestion: on memory add → extract → write Neo4j → update Qdrant `entity_ids`.
4. Ensure Qdrant payload includes `user_id`, `session_id`, `entity_ids`.
5. Retrieval: Qdrant search + Neo4j expansion.
6. Migration script: backfill existing Qdrant memories → Neo4j.

---

## 7. Files Created/Modified

| File | Status |
|------|--------|
| `memory/knowledge_graph.py` | Neo4j client, schema, CRUD; `resolve_entity_candidates`, `get_memory_ids_for_entity_names`, `expand_from_entities` |
| `memory/entity_extractor.py` | LLM extraction from memory text; `extract_from_query` for lightweight NER on query |
| `memory/memory_retriever.py` | **New:** Orchestrates semantic recall (k=10), entity recall (dual path), graph expansion, merge |
| `config/qdrant_config.yaml` | `session_id` in indexed fields |
| `memory/backends/qdrant_store.py` | add() accepts `session_id`; `_ingest_to_knowledge_graph` on add |
| `routers/runs.py` | Uses `memory_retriever.retrieve(query)` instead of direct search |
| `scripts/migrate_memories_to_neo4j.py` | Backfill script |

---

## 8. How to Continue in a New Chat

Start a new chat and say:

> "Continue the Neo4j knowledge graph implementation from @CAPSTONE/project_charters/P11_NEO4J_KNOWLEDGE_GRAPH_DESIGN.md"

Or attach the file and ask to implement the design.

---

## 9. Next Steps (Recorded for Future Implementation)

*No code in this section — use this as the spec for a new context.*

### 9.1 Retrieval Gap: When Semantic Search Returns Nothing

**Status:** Implemented. A few more tweaks will be discussed in a separate context.

**Problem (was):** At agent run time we did a single vector search (top-k=3) on Qdrant. If the query did not semantically match any memory, we never called Neo4j and lost entity-matched memories (e.g. "John" in query vs "Jon" in memory).

**Implemented:**
- **Entity-first path:** `memory_retriever.py` runs entity recall **independently** of semantic search. Extract entities from query → resolve against Neo4j (fuzzy match, e.g. John↔Jon) → get memory_ids → fetch memories from Qdrant. Runs even when semantic returns 0.
- **Larger k:** Semantic recall uses k=10; top 3 for direct context; all 10 for graph expansion.
- **KnowledgeGraph:** `resolve_entity_candidates`, `get_memory_ids_for_entity_names`; `EntityExtractor.extract_from_query`.
- **Cross-type fallback:** In `resolve_entity_candidates`, fuzzy matching uses within-type candidates first, then always includes global (all_names) fallback so a wrong NER type (e.g. "John" as Concept when graph has Person) can still match.

**Tweaks pending (to be discussed in separate context):**

1. **Entity-friendly payload in Qdrant (optional)**
   - **Idea:** Store something more readable than raw `entity_ids` in Qdrant (e.g. composite keys like `Person::Jon`, `Company::Google`, or a small list of `{type, name}` objects) so we can do entity-based matching or display without always querying Neo4j.
   - **Industry practice:** Keeping only foreign IDs in the vector store is common (single source of truth in the graph). Denormalizing entity names/types into the payload is also common when you need filter-by-entity or hybrid search (e.g. keyword/entity filters in Qdrant) or to avoid a Neo4j round-trip for every read. Tradeoff: payload size and consistency (if an entity is renamed in Neo4j, you’d need to update Qdrant). A practical approach is to store both: `entity_ids` (for Neo4j link) and something like `entity_labels` or `entity_composite_keys` (for display and optional filter/expansion) so reads and entity-first retrieval can work without always hitting Neo4j.

2. **Further search refinements (if needed)** — Larger k and dual path are already in place. Possible future tweaks: tune k, top_for_context, fuzzy_threshold; or add entity labels to Qdrant for filter/display without Neo4j round-trip. *(Original ideas: larger k + entity-first fallback; both are now implemented.)*

### 9.2 Session-Level Extraction: One Pass for Memories, Preferences, and Entities

**Current limitation:** Session summaries are used to extract memories (and preferences) via the existing extractor. Those memories are then stored in Qdrant and, on add, we run entity extraction on the **memory text only**. So we can lose entities and relationships that existed in the full session but were compressed or dropped when the memory snippet was written.

**Better design:**

- **Single session-level extraction:** Update the extractor (and its output schema) so that when processing a **session summary** (or full session), it produces in one shot:
  - **Memories** (as today: add/update/delete commands or text snippets),
  - **Preferences** (as today: key-value or structured for hubs),
  - **Entities and relationships** (same structure as the current entity extractor: entities, entity_relationships, user_facts).
- **One JSON structure** from the extractor that includes all three. The ingestion pipeline then:
  - Writes memories to Qdrant (and Neo4j: Memory, Session, User, entities, relationships, user_facts) using that single extraction result, so entities are derived from the **full session context**, not from the shortened memory text.
- **Manual memory add stays separate:** When the user adds a memory directly from the UI, we only have that single text. So we keep the current flow: add to Qdrant → run entity extraction on that text → write to Neo4j and update Qdrant. No change to that path; only the **session-based** path becomes “one extraction, memories + preferences + entities.”

**Extractor change:** The remme extractor (or a unified extraction prompt/skill) would need an updated JSON schema that includes both the existing memory commands and preferences and the new entities/entity_relationships/user_facts. Downstream: same Neo4j ingestion, same Qdrant payload updates; preferences can still be written to staging/hubs as today.

### 9.3 Unifying Preferences with Qdrant + Neo4j (Longer-Term)

**Observation:** Extracted entities and user_facts (LIVES_IN, WORKS_AT, KNOWS, PREFERS) are very similar to what is stored in JSON files (e.g. `evidence_log.json`, `preferences_hub.json`, etc.). Having two places for “user preferences and facts” can lead to duplication and drift.

**Possible direction:**

- **Move preferences / evidence into Qdrant + Neo4j** so that:
  - Preference-like facts are stored as memories (Qdrant) and/or as user–entity relationships and entities (Neo4j).
  - One source of truth for “what we know about the user” for retrieval and reasoning.
- **UI and existing consumers:** Keep the current UX “more or less” the same by:
  - Adding an **adapter or service layer** that reads from Qdrant/Neo4j (and optionally from existing JSON for backward compatibility) and exposes the same or similar structure that the UI and hubs expect (e.g. same categories, same field names). Over time, the UI can be pointed only at the new store.
- **Extraction pipeline:** As in 9.2, the session-level extractor would output memories, preferences, and entities; the ingestion path would write preferences into the new store (and optionally still to JSON for a transition period). This may require mapping current hub schema (e.g. dietary_style, verbosity) to entities/concepts and user_facts (e.g. PREFERS → Concept "vegetarian") so that both the graph and the UI stay consistent.

Use this section (9) as the reference when starting a new context to implement retrieval improvements, session-level extraction, and/or preferences unification.

### 9.4 Space / space_id — Reserved Hook (Do Not Implement Yet)

**Context:** Mnemo spec includes Spaces/Collections. The graph is currently scoped by `user_id` and `session_id` only; there is no space dimension. When Spaces are introduced, cross-project retrieval could become noisy without scoping.

**Reserved design (no code yet):**
- **Option A:** Add `(:Memory)-[:IN_SPACE]->(:Space)` and a `Space` node; constrain all retrieval paths (entities for user, expand, resolve) to memories in the requested space(s).
- **Option B:** Add `space_id` as a property on `Memory` and filter queries with `WHERE m.space_id = $space_id` (or `IN $space_ids`).

**Where to add the hook when implementing:** In `memory/knowledge_graph.py`, all user-scoped reads that traverse memories (e.g. `get_entities_for_user`, `expand_from_entities`, `get_memory_ids_for_entity_names`, and any Qdrant call that uses `entity_ids` from the graph) should accept an optional `space_id` (or `space_ids`) and constrain to memories in that space. Ingestion (`create_memory`, `ingest_memory`) would accept optional `space_id` and set the relationship or property. Qdrant payload would include `space_id` for filtered search.
