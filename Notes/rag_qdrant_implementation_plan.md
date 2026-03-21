# RAG → Qdrant-first listing & optional S3 — Implementation plan

This plan keeps **blob storage** on **local disk by default** (path = Qdrant payload `doc`, relative to `data/`). **Qdrant** becomes the **source of truth for “what is indexed,” per-tenant/space scope, and (optionally) where bytes live** once S3 is enabled.

**Related doc:** [rag_qdrant_unified.md](./rag_qdrant_unified.md) (current behavior, spaces, gaps).

---

## 1. Goals

| Goal | Detail |
|------|--------|
| **Listing** | `GET /api/rag/documents` derives the indexed document set from **Qdrant** (not only `ledger.json`), scoped by **`user_id`** + **`space_id`**. |
| **Local files** | Default: `doc` = path under `PROJECT_ROOT/data/` (current convention). No requirement to move files for phase 1–3. |
| **Spaces** | Same `space_id` semantics as indexing/search today; **uploads and paths** must align so listing + search + disk stay consistent. |
| **Uploads** | New uploads are **space-aware** (correct relative path + reindex with `space_id`). |
| **S3 (last step)** | If **`RAG_S3_*`** (or equivalent) is set, **migration** can upload objects keyed by `doc`; runtime **read/write** uses S3 when configured, else local. |
| **Notes** | Notes **are** RAG documents under `data/Notes/`; same listing API, same indexing, same space convention. NotesPanel create/delete/rename must be space-aware. |

---

## 2. Target architecture (high level)

```
┌─────────────────┐     ┌──────────────────────────────────────┐     ┌─────────────┐
│  FastAPI        │     │  Qdrant                              │     │  Blobs      │
│  /rag/documents │────▶│  arcturus_rag_chunks (search)         │     │  local      │
│  /rag/upload    │     │  arcturus_rag_documents (listing)     │     │  or S3      │
└────────┬────────┘     └──────────────────────────────────────┘     └─────────────┘
         │
         └── Optional: merge with local FS scan for "unindexed" / orphan files (hybrid mode)
```

- **Chunk collection** (`arcturus_rag_chunks`) stores `doc`, `chunk`, `chunk_id`, `page`, `space_id`, `user_id` (tenant).
- **Document registry** (`arcturus_rag_documents`) — one point per doc for **O(1) listing**; see Phase 1.

---

## 3. Configuration (introduce incrementally)

| Variable | Purpose |
|----------|---------|
| `RAG_DOCUMENT_SOURCE` | `ledger` \| `qdrant` \| `hybrid` — controls `GET /documents` backend (default `ledger` until rollout, then `qdrant` or `hybrid`). |
| `RAG_VECTOR_STORE_PROVIDER` | Already: `qdrant` \| `faiss`. |
| **S3 (final phase)** | |
| `RAG_S3_BUCKET` | If set, enable S3 path for blob I/O + migration upload. |
| `RAG_S3_PREFIX` | Optional key prefix (e.g. `rag/`). Final key = `{prefix}{doc}` with `doc` normalized to POSIX, no leading `/`. |
| `RAG_S3_ENDPOINT_URL` | Optional (MinIO/custom). |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Standard; or instance role. |

**Invariant:** Qdrant payload **`doc`** is always the **logical key** (relative path under the data root), whether the bytes live under `data/` or at `s3://bucket/{prefix}{doc}`.

---

## 4. Phases

### Phase 0 — Prerequisites & API contract

**Deliverables**

- [ ] Document the canonical **`doc`** format: relative path from `data/` (e.g. `Notes/__global__/foo.md`, `Notes/<uuid>/bar.md`), POSIX separators.
- [ ] Ensure **authenticated requests** can resolve **`user_id`** server-side (same as `reindex` / MCP args today via `memory.user_id.get_user_id()` or auth-derived id) — **required** for Qdrant tenant filter on list/search.
- [ ] Add **`RAG_DOCUMENT_SOURCE`** to `.env.example` and settings loader if you centralize env there.

**Exit criteria:** Single place that returns `(user_id, space_id)` for RAG routes (query + auth).

---

### Phase 1 — Qdrant: document registry (dedicated collection)

**Problem:** Listing requires distinct documents + `chunk_count` (+ optional hash/status) without scanning the whole `data/` tree for “indexed” truth.

**Approach: Dedicated `arcturus_rag_documents` collection**

