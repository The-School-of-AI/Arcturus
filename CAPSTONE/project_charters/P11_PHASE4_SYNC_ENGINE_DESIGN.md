# P11 Phase 4 — Sync Engine Design

**Status:** Design only (no code yet).  
**Goals:** CRDT-based sync, offline-first, selective sync per space.  
**Reference:** P11_UNIFIED_REFERENCE.md §8.5; current stack: Qdrant + Neo4j, Spaces, user_id.

---

## 1. Design goals (from charter)

| Goal | Meaning |
|------|--------|
| **CRDT-based sync** | Conflict-free replication across devices; no central lock; merge is commutative, associative, idempotent. |
| **Offline-first** | Local store is source of truth; full read/write offline; sync when connected. |
| **Selective sync** | Per-space sync policy: some spaces sync to cloud/other devices, some are local-only (privacy). |

---

## 2. Industry practices we follow

### 2.1 Offline-first

- **Local DB as source of truth** — UI and agents read/write only to local store; network is optional.
- **Sync as background process** — Sync engine runs asynchronously; never blocks reads/writes.
- **Change tracking** — Every mutable entity has a sync footprint: version, device_id, timestamp, and optionally a CRDT state so we know what to push/pull.
- **Network detection** — When connectivity returns, trigger sync (push then pull, or pull-then-merge-then-push depending on strategy).

### 2.2 CRDT sync

- **Convergence** — All replicas that have seen the same set of updates converge to the same state.
- **No coordination** — No single “master”; any device can write; merge is deterministic.
- **Operational transform vs state-based** — We prefer **state-based** or **op-based** CRDTs: either merge whole CRDT states, or merge ordered ops (e.g. LWW register, OR-Set, RGA for text). For “memories” and “facts,” **last-writer-wins (LWW)** or **OR-Set** (for collections) are typical.
- **Hybrid approach** — Many production systems use CRDTs only where conflicts are likely (e.g. rich text, lists); for simple records (e.g. “memory text,” “fact value”) **vector clocks + LWW** or **version vectors** are enough and simpler.

### 2.3 Selective sync

- **Policy per scope** — Sync policy is attached to a scope (here: **space**). Possible values: `sync` (full sync), `local_only` (never leave device).
- **Metadata sync** — Space list and space metadata (name, description) must sync so all devices know which spaces exist; policy is stored with space metadata (e.g. `sync_policy: "sync" | "local_only"`).
- **Filter on sync** — When pushing/pulling, include only entities whose scope (space_id) has policy `sync`; local_only spaces are never sent to server/other devices.

---

## 3. Scope: what we sync

From the current Mnemo stack, the **syncable units** are:

| Entity | Store | Identified by | Sync strategy |
|--------|--------|---------------|----------------|
| **Memory** | Qdrant (vector + payload) | `memory_id` (UUID) | Per-memory; payload includes `space_id`, `user_id`, timestamps. Vector is derived (embedding of text); sync payload + text, recompute vector on receiver if needed. |
| **Space** | Neo4j (Space node) | `space_id` (UUID) | Space metadata (name, description, **sync_policy**) must sync so devices agree on list and policy. |
| **Session** | Neo4j | `session_id` (run_id) | Session belongs to a space; sync if space is synced. |
| **Fact** | Neo4j | (user_id, namespace, key, space_id) | Sync if space is synced (or global); global facts always synced. |
| **Evidence** | Neo4j | Evidence id | Tied to Fact; sync with fact. |
| **Entity / Memory–Entity** | Neo4j | Entity id, CONTAINS_ENTITY | Derived from memories; sync with memories (or recompute on receiver). |

**Out of scope for Phase 4 (or later):**

- **RAG chunks** — Separate collection; can be Phase 4+ (same patterns apply).
- **Episodic session summaries** — Local JSON; can stay local or be synced later with same engine.

