# P11 Mnemo --- Unified Extraction & User Knowledge Model Proposal

## Purpose

This document summarizes the proposed evolution of the **P11 Mnemo
memory and knowledge graph architecture** before Phase 3 (Spaces).

Goals:

-   Unify **entity extraction** and **memory extraction**
-   Move **user preferences and profile data from JSON hubs to Neo4j**
-   Maintain **Qdrant as the semantic recall store**
-   Introduce a canonical **Fact + Evidence model**
-   Allow **UI editing of user profile/preferences** (implemented **last**)
-   Prepare the system for **future multi‑space architecture**

This document is meant to accompany:

`P11_UNIFIED_REFERENCE.md`

and serve as the **authoritative design** for implementation.

**For implementers:** Use both this document and **P11_UNIFIED_REFERENCE.md** when starting implementation. This document defines the target model and implementation order; the unified reference describes current modules, data flow, and env/config.

------------------------------------------------------------------------

# Current Situation

The current architecture contains:

### Storage Layers

**Qdrant** - Stores memory text - Used for semantic recall (RAG) -
Contains memory payload metadata

**Neo4j** - Stores entities and relationships - Stores user / session /
memory nodes

### Current JSON "Hubs"

The UI currently reads structured user information from several JSON
files:

-   `preferences_hub.json`
-   `soft_identity_hub.json`
-   `operating_context_hub.json`
-   `evidence_log.json`

Problems with current model:

1.  JSON hubs are **presentation-oriented**
2.  Evidence is not tightly linked to structured data
3.  Extraction logic is split across systems
4.  Preference values are mixed with inferred identity data
5.  UI edits cannot be cleanly reconciled with extraction confidence

------------------------------------------------------------------------

# Mapping: current preference pipeline → new architecture

The current RemMe preference flow (extractor → staging → normalizer →
belief engine → JSON hubs, plus evidence_log) is replaced as follows.
No separate normalizer or staging layer; canonical mapping and
confidence live in the unified extractor and ingestion.

| Old responsibility              | Old component   | New component            |
| --------------------------------- | --------------- | ------------------------ |
| Extract preference candidates    | extractor       | unified extractor        |
| Stage preference updates         | staging (JSON)  | **removed**              |
| Map preference to canonical field| LLM normalizer  | unified extractor        |
| Manage confidence updates       | belief engine   | ingestion logic          |
| Store preference                | JSON hub        | Neo4j Fact node          |
| Store evidence                  | evidence_log    | Neo4j Evidence node      |
| Render UI                       | JSON hub files  | adapter from Neo4j       |
| Handle unknown fields           | extras (in hub) | Fact with `namespace=extras` |

**Implications:**

- **Normalizer** is removed as a separate step; its job (raw key →
  canonical `namespace`+`key`) is done inside the unified extractor
  output and prompt.
- **Staging** is removed; extractor output goes straight to ingestion →
  Neo4j.
- **Belief engine** is replaced by ingestion-time logic that sets/updates
  Fact confidence when writing or upserting from extraction or migration.
- **Unknown fields** (today’s “extras” in soft_identity_hub) become
  Facts with `namespace=extras` and `key=<field_name>`; the adapter
  can still expose an `extras` structure for the UI.

------------------------------------------------------------------------

# High Level Architecture Direction

## Core Principle

Separate responsibilities:

### Neo4j → Canonical structured knowledge store

Responsible for:

-   Entities
-   Relationships
-   User facts
-   Preferences
-   Evidence / provenance
-   Session connections

### Qdrant → Semantic recall store

Responsible for:

-   Memory text
-   Semantic retrieval
-   Context recall

Qdrant **is not the source of truth for structured profile data**.

------------------------------------------------------------------------

# New Canonical Layer: Facts + Evidence

A new layer will be introduced into Neo4j.

## Fact Node

Represents a canonical user fact or preference.

Examples:

-   verbosity preference
-   operating system
-   dietary style
-   company
-   programming language preference

### Fact Properties

    Fact
     ├ id
     ├ user_id
     ├ namespace
     ├ key
     ├ value_type
     ├ value_text
     ├ value_number
     ├ value_bool
     ├ value_json
     ├ confidence
     ├ source_mode
     ├ status
     ├ first_seen_at
     ├ last_seen_at
     ├ last_confirmed_at
     └ editability