- New collection `arcturus_rag_documents` (config in `qdrant_config.yaml`):
  - One point per `(user_id, space_id, doc)` with payload: `doc`, `user_id`, `space_id`, `chunk_count`, `content_hash`, `updated_at`, `storage` (`local`|`s3`).
- **Upsert** on successful index completion in `process_documents` / scheduler (same transaction flow as chunk upsert).
- **Delete** when `delete_by_doc` is called on the chunk store.
- **Pros:** O(docs) listing — scales regardless of chunk count; clear schema; no scroll over chunks.
- **Sync:** Keep registry in sync via hooks in `process_documents` and `delete_by_doc` (cost is negligible).

**Fallback:** Scroll `arcturus_rag_chunks` and aggregate by `doc` — use only for early prototyping; switch to registry before production.

**Deliverables**

- [ ] Add `arcturus_rag_documents` to `config/qdrant_config.yaml` (keyword indexes on `user_id`, `space_id`, `doc`).
- [ ] `RAGDocumentRegistry` (or methods in qdrant store): `upsert_doc`, `delete_doc`, `list_documents(user_id, space_id)`.
- [ ] Wire registry upsert/delete into `mcp_servers/server_rag.py` (`process_documents`, `delete_by_doc` path).
- [ ] No-op or ledger-based equivalent for FAISS mode if dual provider retained.
- [ ] Unit tests with mocked Qdrant client or test container.

**Exit criteria:** Callable from FastAPI without MCP round-trip (use same `get_qdrant_url` / credentials as RAG store).

---

### Phase 2 — `GET /api/rag/documents` (Qdrant-backed)

**Behavior**

1. Resolve **`user_id`** (required for tenant Qdrant).
2. Read query **`space_id`** (same as today: omit = “all spaces” vs explicit UUID — **product decision**):
   - **Suggested default for parity with current Global UX:**  
     - `space_id` **omitted** → return **all documents** for user (group tree by `space_id` or flat list with `space_id` field).  
     - **OR** keep current UI contract: Global = omit → merge Qdrant list with full FS tree for `unindexed` only (see hybrid below).
3. **`RAG_DOCUMENT_SOURCE=qdrant`:** Build response from `list_documents` — tree structure can be **synthesized** by splitting `doc` on `/` into folder nodes (virtual tree), not only physical `os.walk`.
4. **`hybrid`:**  
   - Indexed rows from Qdrant (truth for `indexed`, `chunk_count`).  
   - Optional: walk `data/` for paths not in Qdrant → `status: unindexed` (same as ledger today).

**Spaces**

- For **non-Global** space filter: filter Qdrant results where `payload.space_id == requested_space_id` (and `user_id` match).
- **Deprecate** reliance on **folder name == UUID** as the *only* filter; keep optional **legacy FS filter** behind a flag for one release if needed.

**Deliverables**

- [ ] Refactor `routers/rag.py` `get_rag_documents` to branch on `RAG_DOCUMENT_SOURCE`.
- [ ] Virtual tree builder: `doc` paths → nested `{name, path, type, children}` JSON matching current frontend `RagItem` shape.
- [ ] Frontend: ensure `fetchRagFiles` / `fetchNotesFiles` still work; Notes may need **subset** of tree under `Notes/` only (current behavior).

**Exit criteria:** With `RAG_DOCUMENT_SOURCE=qdrant`, selecting a space shows documents that exist in Qdrant for that `space_id`, even without `data/<uuid>/` folders.

**Notes:** `fetchNotesFiles` uses the same `/documents` API with `space_id`, then extracts the `Notes` subtree (`notesRoot.children`). When the tree is Qdrant-backed, the virtual tree must include `Notes/__global__/` and `Notes/<uuid>/` nodes so the frontend can find `notesRoot` and its `children` correctly.

---

### Phase 3 — MCP / search alignment (no `metadata.json` dependency for Qdrant path)

**Goal:** When `RAG_VECTOR_STORE_PROVIDER=qdrant`, **always** prefer **`get_metadata(user_id)`** (scroll payloads) for entity gate / chunk lookup; avoid silent fallback to `metadata.json` if `user_id` is known.

**Deliverables**

- [ ] `search_stored_documents_rag`: if qdrant + `user_id` missing, log warning / surface error to caller instead of reading stale `metadata.json` (or document explicit fallback).
- [ ] Ensure **`space_id`** is passed from API → MCP for search and ask flows (audit `routers/rag.py` + agents).
- [ ] `ensure_rag_ready()`: for qdrant, readiness = **Qdrant reachable** + optional **min chunk count** or “any collection info” — reduce sole dependency on `metadata.json` (still can write it for BM25 until Phase 3b).