**Simplification for v1:**  
Sync **Memories** (Qdrant + Neo4j Memory/Session/Entity graph) and **Spaces** (metadata + sync_policy). **Facts/Evidence** can be Phase 4.1 after memories+spaces work, since they already have space_id and the same filter applies.

---

## 4. Data model for sync

### 4.1 Sync metadata (per syncable entity)

Every syncable record carries:

- **`version`** — Monotonically increasing or vector clock / hybrid logical clock; used for LWW or merge.
- **`device_id`** — Origin device (e.g. UUID per device); breaks ties for LWW.
- **`updated_at`** — Logical or wall-clock time; used for ordering and conflict resolution.
- **`deleted`** — Soft-delete flag so deletes propagate (tombstones).

For **CRDT-style** we can use:

- **LWW (last-writer-wins):** `(updated_at, device_id)` as tiebreaker; winner overwrites.
- **OR-Set:** For “set of memory IDs” or “set of facts” we only add/remove; no in-place edit conflict.

Memories are **replaceable units**: full replace of text + payload is enough. So **LWW per memory** is sufficient; we don’t need CRDT for the text body. Same for Space metadata and for Fact value. So:

- **Sync protocol:** Version vector or logical timestamps + LWW per entity.
- **CRDT:** Use for “which set of memory IDs exist” (OR-Set) so add/delete from different devices merge cleanly; the content of each memory is LWW.

### 4.2 Where to store sync metadata

- **Qdrant (memories):** Add payload fields: `version`, `device_id`, `updated_at`, `deleted` (optional). Existing: `user_id`, `space_id`, `session_id`, `created_at`, `updated_at`.
- **Neo4j:**  
  - **Space:** Add `version`, `device_id`, `updated_at`, `sync_policy` (`"sync"` | `"local_only"`).  
  - **Memory node:** Already has `id` (Qdrant id); add `version`, `device_id`, `updated_at`, `deleted` if we mirror sync state in Neo4j (optional; can derive from Qdrant).  
  - **Fact/Evidence:** Same idea: version + device_id + updated_at for LWW.

Prefer **single source of truth for sync state**: e.g. Qdrant payload for memories, Neo4j properties for Space/Fact. Avoid duplicating sync state in two DBs; one store is authoritative per entity type.

---

## 5. Architecture

### 5.1 High-level