### Example

    namespace = preferences.output_contract
    key = verbosity.default
    value = concise
    confidence = 0.82

------------------------------------------------------------------------

## Evidence Node

Represents **why the system believes a fact is true**.

### Evidence Properties

**Required (first implementation):**

    Evidence
     ├ id
     ├ source_type      (e.g. extraction | session_summary | system_observation | migration | ui_edit)
     ├ source_ref       (memory_id or session_id; links to Memory or Session)
     └ timestamp

**Optional (add when needed for display or decay):** `signal_category`, `signal_strength`, `raw_excerpt`, `confidence_delta`.

Evidence sources: conversation turns, session summaries, extracted memories, system observations, migration, **UI edits** (implemented last).

------------------------------------------------------------------------

# Updated Neo4j Graph Model

## Nodes

    User
    Session
    Memory
    Entity
    Fact
    Evidence
    SchemaField (optional — defer until schema-driven validation or UI generation is needed)

## Relationships

    User ── HAS_MEMORY ──> Memory
    Memory ── FROM_SESSION ──> Session

    Memory ── CONTAINS_ENTITY ──> Entity

    Entity ── RELATED_TO ──> Entity

    User ── HAS_FACT ──> Fact

    Fact ── SUPPORTED_BY ──> Evidence

    Evidence ── FROM_SESSION ──> Session
    Evidence ── FROM_MEMORY ──> Memory

    Fact ── REFERS_TO ──> Entity

    Fact ── SUPERSEDES ──> Fact

Optional derived edges:

    User ── WORKS_AT ──> Company
    User ── LIVES_IN ──> Location
    User ── USES ──> Language
    User ── PREFERS ──> Concept

These edges are **derived shortcuts** from Fact + REFERS_TO Entity, not canonical truth. Maintain them in one place (see **Implementation order**, step 3: derivation table and run after Fact write).

------------------------------------------------------------------------

# Unified Extraction System

The current **entity extractor and memory extractor will be merged**.

The new system produces a **Unified Extraction Result**.

------------------------------------------------------------------------

## Unified Extraction Output

    {
      source,               // e.g. "session" | "memory"
      memories,             // list of { action, text, id? } — same as today
      entities,             // list of { type, name }
      entity_relationships, // list of { from_type, from_name, to_type, to_name, type, value?, confidence? }
      facts,                // list of { namespace, key, value_type, value?, value_text?, value_json?, entity_ref? }
      evidence_events       // list of { source_type, source_ref, timestamp?, signal_category?, raw_excerpt?, confidence_delta? }
    }

Define a **Pydantic model or JSON schema** for this structure so ingestion and tests can validate the extractor output. Map existing hub fields (e.g. verbosity, dietary_style) to fact namespace+key (e.g. preferences.output_contract.verbosity.default, identity.food.dietary_style).

------------------------------------------------------------------------

## Memories

Memories are stored in **Qdrant**.

Example:

    {
      memory_key: "...",
      text: "User prefers concise markdown responses",
      category: "preference",
      importance: 0.7,
      entity_refs: [...],
      fact_refs: [...]
    }

------------------------------------------------------------------------

## Entities

Entities extracted from conversations or memories.

Examples:

-   Python
-   React
-   Google
-   Durham
-   Kubernetes

------------------------------------------------------------------------

## Entity Relationships

Examples:

    Project ── USES ──> Language
    User ── WORKS_AT ──> Company

------------------------------------------------------------------------

## Facts

Structured user information.

Examples:

    preferences.output_contract.verbosity.default = concise
    operating.environment.os = macos
    tooling.package_manager.python = uv
    identity.food.dietary_style = non‑vegetarian

Facts may optionally reference entities.

------------------------------------------------------------------------

## Evidence

Every extracted fact must reference at least one evidence entry.

Example:

    signal_category = explicit_preference
    raw_excerpt = "Please keep responses concise"
    confidence_delta = 0.3

------------------------------------------------------------------------

# Ingestion Pipelines

## Session Pipeline

1.  Conversation/session completes

2.  Session summary generated

3.  Unified extractor runs

4.  System stores:

    -   Entities → Neo4j
    -   Relationships → Neo4j
    -   Facts → Neo4j
    -   Evidence → Neo4j
    -   Memories → Qdrant

5.  Derived edges created for retrieval.

------------------------------------------------------------------------