**Optional Phase 3b — BM25 / entity gate**

- Either regenerate BM25 from `get_metadata` in memory, or persist a sidecar derived from Qdrant scroll (replace `metadata.json` as source).

**Exit criteria:** Search and list both agree on **tenant + space** semantics.

---

### Phase 4 — Space-aware uploads, writes & Notes

**Current gaps:** `upload_rag_file`, `create_rag_folder`, `create_rag_file`, `save_rag_file`, `delete_rag_item`, `rename_rag_item` take paths but **no `space_id`**; files may land outside `Notes/<uuid>/`, so space-scoped listing would miss them.

**Target rules**

1. **API:** Add optional `space_id: Form(None)` (or JSON body) to upload, save, create_folder, create_file, delete, rename.
2. **Path resolution:**  
   - If `space_id` is set and path is “relative to Notes”, normalize to `Notes/<space_id>/<user_relative_path>` (use `__global__` literal folder name for global space if product uses that).  
   - Align with `_derive_space_id_for_notes` in `server_rag.py` so indexing assigns the same `space_id` payload.
3. **RAG panel:** Pass `currentSpaceId` when uploading (and default folder target to that space’s Notes subtree).
4. **Reindex:** After upload/create/save, trigger reindex for that path with same `user_id` + `space_id`.
5. **Delete:** When deleting a doc, remove from Qdrant (`delete_by_doc`) and from blob store (local or S3).

---

#### Notes — explicit coverage

Notes **are** RAG documents under `data/Notes/`; they use the same listing API and indexing. The NotesPanel has its own flows that must be space-aware:

| Flow | Endpoint | Current | Change |
|------|----------|---------|--------|
| **List notes** | `GET /rag/documents` | `fetchNotesFiles` passes `space_id`, extracts Notes subtree | Same; tree shape must support Notes nodes when Qdrant-backed. |
| **Create folder** | `POST /rag/create_folder` | Path like `Notes/Subfolder` — no space segment | Frontend passes `space_id` + relative path (e.g. `Subfolder`); **backend** resolves to `Notes/<space_id>/Subfolder`. |
| **Create note** | `POST /rag/create_file` | Path like `Notes/foo.md` — no space segment | Frontend passes `space_id` + relative path (e.g. `MyFolder/foo.md`); **backend** resolves to `Notes/<space_id>/MyFolder/foo.md`. |
| **Delete** | `POST /rag/delete` | Path from selected item | Path will be correct once create uses space paths; ensure delete triggers Qdrant `delete_by_doc` + blob removal. |
| **Rename** | `POST /rag/rename` | old_path, new_path | Paths must stay within space convention; consider `space_id` for validation. |
| **Save (edit)** | `POST /rag/save_file` | Path from open doc | Path already includes space segment if created correctly; add `space_id` for consistency. |
| **Wiki links / autocomplete** | `GET /rag/documents` | NotesEditor fetches **all** notes (no `space_id`) for suggestions | **Choice:** keep global (cross-space wikilinks) or scope to current space. Document decision. |

**Frontend NotesPanel changes**

- Pass `space_id` (or `__global__` for Global) and **relative path only** (e.g. `Subfolder`, `MyFolder/note.md`).
- Backend helper `resolve_rag_path(relative_path, space_id, "notes")` builds the canonical `doc` path. No path convention logic on the frontend.

**Other writers (optional / later)**

- `routers/runs.py` auto-saves reports to `data/Notes/Arcturus/` (hardcoded).
- `voice/dictation_service.py` saves to `data/Notes/Voice/`.
- These may stay as global Notes or be extended to accept `space_id` in a future phase.

---

**Deliverables**

- [ ] Extend `POST /rag/upload`, `POST /rag/create_folder`, `POST /rag/create_file`, `POST /rag/save_file`, `POST /rag/delete`, `POST /rag/rename` with `space_id`.
- [ ] Backend helper: `resolve_rag_path(relative_path, space_id, context: "notes"|"rag") -> str` — builds canonical `doc` (e.g. `Notes/<space_id>/<relative_path>`). All path logic on backend only.
- [ ] Frontend: `RagPanel` and **NotesPanel** pass `space_id` + **relative path** for all create/upload/delete/save flows; never construct `Notes/<uuid>/` on the client.
- [ ] NotesEditor: document decision on autocomplete scope (global vs space-scoped).
- [ ] E2E: create note in space A → appears in Notes list when space A selected → reindex → visible in search for space A.