```
┌─────────────────────────────────────────────────────────────────┐
│  Device A (e.g. laptop)                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │ UI / Agent  │───▶│ Local Store  │◀───▶│ Sync Engine (A)   │  │
│  │             │    │ Qdrant+Neo4j │    │ - Push/Pull        │  │
│  └─────────────┘    └──────────────┘    │ - Conflict (LWW)   │  │
│         │                   │          │ - Selective filter │  │
│         │                   │          └──────────┬──────────┘  │
└─────────┼───────────────────┼────────────────────┼─────────────┘
          │                   │                    │
          │                   │              Network (when online)
          │                   │                    │
┌─────────┼───────────────────┼────────────────────┼─────────────┘
│         │                   │                    ▼
│  ┌──────▼──────┐    ┌───────▼───────┐    ┌───────────────────┐  │
│  │ Sync Server │    │ Cloud Store   │    │ Sync Engine (B)   │  │
│  │ (optional)  │    │ Qdrant+Neo4j  │◀───│ Device B (phone)  │  │
│  └─────────────┘    └───────────────┘    └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

- **Local store:** Same as today: Qdrant + Neo4j (local or remote). For true offline-first, “local” means a local Qdrant/Neo4j or SQLite+vector store on device; for a first release, “local” can be “this server instance” and “cloud” another server, or we introduce a proper local DB later.
- **Sync engine:** Component that (1) tracks changes (or scans for version/updated_at), (2) pushes changes to a **sync service**, (3) pulls changes from sync service, (4) merges (LWW/OR-Set), (5) applies only to entities in spaces with `sync_policy = sync`.

### 5.2 Sync server (central or peer)

Two patterns:

- **Central server:** All devices push/pull to one backend. Server stores canonical copy (or just a relay of ops). Simpler for multi-device and auth.
- **Peer-to-peer:** Devices exchange ops directly (e.g. WebRTC or local network). No server; harder for discovery and auth.

**Recommendation:** Start with a **central sync service** (HTTP + optional WebSocket for live push). Server exposes:

- `POST /sync/push` — Client sends batch of changes (memories, space metadata, optionally facts).
- `POST /sync/pull` — Client sends “since” cursor / version vector; server returns changes after that for the user and for spaces with `sync_policy = sync`.
- Optional: `GET /sync/stream` (WebSocket) for real-time notifications.

Server stores **sync log** or **replicated store** (e.g. same Qdrant + Neo4j in “cloud” mode). Sync engine on each device is stateless except for local DB and last pull cursor.

### 5.3 Offline-first flow

1. **Read path:** Always from local store. No change to current API; routers already read from `remme_store` and Neo4j.
2. **Write path (e.g. add memory):**  
   - Write to local store (Qdrant + Neo4j) with `version = local_clock++, device_id = this_device`.  
   - Enqueue “dirty” entity for sync (or mark table/queue).  
   - Return success to client immediately.
3. **Background sync (when online):**  
   - **Push:** For each dirty entity, if its `space_id` has `sync_policy = sync`, send to server.  
   - **Pull:** Ask server for changes since last known version; merge into local store (LWW); update last cursor.  
   - **Conflict:** LWW by (updated_at, device_id). No user prompt for v1.

### 5.4 Selective sync (per-space)

- **Space list:** Sync all space metadata (so every device sees the same spaces) but **do not sync content** of spaces marked `local_only`.
- **Storage:** In Neo4j, Space node: `sync_policy: "sync" | "local_only"` (default `sync` for backward compat).
- **Filtering:**  
  - **Push:** Only include memories (and facts) whose `space_id` has `sync_policy = sync` (or global).  
  - **Pull:** Server only returns memories/facts for spaces with `sync_policy = sync` (and global).  
- **Local-only creation:** When creating a space, user can set “Keep on this device only”; we set `sync_policy = "local_only"`. That space never appears in push payload and is excluded from pull.

---

## 6. Component breakdown

### 6.1 New / modified modules

| Component | Responsibility |
|-----------|----------------|
| **memory/sync/engine.py** | SyncEngine: orchestrate push/pull, call adapters, apply merge (LWW). |
| **memory/sync/transport.py** | HTTP (and optional WS) client to sync server: push batch, pull since cursor. |
| **memory/sync/merge.py** | Merge logic: LWW for memory/space/fact; OR-Set for “set of IDs” if needed. |
| **memory/sync/change_tracker.py** | Track dirty entities (or scan by updated_at); build push payload. |
| **memory/sync/policy.py** | Resolve sync_policy for space_id; filter entities for push/pull. |
| **memory/sync/schema.py** | Pydantic models: SyncPayload, MemoryDelta, SpaceDelta, VersionVector, etc. |
| **Backend sync API** (e.g. **routers/sync.py**) | `POST /sync/push`, `POST /sync/pull`; validate user_id; write to cloud store. |
| **Config** | Feature flag `SYNC_ENGINE_ENABLED`; `SYNC_SERVER_URL`; optional `DEVICE_ID` (or generate per instance). |

### 6.2 Integration points

- **remme_store.add() / delete():** After write, set `version`, `device_id`, `updated_at`; optionally enqueue for sync.  
- **knowledge_graph.create_space():** Add `sync_policy`; set `version`, `device_id`, `updated_at`.  
- **memory_retriever / routers:** No change to read path; they already read from local store.  
- **Startup / connectivity:** On app start or network up, run SyncEngine.pull() then SyncEngine.push() in background.

---

## 7. Sync protocol (v1)

### 7.1 Push

- Client sends `POST /sync/push` with body:  
  `{ "user_id": "...", "device_id": "...", "changes": [ { "type": "memory"|"space"|"fact", "payload": {...}, "version": 1, "updated_at": "ISO8601", "deleted": false } ] }`
- Server:  
  - Validates user_id (and auth if present).  
  - For each change, if space is `sync` (or global): merge into cloud store (LWW).  
  - Returns `{ "accepted": true, "cursor": "..." }` or per-item errors.

### 7.2 Pull

- Client sends `POST /sync/pull` with body:  
  `{ "user_id": "...", "device_id": "...", "since_cursor": "..." }` (or since_version / version vector).
- Server returns:  
  `{ "changes": [ ... ], "cursor": "..." }`  
  Only entities in spaces with `sync_policy = sync` (and global).
- Client: Merge into local store (LWW), then set last cursor.

### 7.3 Cursor / versioning

- **Cursor:** Opaque string encoding “last seen” position (e.g. server log sequence or timestamp).  
- **Version per entity:** Single logical clock per device, or hybrid logical clock; enough to order and break ties (device_id).

---

## 8. CRDT in practice for Mnemo

- **Memories:** Treat each memory as an **LWW register**: one writer wins by (updated_at, device_id). No need for a full CRDT on text.  
- **Set of memory IDs:** If we ever need “presence set” (which memories exist), an **OR-Set** (add/remove only) gives conflict-free set merge; then each ID’s content is LWW.  
- **Spaces:** LWW for name/description/sync_policy.  
- **Facts:** LWW per (user_id, namespace, key, space_id).

So we **don’t** require a generic CRDT library (e.g. Automerge) for Phase 4; **version + LWW + optional OR-Set** is enough and keeps the stack simple. If we later add collaborative editing of a single memory text, we could introduce RGA/CRDT for that field only.

---

## 9. Security and privacy

- **Auth:** Sync endpoints must be authenticated (e.g. same user_id as in session; or token).  
- **Encryption in transit:** HTTPS only.  
- **Local-only spaces:** Never leave the device; server has no content for those space_ids.  
- **Server:** Should not log or retain content of local_only spaces; push payload for local_only is never sent.

---

## 10. Implementation order (suggested)

1. **Schema & config** — Add `version`, `device_id`, `updated_at` (and optional `deleted`) to Qdrant payload and Neo4j Space; add `sync_policy` to Space. Feature flag and sync server URL.  
2. **Sync schema (Pydantic)** — Push/pull payloads, cursor, deltas.  
3. **Policy & filter** — Resolve sync_policy per space; filter list for push/pull.  
4. **Merge (LWW)** — Merge logic for incoming changes.  
5. **Change tracker** — Mark dirty or scan by updated_at; build push list.  
6. **Transport** — HTTP client for push/pull.  
7. **Sync engine** — Orchestrate push then pull on interval or on connectivity.  
8. **Backend sync API** — `POST /sync/push`, `POST /sync/pull` with cloud store.  
9. **Integration** — After add_memory/create_space, enqueue for sync; on startup/network-up trigger sync.  
10. **Tests** — Unit tests for merge and policy; integration test: two “devices” push/pull and converge.

---

## 11. Out of scope for v1

- Peer-to-peer sync (no server).  
- Full CRDT for in-place text editing (RGA/Automerge).  
- Real-time live sync (WebSocket) — can be added after HTTP push/pull works.  
- Sync of RAG collection.  
- Multi-user collaboration (same space, multiple users); single-user multi-device only.

---

## 12. References

- P11_UNIFIED_REFERENCE.md §8.5 (Phase 4 goal).  
- Offline-first: Local DB as source of truth; sync as background.  
- CRDT: Conflict-free merge; LWW and OR-Set sufficient for our entities.  
- Selective sync: Per-space `sync_policy`; filter push/pull by policy.

This design keeps industry best practices (offline-first, CRDT-style convergence, selective sync) while fitting the existing Mnemo stack (Qdrant, Neo4j, Spaces) and avoiding unnecessary complexity (no full CRDT library for v1).