## Direct Memory Add Pipeline

Used when a user explicitly saves a memory.

Steps:

1.  Save memory to Qdrant
2.  Run unified extraction on memory text
3.  Update Neo4j entities / facts
4.  Update Qdrant payload metadata

------------------------------------------------------------------------

## UI Preference Edit Pipeline

When the user edits a preference via UI (implemented **last** in the implementation order):

1.  Update / create Fact node
2.  Create Evidence node with `source_type = ui_edit`
3.  Set `source_mode = ui_edit`
4.  Raise confidence (e.g. 1.0) and update `last_confirmed_at`
5.  Optionally generate memory snippet in Qdrant for audit
6.  Re-run derivation for User–Entity edges if the edited fact implies an entity relationship

------------------------------------------------------------------------

# JSON Hub Migration Strategy

The existing JSON hubs will **no longer be the source of truth**.

They will become **derived read models** generated from Neo4j.

### Mapping

  JSON Hub                Neo4j Storage
  ----------------------- -----------------------
  preferences_hub         Fact nodes
  soft_identity_hub       Fact nodes + Entities
  operating_context_hub   Fact nodes
  evidence_log            Evidence nodes

------------------------------------------------------------------------

# Confidence Model

Facts maintain confidence that evolves over time.

Signals that increase confidence:

-   explicit user statement
-   UI edit
-   repeated implicit signals
-   system observation

Signals that reduce confidence:

-   contradictions
-   stale evidence
-   corrections

------------------------------------------------------------------------

# What This Design Solves

### Unified Extraction

One system extracts:

-   memories
-   entities
-   relationships
-   facts
-   evidence

### Provenance Tracking

Every fact has supporting evidence.

### Clean UI Editing

User edits update facts without corrupting extraction history (implemented last).

### Better Graph Structure

Preferences and identity data no longer forced into entity shapes.

### Migration Friendly

JSON hubs can be reconstructed from graph data.

### Future Ready

Model supports upcoming **Spaces / multi‑tenant memory**.

------------------------------------------------------------------------

# Key Design Principles

1.  **Neo4j = structured truth**
2.  **Qdrant = semantic recall**
3.  **Facts represent user knowledge**
4.  **Evidence explains why facts exist**
5.  **Derived edges support graph retrieval**
6.  **UI hubs become read models, not storage**

------------------------------------------------------------------------

# Implementation Order

Follow this sequence so that each step has a clear deliverable and the system stays runnable. Use **P11_UNIFIED_REFERENCE.md** for existing module locations (knowledge_graph.py, entity_extractor, remme extractor, qdrant_store, etc.).

**1. Neo4j schema (Fact + Evidence)**

- Add **Fact** and **Evidence** node types and relationships to `memory/knowledge_graph.py` (or a dedicated schema module): `User─HAS_FACT→Fact`, `Fact─SUPPORTED_BY→Evidence`, `Evidence─FROM_MEMORY→Memory`, `Evidence─FROM_SESSION→Session`, `Fact─REFERS_TO→Entity`, `Fact─SUPERSEDES→Fact`.
- Create constraints/indexes for Fact (e.g. unique on `(user_id, namespace, key)` or composite key) and Evidence (id).
- Keep existing Entity and User–Entity relationship types; add **derived** flag or document in code that User–Entity edges will be maintained from Fact+REFERS_TO (see step 3). Optionally add `confidence` and `source_memory_ids` on existing User–Entity edges for backward compatibility during migration.
- **Defer:** SchemaField nodes.

**2. Unified extractor (single output schema)**

- Introduce the **feature flag** (e.g. `MNEMO_ENABLED` or repurposed `NEO4J_ENABLED`) and wire entry points (smart scan, direct memory add, GET /preferences) to branch on it: when enabled → unified path; when disabled → legacy extractor + normalizer + JSON hubs (see **Implementation notes: Feature flag**).
- Merge logic from `memory/entity_extractor.py` and `remme/extractor.py` into one **unified extractor** (new module or under `memory/`). One LLM call (or orchestrated calls) producing a single **Unified Extraction Result**: `source`, `memories`, `entities`, `entity_relationships`, `facts`, `evidence_events`.
- **Facts** in the output: list of objects with `namespace`, `key`, `value_type`, `value` (or value_text/value_number/value_bool/value_json), optional `entity_ref` (entity id or composite key for REFERS_TO). No separate top-level "preferences" dict vs "user_facts" list — both are facts (entity-ref facts map to REFERS_TO + derived User–Entity).
- **evidence_events** in the output: list with at least `source_type`, `source_ref`; optionally `signal_category`, `raw_excerpt`, `confidence_delta` for later use.
- Define the JSON schema (and optionally a Pydantic model) for the unified result so ingestion and tests can rely on it.
- Keep **extraction triggers** unchanged from current design: (a) session/summary input, (b) single memory text input (e.g. on direct memory add).