**Exit criteria:** New RAG and Notes content never "disappears" when switching spaces; delete/rename work correctly within space boundaries.

---

### Phase 5 — Optional S3 blob layer

**When `RAG_S3_BUCKET` is unset:** All reads/writes use **`data/{doc}`** (current behavior).

**When set:**

1. **Key:** `f"{RAG_S3_PREFIX or ''}{doc}"` with `doc` normalized (no `..`, POSIX).
2. **Migration script** `scripts/migrate_rag_local_to_s3.py` (or extend existing migrate):
   - Input: distinct `doc` from `arcturus_rag_documents` registry (or `list_documents`).
   - For each `doc`, if local file exists → `put_object` to S3.
   - Optional: `--dry-run`, `--limit`, multipart for large files.
3. **Runtime reads** (`document_content`, preview, PDF page helpers in `routers/rag.py`):
   - If S3 configured → fetch bytes from S3; else `Path(data/doc)`.
4. **Runtime writes** (upload/save):
   - If S3 configured → write to S3 **and** optionally keep local mirror (product choice: **mirror** simplifies ripgrep; **S3-only** requires rg to skip or index from downloaded temp — document tradeoff).
5. **Payload:** Optionally add `storage: local|s3` on chunk or document registry for debugging; not strictly required if env is global.

**Deliverables**

- [ ] `memory/rag_storage.py` (or `shared/rag_blob.py`): `read_doc(doc)`, `write_doc(doc, bytes)`, `exists(doc)` — switches on env.
- [ ] Wire `upload` / `save_file` / file download routes to blob layer.
- [ ] Migration CLI + README section.

**Exit criteria:** Same Qdrant `doc` values work with either local or S3 backends.

---

### Phase 6 — Cleanup, rollout, docs

- [ ] Default `RAG_DOCUMENT_SOURCE=qdrant` in docker/example env after soak.
- [ ] Deprecation notice for folder-name-only space filtering.
- [ ] Update [rag_qdrant_unified.md](./rag_qdrant_unified.md) with “implemented” pointers.
- [ ] Load test: registry listing for your expected doc count.

---

## 5. Frontend checklist (summary)

| Area | Change |
|------|--------|
| `fetchRagFiles` / `fetchNotesFiles` | No URL change if API shape unchanged; verify tree from virtual paths. |
| `RagPanel` upload / create folder | Pass `space_id` from `currentSpaceId` (and map Global → `__global__` or omit per API contract). |
| **NotesPanel** create folder, create note, delete | Pass `space_id` + relative path only; **backend** resolves to canonical `doc` path. |
| `NotesEditor` suggestions | If still calling `/rag/documents` without `space_id`, align with Global vs space behavior (see Phase 4 Notes table). |
| Error UX | Show message if backend requires `user_id` but session missing. |

---

## 6. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Full scroll too slow | N/A — using dedicated `arcturus_rag_documents` registry for O(1) listing. |
| Registry vs chunks drift | Delete document registry points when `delete_by_doc`; reconcile job. |
| S3 + ripgrep | Keep local mirror for dev, or restrict rg to text files still on disk; document limitation. |
| Multi-user `user_id` | Never list without tenant filter in Qdrant. |

---

## 7. Suggested order of work

1. Phase 0 (user_id + env flag)  
2. Phase 1 (document registry `arcturus_rag_documents` + hooks)  
3. Phase 2 (`GET /documents` from registry + virtual tree)  
4. Phase 4 (space-aware upload) — can parallelize with Phase 3  
5. Phase 3 (MCP metadata / search alignment)  
6. Phase 5 (S3 blob + migration)  
7. Phase 6 (defaults + docs)

---

## 8. Key files to touch

| File | Role |
|------|------|
| `routers/rag.py` | `/documents`, upload/save, blob reads for previews |
| `memory/rag_backends/qdrant_rag_store.py` | `list_documents` from registry |
| `config/qdrant_config.yaml` | `arcturus_rag_documents` collection |
| `mcp_servers/server_rag.py` | Indexing hooks, `ensure_rag_ready`, search metadata |
| `memory/rag_storage.py` (new) | Local vs S3 I/O |
| `scripts/migrate_rag_local_to_s3.py` (new) | S3 backfill |
| `platform-frontend/.../RagPanel.tsx`, `store/index.ts` | `space_id` on upload |
| `platform-frontend/.../NotesPanel.tsx` | `space_id` on create_folder, create_file, delete |
| `.env.example` | All new variables |

---

*End of plan — ready for ticket breakdown / sprint planning.*
