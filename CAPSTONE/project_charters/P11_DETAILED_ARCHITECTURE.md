# P11 Mnemo — Detailed Architecture

High-level architecture and key features of the Mnemo (Real-Time Memory & Knowledge Graph) system for Arcturus. Intended for professors and team members who need a concise, readable overview.

---

## 1. What Mnemo Is

Mnemo turns Arcturus memory from local, file-based storage into a **smart, interconnected system** that:

- **Finds things quickly** — Vector search (Qdrant) plus keyword (sparse/BM25) and entity-based recall
- **Shows how concepts connect** — Knowledge graph (Neo4j) with entities and relationships
- **Organizes by Spaces** — Perplexity-style project hubs; memories and runs scoped by space
- **Syncs across devices** — CRDT-style (LWW) sync with selective per-space policy
- **Supports auth and lifecycle** — Login/register, guest flow, importance scoring, archival, contradiction detection

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Frontend (platform-frontend)                        │
│  SpacesPanel │ Runs │ RemMe (Add Memory) │ Graph Explorer │ Login/Register    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Backend API (FastAPI)                            │
│  /runs │ /remme/* │ /api/sync/* │ /auth/* │ /api/graph/explore               │
└─────────────────────────────────────────────────────────────────────────────┘
         │                    │                    │                    │
         ▼                    ▼                    ▼                    ▼
┌──────────────┐    ┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│ Memory       │    │ Vector Store   │    │ Sync Engine  │    │ Auth / User     │
│ Retriever    │    │ (Qdrant/FAISS) │    │ (push/pull)  │    │ (JWT, migration)│
└──────┬───────┘    └───────┬────────┘    └──────┬───────┘    └─────────────────┘
       │                    │                    │
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Knowledge Graph (Neo4j)                              │
│  User, Memory, Session, Entity, Fact, Evidence, Space │ Relationships       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Data flow (simplified):**

- **Write path:** User adds memory or runs a session → RemMe/runs API → Qdrant (vector + payload) → Neo4j (entities, facts, session–space link). Optional: Sync engine pushes changes to server.
- **Read path:** Run/agent needs context → Memory Retriever → semantic search (Qdrant) + entity recall (Neo4j) + graph expansion → fused context for the agent.

---

## 3. Key Components

### 3.1 Vector Store (Qdrant / FAISS)

| Aspect | Description |
|--------|-------------|
| **Role** | Stores memory and RAG chunk vectors; semantic and hybrid (vector + sparse) search. |
| **Collections** | `arcturus_memories` (RemMe), `arcturus_rag_chunks` (RAG), `arcturus_episodic` (session skeletons). |
| **Multi-tenancy** | All scoped by `user_id`; memories/RAG/episodic also by `space_id` where applicable. |
| **Provider** | `VECTOR_STORE_PROVIDER=qdrant` (default `faiss` for backward compatibility). |

### 3.2 Knowledge Graph (Neo4j)

| Aspect | Description |
|--------|-------------|
| **Role** | Structured truth: entities, relationships, facts, evidence, spaces; links to Qdrant via `memory_id` / `entity_ids`. |
| **Main node types** | User, Memory, Session, Entity, Fact, Evidence, Space. |
| **Relationships** | HAS_MEMORY, FROM_SESSION, CONTAINS_ENTITY, entity–entity (e.g. WORKS_AT, KNOWS), User–Entity (LIVES_IN, WORKS_AT, KNOWS, PREFERS), HAS_FACT, SUPPORTED_BY, IN_SPACE, SHARED_WITH. |
| **Retrieval** | Entity extraction from query → resolve entities in Neo4j → memory IDs → fetch from Qdrant; graph expansion from semantic results. |

### 3.3 Memory Retriever

- **Semantic path:** Qdrant vector search (k=10); optional hybrid with sparse (BM25-style) + RRF fusion.
- **Entity path:** Query NER → Neo4j resolve → memory IDs → Qdrant; runs even when semantic returns 0.
- **Graph expansion:** From semantic results’ `entity_ids`; one-hop expansion; space-scoped when run is in a space.
- **Output:** Fused, deduplicated context for the planner/agent.

### 3.4 Spaces & Collections

- **Space:** Logical container (e.g. “Startup Research”, “Personal”). Backed by Neo4j Space node and `space_id` in Qdrant payloads.
- **Scoping:** Memories, runs, sessions, and (optionally) facts are associated with a space or global (`__global__`).
- **Retrieval:** When a run is in a non-global space, only that space’s memories/entities are used (no global injection).
- **Sync policy:** Per space: `sync`, `local_only`, or `shared` (enables sharing with other users).

### 3.5 Sync Engine

- **Model:** LWW (last-writer-wins) per memory/space; conflict-free convergence.
- **Endpoints:** `POST /api/sync/push`, `POST /api/sync/pull`, `POST /api/sync/trigger`.
- **Selective sync:** Only entities in spaces with `sync_policy` = sync or shared are pushed/pulled.
- **Identity:** `user_id` from auth context (JWT or X-User-Id); body `user_id` ignored.

### 3.6 Auth & Lifecycle

- **Auth:** Register, login, guest (X-User-Id); JWT (HS256) with `MNEMO_SECRET_KEY`; guest→registered migration.
- **Lifecycle:** Importance scoring, archival, contradiction edges between facts; memory visibility (private/space/public).

---

## 4. Where Memory Is Used

| Consumer | What it uses | Purpose |
|----------|----------------|--------|
| **PlannerAgent / Runs** | Memory Retriever (Qdrant + Neo4j), preferences (adapter from Neo4j facts) | Context for planning and answers |
| **RemMe (Add Memory)** | Vector store (add), KG ingestion, recommend-space API | Store and organize memories |
| **Episodic memory** | Qdrant `arcturus_episodic` or legacy JSON | Session skeletons for replay/reasoning |
| **RAG** | Qdrant `arcturus_rag_chunks` (vector + sparse), Notes path-derived `space_id` | Document and note search |
| **Graph Explorer** | Neo4j subgraph via `GET /api/graph/explore` | Visualization of entities and relationships |

---

## 5. Configuration at a Glance

| Area | Key env vars |
|------|----------------|
| Vector | `VECTOR_STORE_PROVIDER`, `QDRANT_URL`, `QDRANT_API_KEY`, `RAG_VECTOR_STORE_PROVIDER` |
| Graph | `NEO4J_ENABLED`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` |
| Mnemo unified | `MNEMO_ENABLED` (unified extractor, Neo4j facts, adapter) |
| Sync | `SYNC_ENGINE_ENABLED`, `SYNC_SERVER_URL`, `DEVICE_ID` |
| Auth | `MNEMO_SECRET_KEY` (required for login/register) |
| Episodic | `EPISODIC_STORE_PROVIDER` (qdrant \| legacy) |

---

## 6. Future Enhancements and Improvements

- **Multi-hop expansion:** Current graph expansion is one-hop; `depth` parameter reserved for future use.
- **Graph query API:** Dedicated endpoint for structured reasoning (“What do I know about X and how does it relate to Y?”).
- **Full spaces manager UI:** Beyond SpacesPanel (permissions, bulk actions, analytics).
- **Sharding / federated search:** Per-user shards with cross-user federated search for shared spaces.
- **Embedded / “Lite” mode:** Optional embedded Qdrant and embedded graph (e.g. Kùzu) for local-only, no-Docker setups.
- **Production JWT:** Move from HS256 to RS256 for production; use public/private key pair and document key configuration (see `P11_AUTH_DESIGN.md`).

---

**Related documents:** `P11_SETUP_GUIDE.md`, `P11_DELIVERY_README.md`, `P11_mnemo_real_time_memory_knowledge_graph.md` (original charter).