**3. Ingestion pipelines**

- **Session pipeline:** After unified extraction, write: entities and entity_relationships to Neo4j (reuse existing Entity/relationship creation); create Fact nodes and Evidence nodes; link Evidence to Session and optionally to Memory; create/update Memory in Qdrant with payload (entity_ids, optional fact_refs). **Derived User–Entity edges:** For each Fact that has an `entity_ref` and a namespace/key that implies a user–entity relationship type (e.g. identity.work.company → WORKS_AT, identity.location → LIVES_IN, preferences.*.preference → PREFERS), create or update the corresponding User–Entity edge. Implement this derivation in one place (e.g. after Fact write) so retrieval continues to use existing graph expansion.
- **Direct memory add pipeline:** Same as today: save memory to Qdrant, run unified extraction on memory text, write entities/facts/evidence to Neo4j, update Qdrant payload. Derive User–Entity edges from new facts.
- Ensure **idempotency** where possible (e.g. Fact upsert by user_id + namespace + key; Evidence append).

**4. Adapter (read path for UI)**

- Add a **service or module** that reads from Neo4j: collect all Facts for the user (and optionally derived User–Entity edges) and build the same structure as the current `GET /remme/preferences` response (output_contract, operating_context, soft_identity, evidence summary, meta). Map Fact namespace+key to the existing hub shape; resolve conflicts by confidence and last_confirmed_at.
- Wire `GET /remme/preferences` (or equivalent) to this adapter when Neo4j is enabled; keep optional fallback to JSON hubs during rollout.

**5. Migration (JSON → Neo4j)**

- One-time script: for each existing JSON hub (preferences_hub, operating_context_hub, soft_identity_hub), parse the file and create Fact nodes (and optionally Evidence nodes if evidence_log is imported). Map hub field paths to Fact namespace+key; set source_mode = migration and confidence from hub meta if available. Create Evidence from evidence_log if desired. Run derivation to backfill User–Entity edges where applicable.
- After migration: adapter reads from Neo4j; optionally keep JSON as read-only fallback or remove writes to JSON.

**6. Phase 3 (Spaces) preparation**

- When implementing Spaces: add space_id (or Space node and IN_SPACE) to Memory and optionally to Fact. Scope adapter and derivation by space so that "current space" preferences and facts are what the UI and retrieval see. No code required in this design phase; ensure Fact/Memory schema can accept an optional space_id or relationship.

**7. UI edit pipeline (last)**

- When the user edits a preference/fact in the UI: **upsert** the Fact (set value, value_type, etc.); set `source_mode = ui_edit`, update `last_confirmed_at` and confidence (e.g. 1.0); **create** an Evidence node with `source_type = ui_edit`, `source_ref` = session or a synthetic ref, link Fact─SUPPORTED_BY→Evidence. Optionally create a short memory snippet in Qdrant for audit. **Re-run derivation** for User–Entity edges if the edited fact implies an entity relationship.

------------------------------------------------------------------------

# Implementation Notes (Coding Guidance)

These notes are intended to make implementation easier and avoid overbuilding the first version.

**Feature flag: Mnemo vs legacy path**

- Introduce a single config flag to choose between the **new unified Mnemo path** and the **legacy path** while the feature is developed and tested. Options:
  - **Option A:** New env var **`MNEMO_ENABLED`** (e.g. in `.env`). When `true`, use unified extractor, Neo4j Fact/Evidence, and adapter for preferences; when `false`, use existing RemMe extractor, staging, normalizer, belief engine, and JSON hubs.
  - **Option B:** Repurpose and rename **`NEO4J_ENABLED`** so that it gates the full Mnemo path (unified extraction + Neo4j for entities and for Fact/Evidence). When `false`, use legacy extractor + normalizer + JSON hubs; when `true`, use unified extractor and Neo4j for both entities and preferences. If repurposing, document the new meaning and consider keeping backward compatibility (e.g. read both `NEO4J_ENABLED` and `MNEMO_ENABLED` during transition, then drop the old name).
- **When flag is false:** Keep using the existing RemMe extractor (`remme/extractor.py`), staging store, normalizer (`remme/normalizer.py`), belief engine, and JSON hubs. No unified extractor, no Fact/Evidence writes, no adapter read from Neo4j for preferences.
- **When flag is true:** Use the unified extractor, ingestion to Neo4j (entities + Fact + Evidence), and adapter to serve `GET /remme/preferences` from Neo4j. Do not use staging, normalizer, or JSON hub writes for preferences.
- **Deprecation:** Mark the old extractor, normalizer, staging, and any hub-write paths as **deprecated** (e.g. module-level deprecation warnings or comments) while keeping them in the codebase and tested. Once the new path is stable and the flag is always on, remove the deprecated code and the flag check.
- **`.env.example`:** Document the chosen flag (e.g. `MNEMO_ENABLED=true`) and that when false, legacy extractor and normalizer are used.

**Evidence node — start minimal**

- Implement only **id**, **source_type**, **source_ref**, **timestamp** for Evidence at first. Add `signal_category`, `signal_strength`, `raw_excerpt`, `confidence_delta` when building features that use them (e.g. "why do we believe this?" in UI, or confidence decay).

**Fact source_mode**

- **extraction** and **migration** are used from steps 1–6. **ui_edit** is used when step 7 (UI edit pipeline) is implemented.

**Fact value storage**

- Use **value_type** to choose which of value_text, value_number, value_bool, value_json is set. For list or nested struct (e.g. by_scope), use value_json. Keep a single source of truth in code for "which Fact keys use which value_type" (e.g. a small mapping or constant set).

**Derived User–Entity edges**

- Define a **single derivation table** in code: which (namespace, key) or (namespace pattern) maps to which relationship type (WORKS_AT, LIVES_IN, PREFERS, USES, etc.) and which Entity type. Run this after every Fact create/update that has an entity_ref. Use MERGE so repeated extraction does not duplicate edges. This keeps retrieval logic (expand_from_entities, user facts) unchanged.

**Unified extractor prompt**

- Single prompt (or system + user) that asks for: memories (add/update/delete), entities, entity_relationships, facts (namespace, key, value, optional entity_ref), and evidence_events (source_type, source_ref, optional excerpt). Output schema as JSON; validate with Pydantic before ingestion.

**Qdrant payload**

- Current payload: user_id, session_id, entity_ids (and optional entity_labels). Optionally add **fact_refs** (list of Fact ids) when a memory supports facts, so that vector-side filtering or display can use it. Not required for the first version; entity_ids remain sufficient for graph expansion.

**Idempotency**

- Fact: upsert by (user_id, namespace, key). On conflict, update value and timestamps; optionally merge evidence (append new Evidence, keep old). Evidence: append-only; no update. Entity and relationships: keep existing get_or_create / MERGE semantics.

**Testing**

- Unit tests: unified extractor output parsing; Fact/Evidence creation from sample extraction result. Integration tests: session pipeline end-to-end (extract → Neo4j + Qdrant); adapter returns shape compatible with current GET /preferences. Reuse or extend tests in `tests/acceptance/p11_mnemo/` and `tests/integration/` per P11_UNIFIED_REFERENCE.md.

**Reference files for implementation**

- **P11_UNIFIED_REFERENCE.md** — Current status, module map, data flow, env vars, remaining work (§8).
- **This document** — Target model, pipelines, implementation order, coding notes.

------------------------------------------------------------------------

# Next Steps (Checklist)

Use the **Implementation order** above as the main plan. High-level checklist:

1.  Introduce **Fact + Evidence** nodes and relationships in Neo4j (step 1).
2.  Implement **Unified Extraction** output schema and merge extractors (step 2).
3.  Update **ingestion pipelines** (session + direct memory add) and **derived User–Entity edges** (step 3).
4.  Build **adapter** to generate UI hub shape from Neo4j (step 4).
5.  **Migrate** legacy JSON hubs into graph (step 5).
6.  Prepare for **Phase 3: Spaces** when ready (step 6).
7.  Implement **UI edit** pipeline (step 7 — last).
